"""
Neo4j Ingestor — pushes ParsedCorpus into Neo4j via Cypher MERGE.

Uses the official ``neo4j`` Python driver directly (no Graphiti, no LLM).
All operations are idempotent via MERGE statements.
"""

from __future__ import annotations

import json
import logging
from typing import Any

from neo4j import GraphDatabase, Driver, Session

from .models import (
    BusinessRule,
    Component,
    Decision,
    Dependency,
    Domain,
    Endpoint,
    Entity,
    Field,
    ParsedCorpus,
    ParsedDocument,
    ParsedTopic,
    Requirement,
    Task,
    Term,
)

logger = logging.getLogger(__name__)


# ── Schema Setup ───────────────────────────────────────────────────────

_INDEX_STATEMENTS = [
    "CREATE INDEX IF NOT EXISTS FOR (n:Feature) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:System) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Version) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Requirement) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:BusinessRule) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Entity) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Field) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Endpoint) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Component) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Decision) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Dependency) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Task) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Term) ON (n.id)",
    "CREATE INDEX IF NOT EXISTS FOR (n:Symbol) ON (n.name)",
]


def _ensure_indexes(session: Session) -> None:
    for stmt in _INDEX_STATEMENTS:
        session.run(stmt)
    logger.info("Neo4j indexes ensured")


# ── Helper ─────────────────────────────────────────────────────────────

def _safe_props(obj: Any, exclude: set[str] | None = None) -> dict[str, Any]:
    """Convert a dataclass to a flat dict suitable for Cypher parameters.

    Drops None values, empty strings, empty lists, nested objects, and
    any keys in *exclude*.
    """
    exclude = exclude or set()
    props: dict[str, Any] = {}
    for key, val in vars(obj).items():
        if key.startswith("_") or key in exclude:
            continue
        if val is None or val == "" or val == []:
            continue
        if isinstance(val, list):
            # Only keep lists of primitives
            if val and isinstance(val[0], (str, int, float, bool)):
                props[key] = val
            continue
        if isinstance(val, dict):
            # Serialize dicts as JSON strings
            props[key] = json.dumps(val, ensure_ascii=False)
            continue
        if isinstance(val, (str, int, float, bool)):
            props[key] = val if not hasattr(val, "value") else val.value
            continue
        # Enum
        if hasattr(val, "value"):
            props[key] = val.value
            continue
    return props


# ── Topic/Version Ingestion ────────────────────────────────────────────

def _ingest_topic(session: Session, topic: ParsedTopic) -> None:
    """Create Feature/System node and Version nodes."""
    label = "Feature" if topic.domain == Domain.FEATURE else "System"

    session.run(
        f"MERGE (t:{label} {{id: $id}}) SET t.name = $id, t.domain = $domain",
        id=topic.topic_id,
        domain=topic.domain.value,
    )

    for version_name, docs in topic.versions.items():
        is_active = version_name == topic.active_version
        version_id = f"{topic.topic_id}/{version_name}"
        session.run(
            "MERGE (v:Version {id: $id}) "
            "SET v.name = $name, v.topic = $topic, v.is_active = $is_active",
            id=version_id,
            name=version_name,
            topic=topic.topic_id,
            is_active=is_active,
        )
        # Connect topic → version
        session.run(
            f"MATCH (t:{label} {{id: $topic_id}}), (v:Version {{id: $version_id}}) "
            "MERGE (t)-[:HAS_VERSION]->(v)",
            topic_id=topic.topic_id,
            version_id=version_id,
        )

        # Cross-topic dependencies from YAML frontmatter
        for doc in docs:
            for dep_topic in doc.frontmatter.depends_on:
                session.run(
                    "MATCH (v:Version {id: $version_id}) "
                    "MERGE (dep {id: $dep_id}) "
                    "MERGE (v)-[:DEPENDS_ON_TOPIC]->(dep)",
                    version_id=version_id,
                    dep_id=dep_topic,
                )


# ── Node Ingestion Functions ───────────────────────────────────────────

def _ingest_requirements(session: Session, version_id: str, reqs: list[Requirement]) -> None:
    for req in reqs:
        props = _safe_props(req, exclude={"depends_on", "implements", "meta"})
        session.run(
            "MERGE (r:Requirement {id: $id}) SET r += $props "
            "WITH r "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(r)",
            id=req.id, props=props, version_id=version_id,
        )
        for dep_id in req.depends_on:
            session.run(
                "MATCH (a:Requirement {id: $a_id}), (b:Requirement {id: $b_id}) "
                "MERGE (a)-[:DEPENDS_ON]->(b)",
                a_id=req.id, b_id=dep_id,
            )


