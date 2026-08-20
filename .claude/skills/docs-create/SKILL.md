---
name: docs-create
description: "Use when: creating or updating feature and system documentation. Enforces the strict 3-Phase Safe Change & Documentation Workflow using Neo4j, Serena, GitNexus, and the scaffold script."
---

# Documentation Creation Skill

Automates the complete workflow for creating or updating feature/system documentation while enforcing the Docs-as-Database architecture.

---

## Documentation Workflow (STRICT)

You MUST follow this workflow step-by-step. Do NOT create files manually.

### 1. Scaffold the Files (MANDATORY)
Do NOT create the 9 Markdown files manually. You MUST use the scaffold script:
```bash
python3 -m graph.compiler.scaffold --domain feature --topic <feature-name> --version <version>
```
*(Change `--domain system` if it's a system).*

### 2. Write Docs
- **MUST READ:** `docs/rules/feature-system-docs.md` to understand the strict formatting.
- Open the scaffolded files and inject your findings using the `[ID] {meta}` syntax.
- Determine the Version Scope: Active version is the highest numeric folder (Max 5, at 6th trigger `10000-reset`).

### 3. Compile & Validate (MANDATORY)
Docs are treated as code. Validate your docs against the compiler:
```bash
python3 -m graph.compiler.compile --docs-dir ./docs --dry-run
```
Fix any broken links or duplicate IDs immediately.

### 4. Ingest to Neo4j
Once validation passes, push the new Knowledge Graph to Neo4j:
```bash
python3 -m graph.compiler.compile --docs-dir ./docs --neo4j-uri bolt://localhost:7687
```

---

## Important Rules

- **Source of Truth:** The Neo4j Knowledge Graph is the ultimate source of truth for business logic.
- **No Hallucinations:** Never invent rules. If the Graph is missing info, ask the user.
- **Code Alignment:** Docs must never contradict the code.
- **Line Limits:** `01-requirements.md` (200), `02-business-rules.md` (200), `08-plan.md` (200), `09-glossary.md` (100).
