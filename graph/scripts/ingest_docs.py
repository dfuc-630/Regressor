import argparse
import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
import re

try:
    import yaml
except Exception:
    yaml = None

from graph.graph_client import graph


def parse_frontmatter(text: str):
    if not text.startswith("---"):
        return {}
    parts = text.split("---", 2)
    if len(parts) < 3:
        return {}
    body = parts[1]
    if yaml:
        try:
            return yaml.safe_load(body) or {}
        except Exception:
            return {}
    # Fallback: simple key: value parser
    meta = {}
    for line in body.splitlines():
        if ":" in line:
            k, v = line.split(":", 1)
            meta[k.strip()] = v.strip()
    return meta


def extract_title_and_content(text: str):
    # Find first level-1 header
    for line in text.splitlines():
        m = re.match(r"^#\s+(.*)$", line)
        if m:
            title = m.group(1).strip()
            return title, text
    # Fallback to first non-empty line
    for line in text.splitlines():
        if line.strip():
            return line.strip()[:80], text
    return "", text


def build_folder_metadata(docs_root: Path, item_path: Path):
    rel_path = item_path.relative_to(docs_root)
    parts = list(rel_path.parts)
    folder_parts = parts[:-1] if item_path.is_file() else parts
    if item_path == docs_root:
        folder_parts = []

    top_level = folder_parts[0] if folder_parts else "docs"
    parent_folder = "/".join(folder_parts[:-1]) if len(folder_parts) > 1 else ""

    return {
        "relative_path": str(rel_path),
        "folder_path": "/".join(folder_parts),
        "depth": len(folder_parts),
        "top_level": top_level,
        "parent_folder": parent_folder,
        "is_index": item_path.name == "index.md",
        "is_docs_root": item_path == docs_root,
    }


async def try_call(func, *args, **kwargs):
    if asyncio.iscoroutinefunction(func):
        return await func(*args, **kwargs)
    return func(*args, **kwargs)


def build_episode_body(title: str, metadata: dict, content: str = "") -> str:
    payload = {
        "title": title,
        "metadata": metadata,
        "content": content,
    }
    return json.dumps(payload, ensure_ascii=False, indent=2)


def build_group_id(relative_path: str) -> str:
    return re.sub(r"[^A-Za-z0-9_-]+", "_", relative_path).strip("_") or "docs"


async def ingest_docs(docs_root: Path, dry_run: bool = True, output: Path = None):
    docs_root = docs_root.resolve()
    results = []
    candidates = [
        "add_document",
        "add_episode",
        "create_episode",
        "upsert_document",
        "ingest_document",
        "ingest",
    ]

    inventory = [docs_root]
    inventory.extend(sorted(p for p in docs_root.rglob("*") if p.is_dir()))
    inventory.extend(sorted(p for p in docs_root.rglob("*.md")))

    for p in inventory:
        if p.is_dir() and p != docs_root:
            folder_meta = build_folder_metadata(docs_root, p)
            episode_body = build_episode_body(
                title=p.name,
                metadata=folder_meta,
                content=f"Folder discovered under docs: {folder_meta['relative_path']}",
            )
            if dry_run:
                print(f"Would call add_episode for folder {folder_meta['relative_path']}")
            else:
                try:
                    await graph.add_episode(
                        name=p.name,
                        episode_body=episode_body,
                        source_description=str(p.relative_to(docs_root)),
                        reference_time=datetime.now(timezone.utc),
                        group_id=build_group_id(str(p.relative_to(docs_root))),
                    )
                    print(f"Called add_episode for folder {folder_meta['relative_path']}")
                except Exception as e:
                    print(f"Method add_episode failed for folder {folder_meta['relative_path']}: {e}")
            results.append({
                "doc": folder_meta["relative_path"],
                "kind": "folder",
                "ingested": not dry_run,
                "title": p.name,
                "metadata": folder_meta,
            })
            continue

        if p.is_dir():
            folder_meta = build_folder_metadata(docs_root, p)
            results.append({
                "doc": ".",
                "kind": "docs-root",
                "ingested": False,
                "title": docs_root.name,
                "metadata": folder_meta,
            })
            continue

        rel = p.relative_to(docs_root)
        text = p.read_text(encoding="utf-8")
        fm = parse_frontmatter(text)
        title, content = extract_title_and_content(text)
        folder_meta = build_folder_metadata(docs_root, p)
        item = {
            "path": str(rel),
            "abs_path": str(p),
            "title": fm.get("title") or title,
            "metadata": {**folder_meta, **fm},
            "content": content,
        }

        ingested = False
        for name in candidates:
            if hasattr(graph, name):
                func = getattr(graph, name)
                try:
                    if dry_run:
                        print(f"Would call {name} for {rel}")
                    else:
                        if name == "add_episode":
                            await try_call(
                                func,
                                name=item["title"],
                                episode_body=build_episode_body(
                                    title=item["title"],
                                    metadata=item["metadata"],
                                    content=item["content"],
                                ),
                                source_description=str(rel),
                                reference_time=datetime.now(timezone.utc),
                                group_id=build_group_id(str(rel)),
                            )
                        else:
                            await try_call(func, item["content"], path=str(rel))
                        print(f"Called {name} for {rel}")
                    ingested = True
                    break
                except Exception as e:
                    print(f"Method {name} failed for {rel}: {e}")

        results.append({
            "doc": str(rel),
            "kind": "document",
            "ingested": ingested,
            "title": item["title"],
            "metadata": item["metadata"],
        })

    if output:
        output.parent.mkdir(parents=True, exist_ok=True)
        with output.open("w", encoding="utf-8") as fh:
            for r in results:
                fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    ingested_count = sum(1 for r in results if r["ingested"])
    print(f"Processed {len(results)} docs, {ingested_count} ingested via Graphiti API")
    if not dry_run and hasattr(graph, "close"):
        try:
            await try_call(graph.close)
        except Exception:
            pass


def cli():
    ap = argparse.ArgumentParser(description="Ingest docs into Graphiti (best-effort)")
    ap.add_argument("--root", default=".", help="Project root (default: .)")
    ap.add_argument("--docs", default="docs", help="Docs directory relative to root")
    ap.add_argument("--dry-run", action="store_true", help="Don't call Graphiti; just show actions")
    ap.add_argument("--output", default="graph/ingest/docs_ingest_result.jsonl", help="JSONL output with ingest results")
    args = ap.parse_args()

    root = Path(args.root)
    docs_dir = root / args.docs
    out = Path(args.output)

    asyncio.run(ingest_docs(docs_dir, dry_run=args.dry_run, output=out))


if __name__ == "__main__":
    cli()