def _ingest_business_rules(session: Session, version_id: str, rules: list[BusinessRule]) -> None:
    for rule in rules:
        props = _safe_props(rule, exclude={"applies_to", "depends_on", "meta"})
        session.run(
            "MERGE (r:BusinessRule {id: $id}) SET r += $props "
            "WITH r "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(r)",
            id=rule.id, props=props, version_id=version_id,
        )
        for ref_id in rule.applies_to:
            session.run(
                "MATCH (br:BusinessRule {id: $br_id}), (req:Requirement {id: $req_id}) "
                "MERGE (br)-[:APPLIES_TO]->(req)",
                br_id=rule.id, req_id=ref_id,
            )
        for dep_id in rule.depends_on:
            session.run(
                "MATCH (a:BusinessRule {id: $a_id}), (b:BusinessRule {id: $b_id}) "
                "MERGE (a)-[:DEPENDS_ON]->(b)",
                a_id=rule.id, b_id=dep_id,
            )


def _ingest_entities(session: Session, version_id: str, entities: list[Entity]) -> None:
    for entity in entities:
        props = _safe_props(entity, exclude={"fields", "meta"})
        session.run(
            "MERGE (e:Entity {id: $id}) SET e += $props "
            "WITH e "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(e)",
            id=entity.id, props=props, version_id=version_id,
        )
        # Symbol link
        if entity.symbol:
            session.run(
                "MERGE (s:Symbol {name: $name}) "
                "WITH s "
                "MATCH (e:Entity {id: $entity_id}) "
                "MERGE (e)-[:MAPS_TO_SYMBOL]->(s)",
                name=entity.symbol, entity_id=entity.id,
            )
        # Fields
        for f in entity.fields:
            f_props = _safe_props(f, exclude={"meta"})
            session.run(
                "MERGE (f:Field {id: $id}) SET f += $props "
                "WITH f "
                "MATCH (e:Entity {id: $entity_id}) "
                "MERGE (f)-[:BELONGS_TO]->(e)",
                id=f.id, props=f_props, entity_id=entity.id,
            )
            # Also link field to version
            session.run(
                "MATCH (v:Version {id: $version_id}), (f:Field {id: $field_id}) "
                "MERGE (v)-[:DEFINES]->(f)",
                version_id=version_id, field_id=f.id,
            )


def _ingest_endpoints(session: Session, version_id: str, endpoints: list[Endpoint]) -> None:
    for ep in endpoints:
        props = _safe_props(ep, exclude={"params", "responses", "errors", "meta"})
        # Serialize complex fields
        if ep.params:
            props["params_json"] = json.dumps(ep.params, ensure_ascii=False)
        if ep.responses:
            props["responses_json"] = json.dumps(ep.responses, ensure_ascii=False)
        if ep.errors:
            props["errors_json"] = json.dumps(ep.errors, ensure_ascii=False)

        session.run(
            "MERGE (ep:Endpoint {id: $id}) SET ep += $props "
            "WITH ep "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(ep)",
            id=ep.id, props=props, version_id=version_id,
        )
        if ep.symbol:
            session.run(
                "MERGE (s:Symbol {name: $name}) "
                "WITH s "
                "MATCH (ep:Endpoint {id: $ep_id}) "
                "MERGE (ep)-[:MAPS_TO_SYMBOL]->(s)",
                name=ep.symbol, ep_id=ep.id,
            )


def _ingest_components(session: Session, version_id: str, components: list[Component]) -> None:
    for comp in components:
        props = _safe_props(comp, exclude={"symbols", "implements", "fallback", "meta"})
        session.run(
            "MERGE (c:Component {id: $id}) SET c += $props "
            "WITH c "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(c)",
            id=comp.id, props=props, version_id=version_id,
        )
        # Symbol links
        for sym_name in comp.symbols:
            session.run(
                "MERGE (s:Symbol {name: $name}) "
                "WITH s "
                "MATCH (c:Component {id: $comp_id}) "
                "MERGE (c)-[:MAPS_TO_SYMBOL]->(s)",
                name=sym_name, comp_id=comp.id,
            )
        # Implements links
        for ref_id in comp.implements:
            session.run(
                "MATCH (c:Component {id: $comp_id}), (r:Requirement {id: $req_id}) "
                "MERGE (c)-[:IMPLEMENTS]->(r)",
                comp_id=comp.id, req_id=ref_id,
            )
        # Fallback links
        for fb_id in comp.fallback:
            session.run(
                "MATCH (a:Component {id: $a_id}), (b:Component {id: $b_id}) "
                "MERGE (a)-[:FALLBACK_TO]->(b)",
                a_id=comp.id, b_id=fb_id,
            )


