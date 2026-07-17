"""Domain models for retrievable knowledge."""

from enum import StrEnum
from typing import Any

from pydantic import Field

from creativebench.models import StrictModel


class KnowledgeDocumentType(StrEnum):
    LABEL_DEFINITION = "label_definition"
    APPROVED_EXAMPLE = "approved_example"


class KnowledgeDocument(StrictModel):
    id: str
    content: str = Field(min_length=1)
    doc_type: KnowledgeDocumentType
    metadata: dict[str, Any]


class KnowledgeSearchHit(StrictModel):
    document_id: str
    content: str
    doc_type: KnowledgeDocumentType
    score: float
    metadata: dict[str, Any]
