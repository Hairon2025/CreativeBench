"""Inspect LangChain retrieval context and generated model messages."""

import argparse

from creativebench.config import get_settings
from creativebench.deduplication.embeddings import (
    SentenceTransformerEmbeddingProvider,
)
from creativebench.knowledge.store import QdrantKnowledgeStore
from creativebench.rag.chain import LABEL_DIMENSIONS, build_rag_chain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="生成 CreativeBench RAG 分类上下文")
    parser.add_argument("prompt_text")
    parser.add_argument(
        "--show",
        choices=["context", "prompt", "all"],
        default="all",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
    store = QdrantKnowledgeStore(
        settings.vector_store_path,
        settings.knowledge_collection,
    )
    try:
        chain = build_rag_chain(
            store,
            provider,
            query_instruction=settings.embedding_query_instruction,
            label_top_k=settings.rag_label_top_k,
            example_top_k=settings.rag_example_top_k,
        )
        result = chain.invoke(args.prompt_text)

        if args.show in {"context", "all"}:
            context = result["context"]
            print("=== RETRIEVAL CONTEXT ===")
            for dimension in LABEL_DIMENSIONS:
                ids = [hit.document_id for hit in context.label_hits[dimension]]
                print(f"{dimension}: {ids}")
            print(
                "examples:",
                [hit.document_id for hit in context.example_hits],
            )

        if args.show in {"prompt", "all"}:
            print("\n=== MODEL MESSAGES ===")
            for message in result["prompt"].to_messages():
                print(f"--- {message.type.upper()} ---")
                print(message.content)
        return 0
    finally:
        store.close()
