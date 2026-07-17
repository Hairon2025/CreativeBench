"""Knowledge document and local vector store tests."""

from pathlib import Path

from creativebench.knowledge.builder import build_knowledge_documents
from creativebench.knowledge.feedback import (
    build_review_feedback_documents,
    merge_knowledge_documents,
)
from creativebench.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentType,
)
from creativebench.knowledge.store import QdrantKnowledgeStore
from creativebench.review.models import ReviewedClassification

ROOT = Path(__file__).resolve().parents[1]


def test_builder_creates_label_and_approved_example_documents() -> None:
    documents = build_knowledge_documents(
        ROOT / "data/taxonomy.json",
        ROOT / "data/examples/prompts.jsonl",
    )

    label_documents = [
        item for item in documents
        if item.doc_type is KnowledgeDocumentType.LABEL_DEFINITION
    ]
    example_documents = [
        item for item in documents
        if item.doc_type is KnowledgeDocumentType.APPROVED_EXAMPLE
    ]

    assert len(documents) == 36
    assert len(label_documents) == 24
    assert len(example_documents) == 12
    assert len({item.id for item in documents}) == 36
    suspense = next(item for item in documents if item.id == "label:genres:suspense")
    assert "排除条件" in suspense.content
    assert suspense.metadata["label_name"] == "悬疑"


def test_qdrant_store_rebuild_search_and_filter(tmp_path: Path) -> None:
    documents = [
        KnowledgeDocument(
            id="label:genres:sci_fi",
            content="科幻标签定义",
            doc_type=KnowledgeDocumentType.LABEL_DEFINITION,
            metadata={"dimension": "genres"},
        ),
        KnowledgeDocument(
            id="example:cbp-0001",
            content="火星故事审核样例",
            doc_type=KnowledgeDocumentType.APPROVED_EXAMPLE,
            metadata={"prompt_id": "cbp-0001"},
        ),
    ]
    store = QdrantKnowledgeStore(tmp_path / "qdrant", "test_knowledge")
    try:
        store.rebuild(documents, [[1.0, 0.0], [0.9, 0.1]])

        assert store.count() == 2
        hits = store.search(
            [1.0, 0.0],
            top_k=2,
            doc_type=KnowledgeDocumentType.LABEL_DEFINITION,
            dimension="genres",
        )
        assert len(hits) == 1
        assert hits[0].document_id == "label:genres:sci_fi"
    finally:
        store.close()


def test_review_feedback_builds_human_approved_example() -> None:
    reviewed = ReviewedClassification(
        review_task_id=7,
        classification_run_id=9,
        prompt_id="cbp-9001",
        prompt_text="请续写一个火星殖民地故事。",
        reviewer="reviewer-a",
        decision="human_corrected",
        prediction={
            "scope": "creative_writing",
            "genres": ["sci_fi"],
            "intents": ["story_continuation"],
            "roles": ["no_explicit_role"],
            "risks": ["normal"],
            "confidence": 1,
            "rationale": "人工确认是科幻续写。",
        },
    )

    documents = build_review_feedback_documents([reviewed])

    assert len(documents) == 1
    assert documents[0].id == "review-example:7"
    assert documents[0].doc_type is KnowledgeDocumentType.APPROVED_EXAMPLE
    assert documents[0].metadata["annotation_source"] == "human"
    assert documents[0].metadata["review_decision"] == "human_corrected"


def test_qdrant_feedback_upsert_is_idempotent(tmp_path: Path) -> None:
    base = KnowledgeDocument(
        id="label:genres:sci_fi",
        content="科幻标签定义",
        doc_type=KnowledgeDocumentType.LABEL_DEFINITION,
        metadata={"dimension": "genres"},
    )
    feedback = KnowledgeDocument(
        id="review-example:7",
        content="人工审核的火星故事",
        doc_type=KnowledgeDocumentType.APPROVED_EXAMPLE,
        metadata={"origin": "review_feedback"},
    )
    store = QdrantKnowledgeStore(tmp_path / "feedback-qdrant", "feedback")
    try:
        store.rebuild([base], [[1.0, 0.0]])
        store.upsert([feedback], [[0.9, 0.1]])
        store.upsert([feedback], [[0.9, 0.1]])

        assert store.count() == 2
        hits = store.search(
            [0.9, 0.1],
            top_k=2,
            doc_type=KnowledgeDocumentType.APPROVED_EXAMPLE,
        )
        assert [hit.document_id for hit in hits] == ["review-example:7"]
    finally:
        store.close()


def test_merge_knowledge_documents_rejects_id_collision() -> None:
    document = KnowledgeDocument(
        id="same-id",
        content="知识内容",
        doc_type=KnowledgeDocumentType.APPROVED_EXAMPLE,
        metadata={},
    )

    try:
        merge_knowledge_documents([document], [document])
    except ValueError as error:
        assert "ID 重复" in str(error)
    else:
        raise AssertionError("重复文档 ID 应被拒绝")
