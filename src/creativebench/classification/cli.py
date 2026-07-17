"""Command-line entry point for GLM structured classification."""

import argparse

from creativebench.classification.model import MissingGLMAPIKeyError, build_glm_model
from creativebench.classification.service import ClassificationError, ClassificationService
from creativebench.config import get_settings
from creativebench.deduplication.embeddings import SentenceTransformerEmbeddingProvider
from creativebench.knowledge.store import QdrantKnowledgeStore
from creativebench.rag.chain import build_rag_chain


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="使用 RAG + GLM 分类一个 Prompt")
    parser.add_argument("prompt_text")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()

    try:
        model = build_glm_model(settings)
    except MissingGLMAPIKeyError as error:
        print(f"分类未启动：{error}")
        return 2

    provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
    store = QdrantKnowledgeStore(
        settings.vector_store_path,
        settings.knowledge_collection,
    )
    try:
        rag_chain = build_rag_chain(
            store,
            provider,
            query_instruction=settings.embedding_query_instruction,
            label_top_k=settings.rag_label_top_k,
            example_top_k=settings.rag_example_top_k,
        )
        service = ClassificationService(
            rag_chain,
            model,
            model_name=settings.glm_model,
            max_attempts=settings.glm_max_attempts,
            retry_delay_seconds=settings.glm_retry_delay_seconds,
        )
        result = service.classify(args.prompt_text)
        print(result.model_dump_json(indent=2))
        return 0
    except ClassificationError as error:
        print(f"分类失败：{error}")
        return 1
    finally:
        store.close()
