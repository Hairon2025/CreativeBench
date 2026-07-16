"""Result models for Prompt deduplication."""

from enum import StrEnum

from pydantic import Field

from creativebench.ingestion.models import IngestedPromptRecord
from creativebench.models import StrictModel


class DuplicateMethod(StrEnum):
    EXACT = "exact"
    NEAR = "near"
    SEMANTIC = "semantic"


class DuplicateMatch(StrictModel):
    duplicate_id: str
    representative_id: str
    method: DuplicateMethod
    score: float = Field(ge=0, le=1)


class DeduplicationResult(StrictModel):
    total: int = Field(ge=0)
    unique_records: list[IngestedPromptRecord]
    duplicates: list[DuplicateMatch]
