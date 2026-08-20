import os

from dotenv import load_dotenv
from graphiti_core.graphiti import Graphiti
from graphiti_core.embedder.gemini import GeminiEmbedder, GeminiEmbedderConfig
from graphiti_core.llm_client.gemini_client import GeminiClient
from graphiti_core.cross_encoder.gemini_reranker_client import GeminiRerankerClient


load_dotenv()


def build_graphiti() -> Graphiti:
    return Graphiti(
        uri=os.getenv("GRAPHITI_URI", "bolt://localhost:7687"),
        user=os.getenv("GRAPHITI_USER", "neo4j"),
        password=os.getenv("GRAPHITI_PASSWORD", "password"),
        llm_client=GeminiClient(),
        embedder=GeminiEmbedder(
            config=GeminiEmbedderConfig(
                embedding_model=os.getenv("GRAPHITI_EMBEDDING_MODEL", "gemini-embedding-001"),
            )
        ),
        cross_encoder=GeminiRerankerClient(),
    )


graph = build_graphiti()