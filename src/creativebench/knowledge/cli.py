"""Build and inspect the local knowledge base."""

import argparse
import json

from creativebench.config import get_settings
from creativebench.database.classification_repository import (
    ClassificationReviewRepository,
)
from creativebench.database.session import create_database, create_session_factory
from creativebench.deduplication.embeddings import (
    SentenceTransformerEmbeddingProvider,
)
from creativebench.knowledge.builder import (
    build_knowledge_documents,
    write_knowledge_jsonl,
)
from creativebench.knowledge.feedback import (
    build_review_feedback_documents,
    merge_knowledge_documents,
)
from creativebench.knowledge.models import KnowledgeDocumentType
from creativebench.knowledge.store import QdrantKnowledgeStore


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 CreativeBench 知识库")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("build", help="构建知识文档和向量库")
    subparsers.add_parser("feedback", help="将已完成人工审核的样本回流向量库")
    subparsers.add_parser("stats", help="查看向量库文档数量")

    search_parser = subparsers.add_parser("search", help="执行原生向量检索")
    search_parser.add_argument("query")
    search_parser.add_argument("--top-k", type=int)
    search_parser.add_argument(
        "--doc-type",
        choices=[item.value for item in KnowledgeDocumentType],
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    store = QdrantKnowledgeStore(
        settings.vector_store_path,
        settings.knowledge_collection,
    )
    try:
        if args.command == "build":
            documents = merge_knowledge_documents(
                build_knowledge_documents(
                    settings.taxonomy_path,
                    settings.examples_path,
                ),
                _load_review_feedback(settings.database_url),
            )
            write_knowledge_jsonl(documents, settings.knowledge_documents_path)
            provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
            embeddings = provider.encode([document.content for document in documents])
            store.rebuild(documents, embeddings)
            counts = {
                item.value: sum(document.doc_type is item for document in documents)
                for item in KnowledgeDocumentType
            }
            print(f"知识文档：{len(documents)}")
            print(json.dumps(counts, ensure_ascii=False, indent=2))
            print(f"向量库文档：{store.count()}")
            return 0

        if args.command == "feedback":
            documents = _load_review_feedback(settings.database_url)
            if not documents:
                print("没有可回流的人工审核样本")
                return 0
            provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
            embeddings = provider.encode([document.content for document in documents])
            store.upsert(documents, embeddings)
            print(f"审核样本回流完成：{len(documents)} 条")
            print(f"向量库文档：{store.count()}")
            return 0

        if args.command == "stats":
            print(f"向量库文档：{store.count()}")
            return 0

        provider = SentenceTransformerEmbeddingProvider(settings.embedding_model)
        query_text = f"{settings.embedding_query_instruction}{args.query}"
        query_vector = provider.encode([query_text])[0]
        doc_type = (
            KnowledgeDocumentType(args.doc_type) if args.doc_type else None
        )
        hits = store.search(
            query_vector,
            top_k=args.top_k or settings.knowledge_top_k,
            doc_type=doc_type,
        )
        for index, hit in enumerate(hits, start=1):
            print(f"[{index}] {hit.document_id} score={hit.score:.4f}")
            print(hit.content)
            print()
        return 0
    finally:
        store.close()


def _load_review_feedback(database_url: str):
    engine = create_database(database_url)
    session_factory = create_session_factory(engine)
    with session_factory() as session:
        reviewed = ClassificationReviewRepository(
            session
        ).list_reviewed_classifications()
    engine.dispose()
    return build_review_feedback_documents(reviewed)
