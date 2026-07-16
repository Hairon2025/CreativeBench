"""Models used before a Prompt enters the labeling workflow."""

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from creativebench.models import PromptSource, Scope, SourceType, StrictModel


class CleaningOperation(StrEnum):
    NORMALIZED_LINE_ENDINGS = "normalized_line_endings"
    NORMALIZED_UNICODE = "normalized_unicode"
    REMOVED_INVISIBLE_CHARACTERS = "removed_invisible_characters"
    REMOVED_CONTROL_CHARACTERS = "removed_control_characters"
    NORMALIZED_WHITESPACE = "normalized_whitespace"
    TRIMMED_TEXT = "trimmed_text"


class RawPromptInput(BaseModel):
    """One untrusted row read from CSV or JSONL."""

    model_config = ConfigDict(extra="forbid")

    external_id: str = Field(min_length=1)
    prompt_text: str
    source_type: SourceType
    source_reference: str | None = None
    language: str = Field(default="zh-CN", min_length=2)
    scope: Scope = Scope.CREATIVE_WRITING

    @field_validator("external_id", "language")
    @classmethod
    def strip_identifier_fields(cls, value: str) -> str:
        return value.strip()

    @field_validator("source_reference", mode="before")
    @classmethod
    def empty_reference_to_none(cls, value: object) -> object:
        if isinstance(value, str) and not value.strip():
            return None
        return value


class IngestionMetadata(StrictModel):
    external_id: str
    imported_at: datetime
    original_length: int = Field(ge=0)
    cleaned_length: int = Field(ge=0)
    cleaning_operations: list[CleaningOperation]


class IngestedPromptRecord(StrictModel):
    """Canonical, cleaned Prompt waiting for labeling."""

    schema_version: Literal["1.0"] = "1.0"
    id: str = Field(pattern=r"^cbp-[0-9]{4,}$")
    prompt_text: str = Field(min_length=1)
    language: str = Field(min_length=2)
    scope: Scope
    source: PromptSource
    ingestion: IngestionMetadata
