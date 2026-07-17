"""Convert completed human reviews into retrievable Few-shot examples."""

from creativebench.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentType,
)
from creativebench.review.models import ReviewedClassification


def build_review_feedback_documents(
    reviewed: list[ReviewedClassification],
) -> list[KnowledgeDocument]:
    """Build deterministic knowledge documents from human-reviewed results."""

    documents: list[KnowledgeDocument] = []
    for item in reviewed:
        prediction = item.prediction
        labels = {
            "genres": [label.value for label in prediction.genres],
            "intents": [label.value for label in prediction.intents],
            "roles": [label.value for label in prediction.roles],
            "risks": [label.value for label in prediction.risks],
        }

        def display(values: list[str]) -> str:
            return "、".join(values) or "无"

        documents.append(
            KnowledgeDocument(
                id=f"review-example:{item.review_task_id}",
                content="\n".join(
                    [
                        "人工审核回流 Prompt 标注样例",
                        f"Prompt：{item.prompt_text}",
                        f"样本范围：{prediction.scope.value}",
                        f"文体标签：{display(labels['genres'])}",
                        f"创作意图：{display(labels['intents'])}",
                        f"角色方式：{display(labels['roles'])}",
                        f"安全风险：{display(labels['risks'])}",
                        f"人工最终判断依据：{prediction.rationale}",
                    ]
                ),
                doc_type=KnowledgeDocumentType.APPROVED_EXAMPLE,
                metadata={
                    "prompt_id": item.prompt_id,
                    "review_task_id": item.review_task_id,
                    "classification_run_id": item.classification_run_id,
                    "scope": prediction.scope.value,
                    **labels,
                    "annotation_source": "human",
                    "review_decision": item.decision,
                    "reviewer": item.reviewer,
                    "origin": "review_feedback",
                },
            )
        )
    return documents


def merge_knowledge_documents(
    base_documents: list[KnowledgeDocument],
    feedback_documents: list[KnowledgeDocument],
) -> list[KnowledgeDocument]:
    """Merge sources while rejecting accidental document-ID collisions."""

    documents = [*base_documents, *feedback_documents]
    ids = [document.id for document in documents]
    if len(ids) != len(set(ids)):
        raise ValueError("合并后的知识文档 ID 重复")
    return documents
