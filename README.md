# Regressor

> A method for building **long-term memory** and **documentation-as-database** for AI coding agents — so every task stands on the shoulders of every task before it.

---

## Table of Contents

1. [What is Regressor?](#what-is-regressor)
2. [Core Philosophy: Docs-as-Database](#core-philosophy-docs-as-database)
3. [High-Level Architecture](#high-level-architecture)
4. [Tech Stack](#tech-stack)
5. [Lookup Order & Source of Truth](#lookup-order--source-of-truth)
6. [Operating Workflow (3 Phases)](#operating-workflow-3-phases)
7. [The Docs-as-Database System in Detail](#the-docs-as-database-system-in-detail)
8. [Python Compiler Pipeline](#python-compiler-pipeline)
9. [The `docs-create` Skill](#the-docs-create-skill)
10. [GitNexus — Code Intelligence](#gitnexus--code-intelligence)
11. [Serena — Semantic Code Toolkit](#serena--semantic-code-toolkit)
12. [Superpowers — Process Discipline](#superpowers--process-discipline)
13. [Connected MCP Servers](#connected-mcp-servers)
14. [Reference Directory Tree](#reference-directory-tree)
15. [Golden Rules](#golden-rules)
16. [Command Cheat Sheet](#command-cheat-sheet)

---

## What is Regressor?

Regressor is a method for building a **deep long-term memory system** combined with a **strict documentation system**, bringing together several proven, effective solutions to give an AI agent **full context** before it carries out any software-engineering task — design, coding, debugging, writing docs, or planning.

The name is inspired by the archetype of the manga/manhwa/manhua protagonist who has the power of **regression**: with every loop, the character returns but keeps every important and core piece of knowledge accumulated in the loops before. Applied to software engineering: every time the agent starts a new task, it **does not start from zero** — it looks back at the "memory" already built up across every previous task: business logic, architecture, design decisions, constraints, change history.

The core principle: **the longer it's used, the larger the system grows.** Every feature gets documented, every decision gets recorded, and every compile run feeds one more layer of knowledge into the graph. Context doesn't shrink with each new conversation — it **accumulates** over time, closing a self-reinforcing development loop:

> do a task → knowledge gets recorded → the graph grows richer → the agent understands more deeply → the next task gets done faster and more correctly → which feeds back into the graph again...

## Core Philosophy: Docs-as-Database

Unlike traditional documentation (free-form prose that easily drifts away from the actual code), Regressor treats **docs as structured, compilable data**, just like code:

- Every doc file must follow a fixed shape (YAML frontmatter + the `[ID] {meta} content` tag syntax).
- Docs are **parsed → validated → compiled** by a real Python compiler, not just read by eye.
- Once validation is clean, docs are **ingested as nodes/relationships in Neo4j** — turning plain text into a queryable knowledge graph.
- If a doc has broken syntax, a missing ID, or references an ID that doesn't exist, the compiler blocks ingestion outright.

As a result, the Neo4j Knowledge Graph stays a trustworthy **source of truth** for business logic — not a Confluence page that quietly goes stale without anyone noticing.

## High-Level Architecture

```text
 ┌──────────────────────────────────────────────────────────────────────┐
 │                 NEW TASK (design / code / debug / plan)               │
 └───────────────────────────────────┬────────────────────────────────────┘
                                      ▼
        ┌────────────────────────────────────────────────────┐
        │  PHASE 1 — Context Gathering                          │
        │  ① Neo4j Knowledge Graph        (Priority 1)          │
        │  ② Serena  +  GitNexus          (Priority 2 & 3,      │
        │     run in parallel)                                  │
        └────────────────────────┬─────────────────────────────┘
                                  ▼
        ┌────────────────────────────────────────────────────┐
        │  PHASE 2 — Docs-as-Database  (`docs-create` skill)    │
        │  scaffold.py → write the 9 files → compile            │
        │  --dry-run → neo4j_ingestor (MERGE into Neo4j)        │
        └────────────────────────┬─────────────────────────────┘
                                  ▼
        ┌────────────────────────────────────────────────────┐
        │  PHASE 3 — Implement & Verify                         │
        │  code matches the docs → detect_changes() → commit    │
        └────────────────────────┬─────────────────────────────┘
                                  │
                                  ▼
                 Neo4j Knowledge Graph gains one more layer
                                  │
                 ╰────────────── loop back for the next task ───────────╮
                                                                        │
                 ◄──────────────────────────────────────────────────────╯
```

The four tool blocks behind these three phases are **Neo4j**, the **9-file docs system + Python compiler**, **GitNexus & Serena**, and **Superpowers**.

## Tech Stack

| Component | Role in Regressor |
|---|---|
| **Neo4j** | The Knowledge Graph — stores Feature/System, Requirement, BusinessRule, Component, Decision, etc. as nodes/relationships, queryable via Cypher. |
| **Docs-as-Database** | A proprietary docs system: 9 standardized files per feature/system, with a scaffold flow, validation/verification, and ingestion — all driven by the Python scripts in `graph/compiler/`. |
| **GitNexus** | Code intelligence: symbol graph, execution flow, impact analysis (blast radius), call-graph-aware renames, change detection before every commit. |
| **Serena** | A semantic code toolkit over LSP: find symbols, find callers, read/edit code precisely at the AST level instead of raw text. |
| **Superpowers** | A library of process skills that must be checked before every action: brainstorming, writing-plans, TDD, systematic-debugging, etc. — enforcing engineering discipline. |
| **`docs-create` skill** | The custom skill that enforces the 3-Phase Safe Change & Documentation Workflow, wiring all of the above into a single pipeline. |

## Lookup Order & Source of Truth

Before **every** task (design/coding/debugging/docs/planning), the mandatory lookup order is:

1. **Neo4j Knowledge Graph** — business rules, requirements, impact analysis, blast radius.
2. **Serena + GitNexus** (in parallel) — the real implementation, execution flow, side effects.
3. Only open specific files, then fall back to `grep`/`rg`/`find`/`ls`, once the two steps above aren't enough.

If information is still missing: **keep querying — never guess or invent it.**

Source-of-truth hierarchy:

| Priority | Source | Answers |
|---|---|---|
| 1 | **Neo4j Knowledge Graph** | Business intent, rules, architecture |
| 2 | **Serena + GitNexus** | Technical implementation & real execution |
| 3 | **Raw docs (`/docs/`)** | The source data that feeds the graph |

If the three sources conflict: the code may be outdated, or the graph may need updating — **stop and ask the user** rather than deciding unilaterally.

## Operating Workflow (3 Phases)

### Phase 1 — Context Gathering

Before proposing or touching a single line of code, the agent must have:

- The relevant requirements & business rules (from Neo4j).
- Blast radius / impact analysis (from Neo4j + GitNexus `impact()`).
- The affected symbols & components (from Neo4j + Serena `find_symbol`).
- The execution flow, if the logic is complex (from GitNexus `context()`).

### Phase 2 — Create/Update Docs

Whenever architecture/feature docs need to be created or changed, it **must** go through the `docs-create` skill (details in section 9) — never handwritten, never freehand markdown:

1. `scaffold.py` generates the 9-file skeleton.
2. Fill it in using the required tag syntax.
3. `compile.py --dry-run` to validate.
4. `compile.py --neo4j-uri ...` to ingest for real.

### Phase 3 — Implement & Verify

- The code must match the docs just written — docs must never contradict the code.
- Run GitNexus's `detect_changes()` before committing, comparing against `master` for a regression review.
- Warn the user if impact analysis comes back HIGH/CRITICAL risk.
- Commit docs and code **together**.

By the end of Phase 3, Neo4j has gained one more layer of knowledge — the next task starts Phase 1 with a richer graph than before. That's the "regression" loop Regressor is named for.

## The Docs-as-Database System in Detail

### Two Domains

Docs live strictly under two domains:

- **`docs/features/`** — feature-level documentation.
- **`docs/systems/`** — system/infrastructure-level component documentation.

Each topic (feature/system) has version folders numbered incrementally (`00000-init`, `00001`, `00002`...). The highest-numbered folder is the single **active version**.

### The 9-File Standard

Every version folder must contain exactly these 9 files — no more, no less:

| # | File | doc_type | ID Prefix | Content | Line Limit |
|---|---|---|---|---|---|
| 1 | `01-requirements.md` | Requirements | `REQ-` | Business/functional requirements | 200 · **required** |
| 2 | `02-business-rules.md` | BusinessRules | `RULE-` | Business rules as WHEN / THEN / REASON | 200 |
| 3 | `03-data-models.md` | DataModels | `ENTITY-`, `FIELD-` | Database entities & fields | unlimited |
| 4 | `04-api-contracts.md` | APIContracts | `API-` | Endpoints, params, responses, errors | unlimited |
| 5 | `05-components.md` | Components | `COMP-` | Code components, mapped to real symbols via `MAPS_TO_SYMBOL` | unlimited · **required** |
| 6 | `06-decisions.md` | Decisions | `DEC-` | ADRs: CONTEXT / DECISION / CONSEQUENCES | unlimited |
| 7 | `07-dependencies.md` | Dependencies | `DEP-` | FROM → TO links between components/systems/externals/Kafka | unlimited |
| 8 | `08-plan.md` | Plan | `TASK-` | Implementation checklist, TODO/DONE status | 200 · **required** |
| 9 | `09-glossary.md` | Glossary | `TERM-` | Domain-specific term definitions | 100 |

Three files are **required** in every version: `01-requirements.md`, `05-components.md`, `08-plan.md` — the compiler warns if any are missing.

### YAML Frontmatter

Every `.md` file opens with a YAML block — this is how the compiler links files together:

```yaml
---
domain: Feature|System
topic: <topic-name-kebab-case>
version: "00000-init"
doc_type: Requirements|BusinessRules|DataModels|APIContracts|Components|Decisions|Dependencies|Plan|Glossary
depends_on: []
gitnexus_processes: []
last_updated: 2026-08-20
author: <agent-or-user-name>
---
```

`depends_on` links this topic to other topics in the graph; `gitnexus_processes` maps the docs to GitNexus's real execution flows.

### Structured Tag Syntax

Content inside each file uses a deterministic tag syntax the compiler can parse: `[NODE-ID] {key: value} Short description`, with sub-fields indented underneath.

```markdown
[RULE-01] {priority: high, status: active} Late payment penalty rule
  - WHEN: Payment is received after the due date
  - THEN: Apply 2% penalty on outstanding amount
  - REASON: Enforce timely payment compliance
```

```markdown
[COMP-01] {type: service} MaintenanceFeeCalculator
  - IMPLEMENTS: [REQ-01], [REQ-02]
  - MAPS_TO_SYMBOL: src/calculator.py
```

IDs must be **unique within a topic** — never duplicated, and never given a new prefix outside the fixed set: `REQ-`, `RULE-`, `ENTITY-`, `FIELD-`, `API-`, `COMP-`, `DEC-`, `DEP-`, `TASK-`, `TERM-`.

### Versioning

- A maximum of **5 versions** per topic (`00000-init` through `00004`).
- The 6th change must trigger a `10000-reset` — a version that consolidates the full state so nobody needs to read older versions to understand it.
- For incremental versions (`00001+`): **write only what changed**, add a "What Changed" section, and clearly reference the old baseline — never copy the whole thing over again.
- Marker folders like `CURRENT`/`latest`/`active` are strictly forbidden — the active version is always the highest number, by convention.

## Python Compiler Pipeline

The whole pipeline lives in `graph/compiler/`. Docs are treated as code and pass through four sequential stages:

| File | Role |
|---|---|
| `scaffold.py` | Generates the 9 standard files (with YAML frontmatter + syntax examples) for a new topic. Manual file creation is not allowed. |
| `parser.py` + `models.py` | Reads the entire `/docs` tree and parses it into a `ParsedCorpus` → `ParsedTopic` → `ParsedDocument` (dataclasses for Requirement, BusinessRule, Entity, Component, Decision, Dependency, Task, Term, etc.). |
| `validators.py` | Checks frontmatter completeness, ID uniqueness within a topic, broken references (pointing at IDs that don't exist), required files present, and line limits. `ERROR`-level issues block ingestion; `WARNING`s do not. |
| `neo4j_ingestor.py` | Pushes the validated corpus into Neo4j using **idempotent** Cypher `MERGE` statements, via the official `neo4j` driver directly — no LLM involved. By default it wipes the graph and rebuilds it (`clear_first=True`); pass `--no-clear` to keep existing data. |
| `compile.py` | The CLI orchestrator: parse → validate → (stop if `--dry-run`) → ingest into Neo4j. |

### Neo4j Node Labels

`Feature`, `System`, `Version`, `Requirement`, `BusinessRule`, `Entity`, `Field`, `Endpoint`, `Component`, `Decision`, `Dependency`, `Task`, `Term`, `Symbol`, `External` — each label is indexed on `id` for fast lookups.

### Key Relationships

| Relationship | Meaning |
|---|---|
| `HAS_VERSION` | Feature/System → Version |
| `DEFINES` | Version → every content node (Requirement, Rule, Entity, Component, ...) |
| `DEPENDS_ON` | Requirement→Requirement, BusinessRule→BusinessRule, Task→Task |
| `DEPENDS_ON_TOPIC` | Version → another topic (cross-feature/system link) |
| `APPLIES_TO` | BusinessRule → Requirement |
| `MAPS_TO_SYMBOL` | Entity/Endpoint/Component → the real code Symbol (the docs ↔ code bridge) |
| `IMPLEMENTS` | Component/Task → Requirement/Endpoint |
| `FALLBACK_TO` | Component → its fallback Component |
| `AFFECTS` / `SUPERSEDES` | Decision → Component / an older Decision |
| `FROM` / `TO` | Dependency → Component, System, External, or Kafka |
| `COVERS` | Task → BusinessRule |
| `USED_BY` | Term → any node that uses that term |

This is the "long-term memory" that Regressor queries during Phase 1 of every task.

## The `docs-create` Skill

Located at `.claude/skills/docs-create/`, made up of three files: `SKILL.md` (the workflow), `templates.md` (quick templates), `checklist.md` (the QA checklist). Alongside it sits the mandatory rule file `docs/rules/feature-system-docs.md` (`alwaysApply: true`) — the ultimate authority on formatting.

A strict 4-step workflow, with no shortcuts allowed:

1. **Scaffold first** — `python3 -m graph.compiler.scaffold --domain feature --topic <name> --version <ver>`; never hand-create the 9 files.
2. **Write the docs** — read `docs/rules/feature-system-docs.md` carefully, fill in content using the `[ID] {meta}` syntax, and determine the correct version (max 5, then `10000-reset` on the 6th change).
3. **Compile & Validate** — `python3 -m graph.compiler.compile --docs-dir ./docs --dry-run`, fixing every broken link or duplicate ID.
4. **Ingest into Neo4j** — re-run compile without `--dry-run` to push the new knowledge graph live.

The important rules that go with it: the Neo4j graph is the ultimate source of truth for business logic; **never invent a rule** — if the graph is missing information, ask the user; docs must never contradict the code.

## GitNexus — Code Intelligence

This repository is indexed by GitNexus under the name **maintain-fee-service** (2,925 symbols, 4,400 relationships, 64 execution flows). Its role: understand code, assess impact, and navigate safely — replacing eyeballing the code or blind grepping.

**Main tools:** `impact` (blast radius before editing), `context` (full context for a symbol: callers/callees/execution flows), `query` (find execution flows by concept, instead of grep), `detect_changes` (verify changes before committing, compare against `master`), `rename` (call-graph-aware renaming, safer than find-and-replace), plus `api_impact`, `cypher`, `route_map`, `shape_check`, `tool_map`, `group_list`/`group_sync`, `list_repos`.

**Mandatory rules** (which GitNexus injects into both `CLAUDE.md` and `AGENTS.md` itself):

- Always run `impact()` before editing any function/class/method.
- Always run `detect_changes()` before committing.
- Always warn the user if risk comes back HIGH/CRITICAL.
- Never rename with raw find-and-replace.
- Index gone stale? Run `node .gitnexus/run.cjs analyze` (or `npx gitnexus analyze`).

Six operational skills live at `.claude/skills/gitnexus/`: `gitnexus-exploring`, `gitnexus-impact-analysis`, `gitnexus-debugging`, `gitnexus-refactoring`, `gitnexus-guide`, `gitnexus-cli` (plus `gitnexus-pr-review` at the plugin level) — each one matches a different kind of question (architecture, blast radius, debugging, refactoring, API/schema lookup, index/CLI management).

## Serena — Semantic Code Toolkit

Serena operates on code at the **AST/LSP level** instead of raw text: `find_symbol`, `find_referencing_symbols`, `find_implementations`, `find_declaration`, `get_symbols_overview`, `search_for_pattern` for reading; `replace_symbol_body`, `insert_before_symbol`, `insert_after_symbol`, `rename_symbol`, `safe_delete_symbol` for editing exactly the right symbol, with no unintended side effects.

Serena also keeps its own memory layer, much lighter than Neo4j: `write_memory`/`read_memory`/`list_memories`, stored at `.serena/memories/` — acting as a running "notebook" across sessions for that one project, as opposed to Neo4j's fully structured, Cypher-queryable "knowledge library."

Mandatory rule: call `initial_instructions` (the Serena Instructions Manual) before starting any coding task.

## Superpowers — Process Discipline

Superpowers is a library of **process skills** — unlike knowledge skills, it dictates **how the agent behaves** before it does anything at all. The root skill, `using-superpowers`, forces the agent to check "does any skill apply here" before even asking a clarifying question.

The core process skills:

| Skill | Use when |
|---|---|
| `brainstorming` | Before any creative work — building a feature, adding new behavior |
| `writing-plans` | There's a spec/requirement for a multi-step task, before touching code |
| `executing-plans` | Executing a written plan, with review checkpoints |
| `subagent-driven-development` | Executing a plan with independent tasks in the same session |
| `dispatching-parallel-agents` | 2+ independent tasks that don't share state |
| `systematic-debugging` | A bug/test failure/unexpected behavior shows up, before proposing a fix |
| `test-driven-development` | Before writing implementation code |
| `using-git-worktrees` | Feature work needs an isolated workspace |
| `requesting-code-review` / `receiving-code-review` | Finishing a major task / receiving review feedback |
| `verification-before-completion` | Before claiming something is "done/fixed/passing" |
| `finishing-a-development-branch` | Implementation is done and all tests pass |
| `writing-skills` | Creating or editing a skill |

Superpowers isn't just theoretical here — in this repo, the output of `brainstorming` and `writing-plans` is saved for real under `docs/superpowers/specs/` and `docs/superpowers/plans/` (for example: `2026-05-15-advanced-price-caching-design.md`, `2026-05-08-vulnerability-remediation.md`). This is the **scratch zone** — where ideas get brainstormed and plans get written before implementation.

The important link back to Docs-as-Database: the specs/plans under `docs/superpowers/` are **temporary, in-flight** knowledge; once something is implemented and settled, it gets **crystallized** into the 9 official files via `docs-create`, then compiled and ingested into Neo4j to become **permanent** knowledge. Superpowers keeps discipline while the work is happening; Docs-as-Database + Neo4j keeps the result after the work is done.

## Connected MCP Servers

Configured in `.mcp.json`:

| Server | Startup Command | Role |
|---|---|---|
| `serena` | `serena start-mcp-server --project-from-cwd` | Semantic code toolkit (AST/LSP) |
| `gitnexus` | `gitnexus mcp` | Code intelligence, impact analysis, execution flow |
| `neo4j` | `python -m neo4j_mcp_server` | Reads/writes Cypher directly against the Knowledge Graph |

## Reference Directory Tree

```text
.
├── CLAUDE.md / AGENTS.md            # mandatory rules for the AI agent (discovery order, gitnexus rules)
├── .claude/skills/
│   ├── docs-create/                 # skill that enforces the docs workflow (SKILL.md, templates.md, checklist.md)
│   └── gitnexus/                    # exploring / impact-analysis / debugging / refactoring / guide / cli
├── docs/
│   ├── index.md                     # index of every documented feature & system
│   ├── explain/                     # quick-read summaries, cross-checked via GitNexus + Serena
│   ├── features/<topic>/<version>/01..09-*.md
│   ├── systems/<topic>/<version>/01..09-*.md
│   ├── rules/feature-system-docs.md # mandatory formatting rules (alwaysApply: true)
│   └── superpowers/
│       ├── specs/                   # output of the brainstorming skill
│       └── plans/                   # output of the writing-plans skill
├── graph/
│   ├── compiler/                    # scaffold.py, parser.py, models.py, validators.py,
│   │                                 # neo4j_ingestor.py, compile.py
│   ├── scripts/                     # init_graph.py, ingest_docs.py, ...
│   └── graph_client.py
└── .serena/memories/                 # Serena's lightweight, per-project memory
```

## Golden Rules

**Always:**

- Query Neo4j first, then Serena + GitNexus in parallel — following the lookup order exactly.
- Run `impact()` before editing any symbol; run `detect_changes()` before committing.
- Use `scaffold.py` to generate docs — never hand-write the 9 files.
- Run `compile --dry-run` to get a clean validation before ingesting for real.
- Keep the docs 100% in sync with the implemented code.
- Warn the user when risk comes back HIGH/CRITICAL.

**Never:**

- Invent a business rule when the graph is missing one — ask the user, don't guess.
- Create files outside the 9 standard names, or folders like `CURRENT`/`latest`/`active`.
- Introduce a new ID prefix outside the fixed list.
- Rename a symbol with raw find-and-replace.
- Commit without running `detect_changes()`, or while compile still has errors.

## Command Cheat Sheet

```bash
# Refresh the GitNexus index after significant code changes
node .gitnexus/run.cjs analyze

# Scaffold the 9 doc files for a new feature
python3 -m graph.compiler.scaffold --domain feature --topic <feature-name> --version 00000-init

# Scaffold for a system
python3 -m graph.compiler.scaffold --domain system --topic <system-name> --version 00000-init

# Validate docs (no writes to Neo4j)
python3 -m graph.compiler.compile --docs-dir ./docs --dry-run

# Ingest for real into Neo4j
python3 -m graph.compiler.compile --docs-dir ./docs --neo4j-uri bolt://localhost:7687
```

---

Regressor isn't a single tool — it's **the way these tools are wired into one loop**: every task runs through the loop once, and the knowledge graph never shrinks back down.