def _ingest_decisions(session: Session, version_id: str, decisions: list[Decision]) -> None:
    for dec in decisions:
        props = _safe_props(dec, exclude={"alternatives", "affects", "supersedes", "meta"})
        if dec.alternatives:
            props["alternatives_json"] = json.dumps(dec.alternatives, ensure_ascii=False)

        session.run(
            "MERGE (d:Decision {id: $id}) SET d += $props "
            "WITH d "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(d)",
            id=dec.id, props=props, version_id=version_id,
        )
        for ref_id in dec.affects:
            session.run(
                "MATCH (d:Decision {id: $dec_id}), (c:Component {id: $comp_id}) "
                "MERGE (d)-[:AFFECTS]->(c)",
                dec_id=dec.id, comp_id=ref_id,
            )
        if dec.supersedes and dec.supersedes.lower() not in ("none", "null", ""):
            session.run(
                "MATCH (a:Decision {id: $a_id}), (b:Decision {id: $b_id}) "
                "MERGE (a)-[:SUPERSEDES]->(b)",
                a_id=dec.id, b_id=dec.supersedes,
            )


def _ingest_dependencies(session: Session, version_id: str, deps: list[Dependency]) -> None:
    for dep in deps:
        props = _safe_props(dep, exclude={"from_component", "to_component", "meta"})
        session.run(
            "MERGE (d:Dependency {id: $id}) SET d += $props "
            "WITH d "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(d)",
            id=dep.id, props=props, version_id=version_id,
        )
        # FROM edge
        if dep.from_component:
            session.run(
                "MATCH (d:Dependency {id: $dep_id}), (c:Component {id: $comp_id}) "
                "MERGE (d)-[:FROM]->(c)",
                dep_id=dep.id, comp_id=dep.from_component,
            )
        # TO edge — can be Component, System, or external
        if dep.to_component:
            if dep.to_component.startswith("external:"):
                ext_name = dep.to_component.replace("external:", "")
                session.run(
                    "MERGE (ext:External {id: $id}) SET ext.name = $id "
                    "WITH ext "
                    "MATCH (d:Dependency {id: $dep_id}) "
                    "MERGE (d)-[:TO]->(ext)",
                    id=ext_name, dep_id=dep.id,
                )
            elif dep.to_component.startswith("sys-"):
                session.run(
                    "MERGE (s:System {id: $sys_id}) "
                    "WITH s "
                    "MATCH (d:Dependency {id: $dep_id}) "
                    "MERGE (d)-[:TO]->(s)",
                    sys_id=dep.to_component, dep_id=dep.id,
                )
            elif dep.to_component == "kafka":
                session.run(
                    "MERGE (k:External {id: 'kafka'}) SET k.name = 'kafka' "
                    "WITH k "
                    "MATCH (d:Dependency {id: $dep_id}) "
                    "MERGE (d)-[:TO]->(k)",
                    dep_id=dep.id,
                )
            else:
                session.run(
                    "MATCH (d:Dependency {id: $dep_id}), (c:Component {id: $comp_id}) "
                    "MERGE (d)-[:TO]->(c)",
                    dep_id=dep.id, comp_id=dep.to_component,
                )


def _ingest_tasks(session: Session, version_id: str, tasks: list[Task]) -> None:
    for task in tasks:
        props = _safe_props(task, exclude={"implements", "covers", "depends_on", "meta", "status"})
        props["status"] = task.status.value
        session.run(
            "MERGE (t:Task {id: $id}) SET t += $props "
            "WITH t "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(t)",
            id=task.id, props=props, version_id=version_id,
        )
        for ref_id in task.implements:
            # Could be Component or Endpoint
            session.run(
                "MATCH (t:Task {id: $task_id}) "
                "OPTIONAL MATCH (c:Component {id: $ref_id}) "
                "OPTIONAL MATCH (ep:Endpoint {id: $ref_id}) "
                "FOREACH (_ IN CASE WHEN c IS NOT NULL THEN [1] ELSE [] END | "
                "  MERGE (t)-[:IMPLEMENTS]->(c)) "
                "FOREACH (_ IN CASE WHEN ep IS NOT NULL THEN [1] ELSE [] END | "
                "  MERGE (t)-[:IMPLEMENTS]->(ep))",
                task_id=task.id, ref_id=ref_id,
            )
        for ref_id in task.covers:
            session.run(
                "MATCH (t:Task {id: $task_id}), (br:BusinessRule {id: $rule_id}) "
                "MERGE (t)-[:COVERS]->(br)",
                task_id=task.id, rule_id=ref_id,
            )
        for dep_id in task.depends_on:
            session.run(
                "MATCH (a:Task {id: $a_id}), (b:Task {id: $b_id}) "
                "MERGE (a)-[:DEPENDS_ON]->(b)",
                a_id=task.id, b_id=dep_id,
            )


