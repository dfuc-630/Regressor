"""
Main entry point for the Docs-as-Database compiler.

Parses the /docs directory, validates syntax and structure,
and pushes the knowledge graph to Neo4j.

Usage:
    python -m graph.compiler.compile --docs-dir ./docs --neo4j-uri bolt://localhost:7687
    python -m graph.compiler.compile --docs-dir ./docs --dry-run
"""

import argparse
import logging
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from .neo4j_ingestor import Neo4jIngestor
from .parser import parse_docs
from .validators import validate_corpus

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile /docs into Neo4j Knowledge Graph")
    parser.add_argument("--docs-dir", type=str, default="./docs", help="Path to /docs directory")
    parser.add_argument("--neo4j-uri", type=str, help="Neo4j URI (overrides env NEO4J_URI)")
    parser.add_argument("--neo4j-user", type=str, help="Neo4j User (overrides env NEO4J_USER)")
    parser.add_argument("--neo4j-password", type=str, help="Neo4j Password (overrides env NEO4J_PASSWORD)")
    parser.add_argument("--dry-run", action="store_true", help="Parse and validate only, do not ingest")
    parser.add_argument("--no-clear", action="store_true", help="Do not clear Neo4j before ingest")
    args = parser.parse_args()

    load_dotenv()

    docs_dir = Path(args.docs_dir).resolve()
    if not docs_dir.is_dir():
        logger.error(f"Docs directory not found: {docs_dir}")
        sys.exit(1)

    logger.info(f"Parsing docs from: {docs_dir}")
    corpus = parse_docs(docs_dir)

    logger.info("Validating corpus...")
    result = validate_corpus(corpus)
    
    if result.warnings:
        for warn in result.warnings:
            logger.warning(f"[{warn.file}] {warn.message}")

    if not result.is_valid:
        for err in result.errors:
            logger.error(f"[{err.file}] {err.message}")
        logger.error("Validation failed. Fix errors before compiling.")
        sys.exit(1)

    logger.info(result.summary())

    if args.dry_run:
        logger.info("Dry run complete. No data ingested.")
        sys.exit(0)

    # Ingestion
    uri = args.neo4j_uri or os.getenv("NEO4J_URI", "bolt://localhost:7687")
    user = args.neo4j_user or os.getenv("NEO4J_USER", "neo4j")
    password = args.neo4j_password or os.getenv("NEO4J_PASSWORD", "password")

    if not all([uri, user, password]):
        logger.error("Neo4j connection details missing. Provide via args or .env")
        sys.exit(1)

    logger.info(f"Connecting to Neo4j at {uri}...")
    ingestor = None
    try:
        ingestor = Neo4jIngestor(uri=uri, user=user, password=password)
        stats = ingestor.ingest(corpus, clear_first=not args.no_clear)
        logger.info(f"Ingested successfully: {stats}")
    except Exception as e:
        logger.error(f"Failed to ingest into Neo4j: {e}")
        sys.exit(1)
    finally:
        if ingestor:
            ingestor.close()

if __name__ == "__main__":
    main()
