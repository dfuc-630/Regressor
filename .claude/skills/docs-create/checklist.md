# Documentation Creation Checklist

Use this checklist to ensure absolute compliance with the Docs-as-Database 3-Phase Workflow.

---

## Phase 1: Context Gathering (Absolute Accuracy)

- [ ] Did I query the **Neo4j Knowledge Graph** via `catalog.yml` first?
  - [ ] Checked `feature_overview`
  - [ ] Checked `impact_analysis` to understand the blast radius
  - [ ] Checked `business_rules_for_feature` to capture constraints
- [ ] Did I use **Serena** (`find_symbol`) to inspect code logic that the Graph missed?
- [ ] Did I use **GitNexus** (`context`) to trace dynamic execution flows if needed?
- [ ] Is my understanding 100% accurate without any hallucinations?

---

## Phase 2: Scaffold & Write Docs

- [ ] Did I determine the correct version number?
  - [ ] Maximum 5 versions per topic.
  - [ ] If changing for the 6th time, did I trigger `10000-reset`?
- [ ] Did I use the **Scaffold Script**?
  - [ ] Ran `python3 -m graph.compiler.scaffold --domain [feature/system] --topic [name] --version [ver]`
  - [ ] Did NOT create any Markdown files manually.
- [ ] When writing content into the scaffolded files:
  - [ ] Used exact deterministic tags (e.g., `[REQ-01]`, `[RULE-01]`)?
  - [ ] Ensured NO duplicate IDs within the topic?
  - [ ] Strictly followed the line limits (`01`: 200, `02`: 200, `08`: 200, `09`: 100)?
  - [ ] For incremental versions (`00001+`), only wrote what changed and kept unchanged files untouched?

---

## Phase 3: Implement & Validate

- [ ] Does the documentation perfectly align with the implemented code?
- [ ] Did I run the **Compiler Dry-Run**?
  - [ ] `python -m graph.compiler.compile --docs-dir ./docs --dry-run`
  - [ ] Did it pass with ZERO errors (no broken references, no duplicate IDs)?
- [ ] Did I commit the docs and code together?
- [ ] Did I execute the **Neo4j Ingest** to update the Knowledge Graph?
  - [ ] `python -m graph.compiler.compile --docs-dir ./docs --neo4j-uri bolt://localhost:7687`

---

## Final Sign-Off
- [ ] All checkboxes above completed.
- [ ] Ready to share with the team.
