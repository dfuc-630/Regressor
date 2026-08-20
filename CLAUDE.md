# Context Discovery & Documentation Rules (Docs-as-Database)

## Discovery Order (MANDATORY)

For **every task** (design, coding, debugging, documentation, or planning), strictly follow this order:

### 1. Neo4j Knowledge Graph (`catalog.yml`) — Priority 1
The single source of truth for business logic and architecture.

**Key Queries to Use:**
- `feature_overview` / `feature_summary`
- `business_rules_for_feature`
- `impact_analysis` (Blast Radius)
- `component_details` / `component_dependencies`
- `requirement_details` / `api_contracts`
- `data_model_for_feature`
- `symbol_to_knowledge`
- `pending_tasks` / `task_history`
- `full_knowledge_dump` (when full context is needed)

**Goal:** Understand business rules, requirements ([REQ-XX]), constraints ([RULE-XX]), and impact scope.

### 2. Serena MCP + GitNexus MCP — Priority 2 & 3 (Run in Parallel)
After getting direction from Neo4j, run **Serena and GitNexus together** to gather implementation context.

**Serena** (Code Implementation & AST):
- `find_symbol`
- `find_referencing_symbols`
- `list_symbols`

**GitNexus** (Execution Flow & History):
- `context` (trace dynamic execution flow)
- `impact`
- `query` (Git history & dependencies)

**Goal:** Understand exact implementation, execution paths, side effects, and code-level blast radius.  
Repeat Serena + GitNexus as needed until no important unknowns remain.

---

## Required Context Before Writing Code

You **must** have the following before proposing or making code changes:

1. Governing requirements and business rules (from Neo4j)
2. Blast Radius / Impact Analysis (from Neo4j + GitNexus)
3. Target implementation symbols and affected components (from Neo4j + Serena)
4. Execution flow (from GitNexus if the logic is complex)

If any information is missing, continue querying instead of guessing.

---

## Repository Search Policy

**Preferred Order:**
1. Neo4j Knowledge Graph
2. Serena MCP
3. GitNexus MCP
4. Open specific files
5. grep / rg / find / ls (can combine with Serena, GitNexus for best work)

Avoid repository-wide scans when structured knowledge is available.

---

## Source of Truth

- **Neo4j Knowledge Graph** → Business Intent, Rules, Architecture (highest priority)
- **Serena + GitNexus** → Technical Implementation & Execution
- **Raw Docs** (`/docs/`) → Source data for the Graph

If conflicts arise: The code may be outdated, or the Graph needs updating. Stop and ask the user if necessary.

---

## Safe Change Workflow

### Phase 1: Context Gathering
- Loop until full context:
   1. Neo4j (`impact_analysis` + `business_rules_for_feature`)
   2. Serena + GitNexus (run in parallel)

### Phase 2 & 3: Documentation & Implementation
When creating or modifying architecture/features, you MUST execute the `docs-create` skill. Do NOT write docs or run compiler commands manually.
- Use skill: `.claude/skills/docs-create`

<!-- gitnexus:start -->
# GitNexus — Code Intelligence

This project is indexed by GitNexus as **maintain-fee-service** (2925 symbols, 4400 relationships, 64 execution flows). Use the GitNexus MCP tools to understand code, assess impact, and navigate safely.

> Index stale? Run `node .gitnexus/run.cjs analyze` from the project root — it auto-selects an available runner. No `.gitnexus/run.cjs` yet? `npx gitnexus analyze` (npm 11 crash → `npm i -g gitnexus`; #1939).

## Always Do

- **MUST run impact analysis before editing any symbol.** Before modifying a function, class, or method, run `impact({target: "symbolName", direction: "upstream"})` and report the blast radius (direct callers, affected processes, risk level) to the user.
- **MUST run `detect_changes()` before committing** to verify your changes only affect expected symbols and execution flows. For regression review, compare against the default branch: `detect_changes({scope: "compare", base_ref: "master"})`.
- **MUST warn the user** if impact analysis returns HIGH or CRITICAL risk before proceeding with edits.
- When exploring unfamiliar code, use `query({query: "concept"})` to find execution flows instead of grepping. It returns process-grouped results ranked by relevance.
- When you need full context on a specific symbol — callers, callees, which execution flows it participates in — use `context({name: "symbolName"})`.

## Never Do

- NEVER edit a function, class, or method without first running `impact` on it.
- NEVER ignore HIGH or CRITICAL risk warnings from impact analysis.
- NEVER rename symbols with find-and-replace — use `rename` which understands the call graph.
- NEVER commit changes without running `detect_changes()` to check affected scope.

## Resources

| Resource | Use for |
|----------|---------|
| `gitnexus://repo/maintain-fee-service/context` | Codebase overview, check index freshness |
| `gitnexus://repo/maintain-fee-service/clusters` | All functional areas |
| `gitnexus://repo/maintain-fee-service/processes` | All execution flows |
| `gitnexus://repo/maintain-fee-service/process/{name}` | Step-by-step execution trace |

## CLI

| Task | Read this skill file |
|------|---------------------|
| Understand architecture / "How does X work?" | `.claude/skills/gitnexus/gitnexus-exploring/SKILL.md` |
| Blast radius / "What breaks if I change X?" | `.claude/skills/gitnexus/gitnexus-impact-analysis/SKILL.md` |
| Trace bugs / "Why is X failing?" | `.claude/skills/gitnexus/gitnexus-debugging/SKILL.md` |
| Rename / extract / split / refactor | `.claude/skills/gitnexus/gitnexus-refactoring/SKILL.md` |
| Tools, resources, schema reference | `.claude/skills/gitnexus/gitnexus-guide/SKILL.md` |
| Index, status, clean, wiki CLI commands | `.claude/skills/gitnexus/gitnexus-cli/SKILL.md` |

<!-- gitnexus:end -->
