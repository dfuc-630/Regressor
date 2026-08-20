"""
Validators for the Docs-as-Database Markdown format.

Checks:
  1. YAML frontmatter completeness
  2. ID uniqueness across all files within a topic
  3. Broken references (depends_on, implements, etc. pointing to non-existent IDs)
  4. Line limits per doc_type
  5. Required files presence
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import NamedTuple

from .models import (
    DocType,
    ParsedCorpus,
    ParsedDocument,
    ParsedTopic,
)

logger = logging.getLogger(__name__)


# ── Configuration ──────────────────────────────────────────────────────

# doc_type → filename mapping
DOC_TYPE_TO_FILENAME = {
    DocType.REQUIREMENTS: "01-requirements.md",
    DocType.BUSINESS_RULES: "02-business-rules.md",
    DocType.DATA_MODELS: "03-data-models.md",
    DocType.API_CONTRACTS: "04-api-contracts.md",
    DocType.COMPONENTS: "05-components.md",
    DocType.DECISIONS: "06-decisions.md",
    DocType.DEPENDENCIES: "07-dependencies.md",
    DocType.PLAN: "08-plan.md",
    DocType.GLOSSARY: "09-glossary.md",
}

# Required files (must exist in every version folder)
REQUIRED_DOC_TYPES = {
    DocType.REQUIREMENTS,
    DocType.COMPONENTS,
    DocType.PLAN,
}

# Line limits per doc_type (None = unlimited)
LINE_LIMITS: dict[DocType, int | None] = {
    DocType.REQUIREMENTS: 200,
    DocType.BUSINESS_RULES: 200,
    DocType.DATA_MODELS: None,
    DocType.API_CONTRACTS: None,
    DocType.COMPONENTS: None,
    DocType.DECISIONS: None,
    DocType.DEPENDENCIES: None,
    DocType.PLAN: 200,
    DocType.GLOSSARY: 100,
}


# ── Result Types ───────────────────────────────────────────────────────

class ValidationIssue(NamedTuple):
    severity: str   # "ERROR" | "WARNING"
    file: str       # source file path or topic id
    message: str


class ValidationResult:
    def __init__(self) -> None:
        self.issues: list[ValidationIssue] = []

    def error(self, file: str, msg: str) -> None:
        self.issues.append(ValidationIssue("ERROR", file, msg))

    def warning(self, file: str, msg: str) -> None:
        self.issues.append(ValidationIssue("WARNING", file, msg))

    @property
    def errors(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "ERROR"]

    @property
    def warnings(self) -> list[ValidationIssue]:
        return [i for i in self.issues if i.severity == "WARNING"]

    @property
    def is_valid(self) -> bool:
        return len(self.errors) == 0

    def summary(self) -> str:
        lines = []
        for issue in sorted(self.issues, key=lambda i: (i.severity, i.file)):
            lines.append(f"[{issue.severity}] {issue.file}: {issue.message}")
        if not lines:
            return "✅ All validations passed."
        return "\n".join(lines)


# ── Validators ─────────────────────────────────────────────────────────

def _collect_all_ids(doc: ParsedDocument) -> list[str]:
    """Collect all node IDs defined in a single document."""
    ids: list[str] = []
    for req in doc.requirements:
        ids.append(req.id)
    for rule in doc.business_rules:
        ids.append(rule.id)
    for entity in doc.entities:
        ids.append(entity.id)
        for f in entity.fields:
            ids.append(f.id)
    for ep in doc.endpoints:
        ids.append(ep.id)
    for comp in doc.components:
        ids.append(comp.id)
    for dec in doc.decisions:
        ids.append(dec.id)
    for dep in doc.dependencies:
        ids.append(dep.id)
    for task in doc.tasks:
        ids.append(task.id)
    for term in doc.terms:
        ids.append(term.id)
    return ids


def _collect_all_references(doc: ParsedDocument) -> list[str]:
    """Collect all IDs that are referenced by nodes in this document."""
    refs: list[str] = []
    for req in doc.requirements:
        refs.extend(req.depends_on)
        refs.extend(req.implements)
    for rule in doc.business_rules:
        refs.extend(rule.applies_to)
        refs.extend(rule.depends_on)
    for comp in doc.components:
        refs.extend(comp.implements)
        refs.extend(comp.fallback)
    for dec in doc.decisions:
        refs.extend(dec.affects)
        if dec.supersedes:
            refs.append(dec.supersedes)
    for dep in doc.dependencies:
        if dep.from_component:
            refs.append(dep.from_component)
        if dep.to_component and not dep.to_component.startswith("external:") and not dep.to_component.startswith("sys-"):
            refs.append(dep.to_component)
    for task in doc.tasks:
        refs.extend(task.implements)
        refs.extend(task.covers)
        refs.extend(task.depends_on)
    for term in doc.terms:
        refs.extend(term.used_by)
    return refs


def validate_frontmatter(doc: ParsedDocument, result: ValidationResult) -> None:
    """Check YAML frontmatter completeness."""
    fm = doc.frontmatter
    src = str(doc.source_path)

    if not fm.topic:
        result.error(src, "Frontmatter missing 'topic' field")
    if not fm.version:
        result.error(src, "Frontmatter missing 'version' field")
    if not fm.doc_type:
        result.error(src, "Frontmatter missing 'doc_type' field")

    # Check doc_type matches filename
    expected_filename = DOC_TYPE_TO_FILENAME.get(fm.doc_type)
    if expected_filename and doc.source_path.name != expected_filename:
        result.warning(
            src,
            f"doc_type '{fm.doc_type.value}' expects filename '{expected_filename}', "
            f"got '{doc.source_path.name}'",
        )


def validate_line_limits(doc: ParsedDocument, result: ValidationResult) -> None:
    """Check that file doesn't exceed line limit for its doc_type."""
    limit = LINE_LIMITS.get(doc.frontmatter.doc_type)
    if limit is None:
        return

    try:
        content = doc.source_path.read_text(encoding="utf-8")
        line_count = len(content.splitlines())
        if line_count > limit:
            result.warning(
                str(doc.source_path),
                f"File has {line_count} lines, exceeds limit of {limit} for "
                f"{doc.frontmatter.doc_type.value}",
            )
    except OSError:
        pass