def _ingest_terms(session: Session, version_id: str, terms: list[Term]) -> None:
    for term in terms:
        props = _safe_props(term, exclude={"used_by", "meta"})
        session.run(
            "MERGE (t:Term {id: $id}) SET t += $props "
            "WITH t "
            "MATCH (v:Version {id: $version_id}) "
            "MERGE (v)-[:DEFINES]->(t)",
            id=term.id, props=props, version_id=version_id,
        )
        for ref_id in term.used_by:
            # USED_BY can reference any node type
            session.run(
                "MATCH (t:Term {id: $term_id}) "
                "OPTIONAL MATCH (n {id: $ref_id}) "
                "FOREACH (_ IN CASE WHEN n IS NOT NULL THEN [1] ELSE [] END | "
                "  MERGE (t)-[:USED_BY]->(n))",
                term_id=term.id, ref_id=ref_id,
            )


# ── Document Dispatcher ───────────────────────────────────────────────

def _ingest_document(session: Session, version_id: str, doc: ParsedDocument) -> None:
    """Ingest all nodes from a single parsed document."""
    _ingest_requirements(session, version_id, doc.requirements)
    _ingest_business_rules(session, version_id, doc.business_rules)
    _ingest_entities(session, version_id, doc.entities)
    _ingest_endpoints(session, version_id, doc.endpoints)
    _ingest_components(session, version_id, doc.components)
    _ingest_decisions(session, version_id, doc.decisions)
    _ingest_dependencies(session, version_id, doc.dependencies)
    _ingest_tasks(session, version_id, doc.tasks)
    _ingest_terms(session, version_id, doc.terms)


# ── Public API ─────────────────────────────────────────────────────────

class Neo4jIngestor:
    """Pushes a ParsedCorpus into Neo4j.

    Usage::

        ingestor = Neo4jIngestor(uri="bolt://localhost:7687", user="neo4j", password="password")
        ingestor.ingest(corpus)
        ingestor.close()
    """

    def __init__(self, uri: str, user: str, password: str) -> None:
        self._driver: Driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self) -> None:
        self._driver.close()

    def clear_all(self) -> None:
        """Delete all nodes and relationships. Use with caution."""
        with self._driver.session() as session:
            session.run("MATCH (n) DETACH DELETE n")
        logger.info("Cleared all Neo4j data")

    def ingest(self, corpus: ParsedCorpus, clear_first: bool = True) -> dict[str, int]:
        """Ingest the entire parsed corpus into Neo4j.

        Args:
            corpus: The parsed docs corpus.
            clear_first: If True, delete all existing data before ingesting.

        Returns:
            Stats dict with counts of ingested nodes per type.
        """
        stats: dict[str, int] = {}

        with self._driver.session() as session:
            if clear_first:
                self.clear_all()

            _ensure_indexes(session)

            for topic in corpus.topics:
                _ingest_topic(session, topic)

                for version_name, docs in topic.versions.items():
                    version_id = f"{topic.topic_id}/{version_name}"
                    for doc in docs:
                        _ingest_document(session, version_id, doc)

                        # Collect stats
                        for attr in (
                            "requirements", "business_rules", "entities",
                            "endpoints", "components", "decisions",
                            "dependencies", "tasks", "terms",
                        ):
                            count = len(getattr(doc, attr, []))
                            stats[attr] = stats.get(attr, 0) + count
                            # Count fields inside entities
                            if attr == "entities":
                                for entity in doc.entities:
                                    stats["fields"] = stats.get("fields", 0) + len(entity.fields)

        logger.info("Ingestion complete. Stats: %s", stats)
        return stats
