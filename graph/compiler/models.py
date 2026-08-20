"""
Dataclass models for all 9 knowledge-type nodes parsed from /docs.

Each model maps to a Neo4j node label.  The compiler's parser produces
instances of these classes; the ingestor converts them to Cypher MERGE
statements.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


# ── Enums ──────────────────────────────────────────────────────────────

class Domain(str, Enum):
    FEATURE = "Feature"
    SYSTEM = "System"


class DocType(str, Enum):
    REQUIREMENTS = "Requirements"
    BUSINESS_RULES = "BusinessRules"
    DATA_MODELS = "DataModels"
    API_CONTRACTS = "APIContracts"
    COMPONENTS = "Components"
    DECISIONS = "Decisions"
    DEPENDENCIES = "Dependencies"
    PLAN = "Plan"
    GLOSSARY = "Glossary"


class TaskStatus(str, Enum):
    TODO = "TODO"
    DONE = "DONE"


class DecisionStatus(str, Enum):
    PROPOSED = "proposed"
    ACCEPTED = "accepted"
    DEPRECATED = "deprecated"
    SUPERSEDED = "superseded"


# ── YAML Frontmatter ──────────────────────────────────────────────────

@dataclass
class Frontmatter:
    """Parsed YAML frontmatter common to every doc file."""
    domain: Domain
    topic: str
    version: str
    doc_type: DocType
    depends_on: list[str] = field(default_factory=list)
    gitnexus_processes: list[str] = field(default_factory=list)
    last_updated: str = ""
    author: str = ""


# ── Knowledge-type Nodes ──────────────────────────────────────────────

@dataclass
class Requirement:
    """Node from 01-requirements.md"""
    id: str
    text: str
    priority: str = ""
    category: str = ""          # business | functional | non-functional | constraint
    type: str = ""              # e.g. performance, availability, technical, business
    depends_on: list[str] = field(default_factory=list)
    implements: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class BusinessRule:
    """Node from 02-business-rules.md"""
    id: str
    when_condition: str = ""
    then_action: str = ""
    reason: str = ""
    priority: str = ""
    examples: str = ""
    applies_to: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Field:
    """Sub-node belonging to an Entity, from 03-data-models.md"""
    id: str
    name: str = ""
    type: str = ""
    required: bool = False
    indexed: bool = False
    default: str = ""
    example: str = ""
    unit: str = ""
    primary_key: bool = False
    foreign_key: str = ""
    values: list[str] = field(default_factory=list)
    currency: str = ""
    value: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Entity:
    """Node from 03-data-models.md"""
    id: str
    name: str = ""
    storage: str = ""
    collection_or_table: str = ""
    symbol: str = ""
    key_pattern: str = ""
    fields: list[Field] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Endpoint:
    """Node from 04-api-contracts.md"""
    id: str
    method: str = ""
    path: str = ""
    auth: str = ""
    rate_limit: str = ""
    cache_strategy: str = ""
    symbol: str = ""
    params: list[dict[str, str]] = field(default_factory=list)
    responses: dict[str, Any] = field(default_factory=dict)
    side_effects: str = ""
    errors: list[dict[str, str]] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Component:
    """Node from 05-components.md"""
    id: str
    type: str = ""
    responsibility: str = ""
    layer: str = ""
    inputs: str = ""
    outputs: str = ""
    symbols: list[str] = field(default_factory=list)
    implements: list[str] = field(default_factory=list)
    fallback: list[str] = field(default_factory=list)
    kafka_topic: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Decision:
    """Node from 06-decisions.md (ADR-style)"""
    id: str
    title: str = ""
    context: str = ""
    decision: str = ""
    consequences: str = ""
    status: str = DecisionStatus.ACCEPTED
    date: str = ""
    impact: str = ""
    alternatives: list[dict[str, str]] = field(default_factory=list)
    affects: list[str] = field(default_factory=list)
    supersedes: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Dependency:
    """Node from 07-dependencies.md — becomes edges in Neo4j"""
    id: str
    from_component: str = ""
    to_component: str = ""
    type: str = ""               # calls | produces | consumes | triggers | http_call | database_read | cache_write
    condition: str = ""
    topic: str = ""
    timeout: str = ""
    description: str = ""
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Task:
    """Node from 08-plan.md"""
    id: str
    description: str = ""
    status: TaskStatus = TaskStatus.TODO
    assignee: str = ""
    completed_by: str = ""
    date: str = ""
    phase: str = ""
    type: str = ""               # unit_test | integration_test | (empty = implementation)
    impact_radius: str = ""
    implements: list[str] = field(default_factory=list)
    covers: list[str] = field(default_factory=list)
    depends_on: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


@dataclass
class Term:
    """Node from 09-glossary.md"""
    id: str
    name: str = ""
    definition: str = ""
    context: str = ""
    aliases: list[str] = field(default_factory=list)
    examples: str = ""
    used_by: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)


# ── Aggregate containers ──────────────────────────────────────────────

@dataclass
class ParsedDocument:
    """Result of parsing a single .md file."""
    source_path: Path
    frontmatter: Frontmatter
    requirements: list[Requirement] = field(default_factory=list)
    business_rules: list[BusinessRule] = field(default_factory=list)
    entities: list[Entity] = field(default_factory=list)
    endpoints: list[Endpoint] = field(default_factory=list)
    components: list[Component] = field(default_factory=list)
    decisions: list[Decision] = field(default_factory=list)
    dependencies: list[Dependency] = field(default_factory=list)
    tasks: list[Task] = field(default_factory=list)
    terms: list[Term] = field(default_factory=list)


@dataclass
class ParsedTopic:
    """All parsed documents for a single feature or system topic."""
    topic_id: str
    domain: Domain
    active_version: str
    versions: dict[str, list[ParsedDocument]] = field(default_factory=dict)


@dataclass
class ParsedCorpus:
    """Complete parse result of the entire /docs directory."""
    topics: list[ParsedTopic] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)