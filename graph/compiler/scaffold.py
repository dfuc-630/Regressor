import os
import argparse
from datetime import datetime

# The 9-file standard definitions
DOC_FILES = [
    {
        "filename": "01-requirements.md",
        "doc_type": "Requirements",
        "example": "[REQ-01] {priority: high, status: active} Short description\n  Detailed requirement text here.",
    },
    {
        "filename": "02-business-rules.md",
        "doc_type": "BusinessRules",
        "example": "[RULE-01] {priority: high, status: active} Short description\n  - WHEN: Condition\n  - THEN: Action\n  - REASON: Rationale",
    },
    {
        "filename": "03-data-models.md",
        "doc_type": "DataModels",
        "example": "[ENTITY-01] {collection: table_name, type: document} EntityName\n  [FIELD-01] {type: string, required: true} field_name",
    },
    {
        "filename": "04-api-contracts.md",
        "doc_type": "APIContracts",
        "example": "[API-01] {method: POST, path: /api/v1/resource, auth: required} Endpoint Name\n  - PARAMS: param1 (string, required)\n  - RESPONSE_200: {success: boolean}\n  - ERRORS: RESOURCE_NOT_FOUND",
    },
    {
        "filename": "05-components.md",
        "doc_type": "Components",
        "example": "[COMP-01] {type: service} ComponentName\n  - IMPLEMENTS: [REQ-01]\n  - MAPS_TO_SYMBOL: src/component.py",
    },
    {
        "filename": "06-decisions.md",
        "doc_type": "Decisions",
        "example": "[DEC-01] {status: accepted, date: " + datetime.now().strftime("%Y-%m-%d") + "} Decision Title\n  - CONTEXT: Problem statement\n  - DECISION: What was chosen\n  - CONSEQUENCES: Trade-offs",
    },
    {
        "filename": "07-dependencies.md",
        "doc_type": "Dependencies",
        "example": "[DEP-01] {type: runtime, direction: outbound} → target-system-id\n  Reason for dependency",
    },
    {
        "filename": "08-plan.md",
        "doc_type": "Plan",
        "example": "[TASK-01] {status: TODO, assignee: Unassigned} Task Name\n  - IMPLEMENTS: [REQ-01]",
    },
    {
        "filename": "09-glossary.md",
        "doc_type": "Glossary",
        "example": "[TERM-01] {category: domain} Term Name\n  - DEFINITION: Clear definition\n  - CONTEXT: Context of usage",
    }
]

def generate_yaml_frontmatter(domain, topic, version, doc_type, author):
    date_str = datetime.now().strftime("%Y-%m-%d")
    return f"""---
domain: {domain.capitalize()}
topic: {topic}
version: "{version}"
doc_type: {doc_type}
depends_on: []
gitnexus_processes: []
last_updated: {date_str}
author: {author}
---
"""

def scaffold(domain, topic, version, author):
    # Determine base dir
    base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "docs"))
    domain_dir = "features" if domain.lower() == "feature" else "systems"
    
    target_dir = os.path.join(base_dir, domain_dir, topic, version)
    
    if os.path.exists(target_dir):
        print(f"Warning: Directory {target_dir} already exists.")
        response = input("Overwrite? (y/N): ")
        if response.lower() != 'y':
            print("Aborted.")
            return

    os.makedirs(target_dir, exist_ok=True)

    for doc in DOC_FILES:
        filepath = os.path.join(target_dir, doc["filename"])
        frontmatter = generate_yaml_frontmatter(
            domain=domain,
            topic=topic,
            version=version,
            doc_type=doc["doc_type"],
            author=author
        )
        
        content = f"{frontmatter}\n# {doc['doc_type']} for {topic}\n\n## Overview\nBrief description goes here.\n\n## Content\n\n{doc['example']}\n"
        
        with open(filepath, "w") as f:
            f.write(content)
        
        print(f"Created: {filepath}")
    
    print(f"\n✅ Scaffolded 9 files successfully in {target_dir}")
    print(f"Next steps: Edit the markdown files, then run:\n  python -m graph.compiler.compile --docs-dir ./docs --dry-run")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Scaffold Docs-as-Database Markdown Files.")
    parser.add_argument("--domain", choices=["feature", "system"], default="feature", help="Domain of the documentation (feature or system).")
    parser.add_argument("--topic", required=True, help="Kebab-case name of the feature or system (e.g., maintenance-fee-calculation).")
    parser.add_argument("--version", default="00000-init", help="Version string (e.g., 00000-init, 00001, 10000-reset).")
    parser.add_argument("--author", default="AI Agent", help="Author name to put in the YAML frontmatter.")
    
    args = parser.parse_args()
    
    scaffold(args.domain, args.topic, args.version, args.author)
