"""
Deterministic parser for the Docs-as-Database Markdown format.

Walks the /docs directory, reads each .md file, extracts:
  1. YAML frontmatter  →  Frontmatter dataclass
  2. Tagged list items  →  Knowledge-type dataclasses (Requirement, BusinessRule, …)

Zero LLM usage — pure YAML + Regex.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any

import yaml

from .models import (
    BusinessRule,
    Component,
    Decision,
    Dependency,
    DocType,
    Domain,
    Endpoint,
    Entity,
    Field,
    Frontmatter,
    ParsedCorpus,
    ParsedDocument,
    ParsedTopic,
    Requirement,
    Task,
    TaskStatus,
    Term,
)

logger = logging.getLogger(__name__)

# ── Regex Patterns ─────────────────────────────────────────────────────

# Matches a tagged list item:  - [ID] {meta} Description
#   or a task item:            - [ ] [ID] {meta} Description
#   or a task done item:       - [x] [ID] {meta} Description
_TAGGED_ITEM_RE = re.compile(
    r"^-\s+"
    r"(?:\[(?P<task_status>[x ])\]\s+)?"   # Optional task checkbox [ ] or [x]
    r"\[(?P<id>[A-Z][\w-]+)\]"              # [NODE-ID]
    r"(?:\s+\{(?P<meta>[^}]*)\})?"          # Optional {key: val, key: val}
    r"(?:\s+(?P<text>.+))?$",               # Optional description text
    re.MULTILINE,
)

# Matches a sub-field line:  - KEYWORD: value
_SUB_FIELD_RE = re.compile(
    r"^\s+-\s+(?P<key>[A-Z][A-Z_]+):\s+(?P<value>.+)$",
    re.MULTILINE,
)

# Matches an indented child item (e.g. Field inside Entity):
#   - [FIELD-01] {meta} text
_CHILD_ITEM_RE = re.compile(
    r"^\s+-\s+\[(?P<id>[A-Z][\w-]+)\]"
    r"(?:\s+\{(?P<meta>[^}]*)\})?"
    r"(?:\s+(?P<text>.+))?$",
    re.MULTILINE,
)

# YAML frontmatter delimiter
_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ── Meta Parser ────────────────────────────────────────────────────────

def _parse_meta(meta_str: str | None) -> dict[str, Any]:
    """Parse the {key: value, key: value} meta string into a dict.

    Handles:
      - Simple values:     priority: high
      - Array values:      depends_on: [REQ-01, REQ-02]
      - Quoted strings:    name: "Some Name"
      - Boolean values:    required: true
    """
    if not meta_str:
        return {}

    result: dict[str, Any] = {}
    # Use a mini YAML parser by wrapping in braces
    try:
        parsed = yaml.safe_load("{" + meta_str + "}")
        if isinstance(parsed, dict):
            # Normalize list values: ensure they are always lists
            for k, v in parsed.items():
                if isinstance(v, str) and v.startswith("[") and v.endswith("]"):
                    # Parse "[A, B]" string as list
                    inner = v[1:-1].strip()
                    result[k] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
                else:
                    result[k] = v
            return result
    except yaml.YAMLError:
        pass

    # Fallback: manual comma-split parsing
    for pair in meta_str.split(","):
        pair = pair.strip()
        if ":" not in pair:
            continue
        key, _, val = pair.partition(":")
        key = key.strip()
        val = val.strip()
        # Handle array values
        if val.startswith("[") and val.endswith("]"):
            inner = val[1:-1].strip()
            result[key] = [x.strip() for x in inner.split(",") if x.strip()] if inner else []
        elif val.lower() in ("true", "false"):
            result[key] = val.lower() == "true"
        else:
            result[key] = val
    return result


def _ensure_list(val: Any) -> list[str]:
    """Normalize a value to a list of strings."""
    if val is None:
        return []
    if isinstance(val, list):
        return [str(x) for x in val]
    if isinstance(val, str):
        # Remove all square brackets to handle "[A], [B]" or "[A, B]"
        val = val.replace("[", "").replace("]", "").strip()
        if not val:
            return []
        return [x.strip() for x in val.split(",") if x.strip()]
    return [str(val)]


# ── Sub-field Collector ────────────────────────────────────────────────

def _collect_sub_fields(lines: list[str], start_idx: int) -> dict[str, str]:
    """Starting after a tagged item line, collect indented sub-field lines.

    Returns dict like {'WHEN': '...', 'THEN': '...', 'REASON': '...'}.
    """
    fields: dict[str, str] = {}
    children_ids: list[dict[str, Any]] = []
    idx = start_idx

    while idx < len(lines):
        line = lines[idx]
        # Stop if we hit a non-indented line or another top-level item
        if not line.startswith("  ") and not line.startswith("\t"):
            break
        # Check for sub-field (  - KEYWORD: value)
        m = _SUB_FIELD_RE.match(line)
        if m:
            fields[m.group("key")] = m.group("value")
            idx += 1
            continue
        # Check for child item (  - [CHILD-ID] {meta} text)
        m = _CHILD_ITEM_RE.match(line)
        if m:
            child_meta = _parse_meta(m.group("meta"))
            child_meta["__id__"] = m.group("id")
            child_meta["__text__"] = m.group("text") or ""
            children_ids.append(child_meta)
            idx += 1
            continue
        idx += 1

    if children_ids:
        fields["__children__"] = children_ids  # type: ignore[assignment]
    return fields


# ── Frontmatter Parser ────────────────────────────────────────────────

def _parse_frontmatter(content: str) -> tuple[Frontmatter | None, str]:
    """Extract YAML frontmatter from file content.

    Returns (Frontmatter, body_without_frontmatter) or (None, content).
    """
    m = _FRONTMATTER_RE.match(content)
    if not m:
        return None, content

    try:
        data = yaml.safe_load(m.group(1))
    except yaml.YAMLError as e:
        logger.warning("Failed to parse YAML frontmatter: %s", e)
        return None, content

    if not isinstance(data, dict):
        return None, content

    try:
        domain = Domain(data.get("domain", "Feature"))
    except ValueError:
        domain = Domain.FEATURE

    try:
        doc_type = DocType(data.get("doc_type", "Requirements"))
    except ValueError:
        doc_type = DocType.REQUIREMENTS

    fm = Frontmatter(
        domain=domain,
        topic=data.get("topic", ""),
        version=data.get("version", ""),
        doc_type=doc_type,
        depends_on=_ensure_list(data.get("depends_on")),
        gitnexus_processes=_ensure_list(data.get("gitnexus_processes")),
        last_updated=str(data.get("last_updated", "")),
        author=str(data.get("author", "")),
    )
    body = content[m.end():]
    return fm, body


# ── Node Builders (per doc_type) ──────────────────────────────────────

def _build_requirements(lines: list[str]) -> list[Requirement]:
    results: list[Requirement] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("REQ-") and not m.group("id").startswith("CON-"):
            continue
        meta = _parse_meta(m.group("meta"))
        node_id = m.group("id")
        sub = _collect_sub_fields(lines, i + 1)

        # Determine category from section context
        category = ""
        if node_id.startswith("CON-"):
            category = "constraint"

        results.append(Requirement(
            id=node_id,
            text=m.group("text") or "",
            priority=str(meta.get("priority", "")),
            category=meta.get("category", category),
            type=str(meta.get("type", "")),
            depends_on=_ensure_list(meta.get("depends_on", sub.get("DEPENDS_ON", ""))),
            implements=_ensure_list(meta.get("implements", sub.get("IMPLEMENTS", ""))),
            meta=meta,
        ))
    return results


def _build_business_rules(lines: list[str]) -> list[BusinessRule]:
    results: list[BusinessRule] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("RULE-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)
        results.append(BusinessRule(
            id=m.group("id"),
            when_condition=sub.get("WHEN", ""),
            then_action=sub.get("THEN", ""),
            reason=sub.get("REASON", ""),
            priority=str(meta.get("priority", "")),
            examples=sub.get("EXAMPLES", ""),
            applies_to=_ensure_list(meta.get("applies_to", sub.get("APPLIES_TO", ""))),
            depends_on=_ensure_list(meta.get("depends_on", sub.get("DEPENDS_ON", ""))),
            meta=meta,
        ))
    return results


def _build_entities(lines: list[str]) -> list[Entity]:
    results: list[Entity] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("ENTITY-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)

        fields: list[Field] = []
        children = sub.get("__children__", [])
        if isinstance(children, list):
            for child in children:
                child_id = child.get("__id__", "")
                if child_id.startswith("FIELD-"):
                    fields.append(Field(
                        id=child_id,
                        name=str(child.get("name", "")),
                        type=str(child.get("type", "")),
                        required=bool(child.get("required", False)),
                        indexed=bool(child.get("indexed", False)),
                        default=str(child.get("default", "")),
                        example=str(child.get("example", "")),
                        unit=str(child.get("unit", "")),
                        primary_key=bool(child.get("primary_key", False)),
                        foreign_key=str(child.get("foreign_key", "")),
                        values=_ensure_list(child.get("values")),
                        currency=str(child.get("currency", "")),
                        value=str(child.get("value", "")),
                        meta=child,
                    ))

        # Handle collection/table naming from meta
        collection = str(meta.get("collection", meta.get("table", "")))

        results.append(Entity(
            id=m.group("id"),
            name=str(meta.get("name", "")),
            storage=str(meta.get("storage", "")),
            collection_or_table=collection,
            symbol=str(meta.get("symbol", "")),
            key_pattern=str(meta.get("key_pattern", "")),
            fields=fields,
            meta=meta,
        ))
    return results


def _build_endpoints(lines: list[str]) -> list[Endpoint]:
    results: list[Endpoint] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("API-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)

        # Parse PARAMS sub-field if present
        params: list[dict[str, str]] = []
        params_str = sub.get("PARAMS", "")
        if params_str:
            # Parse [{name: x, type: y, required: z}, ...]
            try:
                parsed = yaml.safe_load(params_str)
                if isinstance(parsed, list):
                    params = parsed
            except yaml.YAMLError:
                pass

        # Collect RESPONSE_XXX sub-fields
        responses: dict[str, Any] = {}
        errors: list[dict[str, str]] = []
        for key, val in sub.items():
            if key.startswith("RESPONSE_"):
                status_code = key.replace("RESPONSE_", "")
                try:
                    responses[status_code] = yaml.safe_load(val)
                except yaml.YAMLError:
                    responses[status_code] = val
            elif key == "ERRORS":
                try:
                    parsed = yaml.safe_load(val)
                    if isinstance(parsed, list):
                        errors = parsed
                except yaml.YAMLError:
                    pass

        results.append(Endpoint(
            id=m.group("id"),
            method=str(meta.get("method", "")),
            path=str(meta.get("path", "")),
            auth=str(meta.get("auth", "")),
            rate_limit=str(meta.get("rate_limit", "")),
            cache_strategy=str(meta.get("cache_strategy", "")),
            symbol=str(meta.get("symbol", "")),
            params=params,
            responses=responses,
            side_effects=sub.get("SIDE_EFFECTS", ""),
            errors=errors,
            meta=meta,
        ))
    return results


def _build_components(lines: list[str]) -> list[Component]:
    results: list[Component] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("COMP-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)
        results.append(Component(
            id=m.group("id"),
            type=str(meta.get("type", "")),
            responsibility=sub.get("RESPONSIBILITY", m.group("text") or ""),
            layer=str(meta.get("layer", "")),
            inputs=sub.get("INPUTS", ""),
            outputs=sub.get("OUTPUTS", ""),
            symbols=_ensure_list(meta.get("symbols", sub.get("SYMBOLS", ""))),
            implements=_ensure_list(meta.get("implements", sub.get("IMPLEMENTS", ""))),
            fallback=_ensure_list(meta.get("fallback", sub.get("FALLBACK", ""))),
            kafka_topic=sub.get("KAFKA_TOPIC", ""),
            meta=meta,
        ))
    return results


def _build_decisions(lines: list[str]) -> list[Decision]:
    results: list[Decision] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("DEC-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)

        # Parse ALTERNATIVES
        alternatives: list[dict[str, str]] = []
        alt_str = sub.get("ALTERNATIVES", "")
        if alt_str:
            try:
                parsed = yaml.safe_load(alt_str)
                if isinstance(parsed, list):
                    alternatives = parsed
            except yaml.YAMLError:
                pass

        results.append(Decision(
            id=m.group("id"),
            title=sub.get("TITLE", ""),
            context=sub.get("CONTEXT", ""),
            decision=sub.get("DECISION", ""),
            consequences=sub.get("CONSEQUENCES", ""),
            status=str(meta.get("status", "accepted")),
            date=str(meta.get("date", "")),
            impact=str(meta.get("impact", "")),
            alternatives=alternatives,
            affects=_ensure_list(meta.get("affects", sub.get("AFFECTS", ""))),
            supersedes=str(meta.get("supersedes", "")),
            meta=meta,
        ))
    return results


def _build_dependencies(lines: list[str]) -> list[Dependency]:
    results: list[Dependency] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("DEP-"):
            continue
        meta = _parse_meta(m.group("meta"))
        # Collect the description from the next indented line
        desc = ""
        if i + 1 < len(lines):
            next_line = lines[i + 1].strip()
            if next_line and not next_line.startswith("- ["):
                desc = next_line

        results.append(Dependency(
            id=m.group("id"),
            from_component=str(meta.get("from", "")),
            to_component=str(meta.get("to", "")),
            type=str(meta.get("type", "")),
            condition=str(meta.get("condition", "")),
            topic=str(meta.get("topic", "")),
            timeout=str(meta.get("timeout", "")),
            description=desc or m.group("text") or "",
            meta=meta,
        ))
    return results


def _build_tasks(lines: list[str]) -> list[Task]:
    results: list[Task] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("TASK-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)

        # Determine status from checkbox
        task_checkbox = m.group("task_status")
        if task_checkbox is not None:
            status = TaskStatus.DONE if task_checkbox == "x" else TaskStatus.TODO
        else:
            status = TaskStatus.TODO

        results.append(Task(
            id=m.group("id"),
            description=m.group("text") or "",
            status=status,
            assignee=str(meta.get("assignee", "")),
            completed_by=str(meta.get("completed_by", "")),
            date=str(meta.get("date", "")),
            phase=str(meta.get("phase", "")),
            type=str(meta.get("type", "")),
            impact_radius=str(meta.get("impact_radius", "")),
            implements=_ensure_list(meta.get("implements", sub.get("IMPLEMENTS", ""))),
            covers=_ensure_list(meta.get("covers", sub.get("COVERS", ""))),
            depends_on=_ensure_list(meta.get("depends_on", sub.get("DEPENDS_ON", ""))),
            meta=meta,
        ))
    return results


def _build_terms(lines: list[str]) -> list[Term]:
    results: list[Term] = []
    for i, line in enumerate(lines):
        m = _TAGGED_ITEM_RE.match(line)
        if not m or not m.group("id").startswith("TERM-"):
            continue
        meta = _parse_meta(m.group("meta"))
        sub = _collect_sub_fields(lines, i + 1)
        results.append(Term(
            id=m.group("id"),
            name=str(meta.get("name", "")),
            definition=sub.get("DEFINITION", ""),
            context=sub.get("CONTEXT", ""),
            aliases=_ensure_list(meta.get("aliases")),
            examples=sub.get("EXAMPLES", ""),
            used_by=_ensure_list(meta.get("used_by", sub.get("USED_BY", ""))),
            meta=meta,
        ))
    return results


# ── Document-level dispatcher ─────────────────────────────────────────

_BUILDER_MAP = {
    DocType.REQUIREMENTS: lambda lines: {"requirements": _build_requirements(lines)},
    DocType.BUSINESS_RULES: lambda lines: {"business_rules": _build_business_rules(lines)},
    DocType.DATA_MODELS: lambda lines: {"entities": _build_entities(lines)},
    DocType.API_CONTRACTS: lambda lines: {"endpoints": _build_endpoints(lines)},
    DocType.COMPONENTS: lambda lines: {"components": _build_components(lines)},
    DocType.DECISIONS: lambda lines: {"decisions": _build_decisions(lines)},
    DocType.DEPENDENCIES: lambda lines: {"dependencies": _build_dependencies(lines)},
    DocType.PLAN: lambda lines: {"tasks": _build_tasks(lines)},
    DocType.GLOSSARY: lambda lines: {"terms": _build_terms(lines)},
}


def parse_file(path: Path) -> ParsedDocument | None:
    """Parse a single Markdown file into a ParsedDocument."""
    try:
        content = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        logger.error("Cannot read %s: %s", path, e)
        return None

    fm, body = _parse_frontmatter(content)
    if fm is None:
        logger.warning("No valid YAML frontmatter in %s — skipping", path)
        return None

    lines = body.splitlines()
    builder = _BUILDER_MAP.get(fm.doc_type)

    doc = ParsedDocument(source_path=path, frontmatter=fm)
    if builder:
        nodes = builder(lines)
        for attr, values in nodes.items():
            setattr(doc, attr, values)

    return doc


# ── Directory walker ──────────────────────────────────────────────────

def _find_active_version(version_dirs: list[Path]) -> str:
    """Return the name of the highest-numbered version folder."""
    version_names = sorted(
        [d.name for d in version_dirs],
        key=lambda n: int(re.sub(r"[^0-9]", "", n) or "0"),
        reverse=True,
    )
    return version_names[0] if version_names else ""


def parse_docs(docs_dir: Path) -> ParsedCorpus:
    """Parse the entire /docs directory into a ParsedCorpus.

    Expected structure:
        docs/
          features/<topic>/<version>/*.md
          systems/<topic>/<version>/*.md
    """
    corpus = ParsedCorpus()

    for domain_name, domain_enum in [("features", Domain.FEATURE), ("systems", Domain.SYSTEM)]:
        domain_dir = docs_dir / domain_name
        if not domain_dir.is_dir():
            continue

        for topic_dir in sorted(domain_dir.iterdir()):
            if not topic_dir.is_dir():
                continue

            topic_id = topic_dir.name
            version_dirs = [d for d in topic_dir.iterdir() if d.is_dir()]
            if not version_dirs:
                continue

            active_version = _find_active_version(version_dirs)
            topic = ParsedTopic(
                topic_id=topic_id,
                domain=domain_enum,
                active_version=active_version,
            )

            for version_dir in sorted(version_dirs):
                version_name = version_dir.name
                docs: list[ParsedDocument] = []
                for md_file in sorted(version_dir.glob("*.md")):
                    parsed = parse_file(md_file)
                    if parsed:
                        docs.append(parsed)
                    else:
                        corpus.warnings.append(f"Skipped unparseable file: {md_file}")
                topic.versions[version_name] = docs

            corpus.topics.append(topic)

    logger.info(
        "Parsed %d topics, %d total documents",
        len(corpus.topics),
        sum(len(docs) for t in corpus.topics for docs in t.versions.values()),
    )
    return corpus