def validate_id_uniqueness(topic: ParsedTopic, result: ValidationResult) -> None:
    """Check that all node IDs are unique within a topic's active version."""
    active_docs = topic.versions.get(topic.active_version, [])
    seen: dict[str, str] = {}  # id → source file

    for doc in active_docs:
        for node_id in _collect_all_ids(doc):
            if node_id in seen:
                result.error(
                    str(doc.source_path),
                    f"Duplicate ID '{node_id}' — also defined in {seen[node_id]}",
                )
            else:
                seen[node_id] = str(doc.source_path)


def validate_references(topic: ParsedTopic, result: ValidationResult) -> None:
    """Check that all referenced IDs actually exist in the topic."""
    active_docs = topic.versions.get(topic.active_version, [])

    # Collect all defined IDs
    all_ids: set[str] = set()
    for doc in active_docs:
        all_ids.update(_collect_all_ids(doc))

    # Check all references
    for doc in active_docs:
        for ref_id in _collect_all_references(doc):
            # Skip special prefixes (external systems, kafka, etc.)
            if ref_id.startswith(("external:", "sys-", "kafka")):
                continue
            # Skip "None" or empty
            if not ref_id or ref_id.lower() in ("none", "null", ""):
                continue
            if ref_id not in all_ids:
                result.warning(
                    str(doc.source_path),
                    f"Reference to '{ref_id}' not found in topic '{topic.topic_id}'",
                )


def validate_required_files(topic: ParsedTopic, result: ValidationResult) -> None:
    """Check that required doc types exist in the active version."""
    active_docs = topic.versions.get(topic.active_version, [])
    present_types = {doc.frontmatter.doc_type for doc in active_docs}

    for required in REQUIRED_DOC_TYPES:
        if required not in present_types:
            result.warning(
                topic.topic_id,
                f"Missing required file: {DOC_TYPE_TO_FILENAME[required]} "
                f"in version {topic.active_version}",
            )


# ── Main Validation Entry ─────────────────────────────────────────────

def validate_corpus(corpus: ParsedCorpus) -> ValidationResult:
    """Run all validations on a parsed corpus.

    Returns a ValidationResult with all issues found.
    """
    result = ValidationResult()

    for topic in corpus.topics:
        # Topic-level validations
        validate_id_uniqueness(topic, result)
        validate_references(topic, result)
        validate_required_files(topic, result)

        # Document-level validations
        for version_docs in topic.versions.values():
            for doc in version_docs:
                validate_frontmatter(doc, result)
                validate_line_limits(doc, result)

    # Report corpus-level parse errors
    for err in corpus.errors:
        result.error("corpus", err)
    for warn in corpus.warnings:
        result.warning("corpus", warn)

    return result
