"""Pydantic domain models for one CreativeBench Prompt record."""

from datetime import datetime
from enum import StrEnum
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class StrictModel(BaseModel):
    """Base model that rejects unknown fields and trims string whitespace."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class Scope(StrEnum):
    CREATIVE_WRITING = "creative_writing"
    RISK_TEST = "risk_test"
    OUT_OF_SCOPE = "out_of_scope"


class SourceType(StrEnum):
    SYNTHETIC = "synthetic"
    PUBLIC_WEB = "public_web"
    INTERNAL = "internal"
    MANUAL = "manual"


class Genre(StrEnum):
    SUSPENSE = "suspense"
    ROMANCE = "romance"
    SCI_FI = "sci_fi"
    HISTORY = "history"
    FANTASY = "fantasy"
    WUXIA = "wuxia"
    REALISM = "realism"
    HORROR = "horror"


class Intent(StrEnum):
    STORY_CONTINUATION = "story_continuation"
    CHARACTER_DESIGN = "character_design"
    STYLE_IMITATION = "style_imitation"
    PLOT_GENERATION = "plot_generation"
    TEXT_REWRITING = "text_rewriting"


class RoleType(StrEnum):
    NO_EXPLICIT_ROLE = "no_explicit_role"
    MODEL_ROLE = "model_role"
    USER_ROLE = "user_role"
    MULTI_ROLE = "multi_role"
    CHARACTER_PROFILE = "character_profile"


class RiskType(StrEnum):
    NORMAL = "normal"
    PROMPT_INJECTION = "prompt_injection"
    INSTRUCTION_OVERRIDE = "instruction_override"
    ROLEPLAY_JAILBREAK = "roleplay_jailbreak"
    SENSITIVE_INDUCEMENT = "sensitive_inducement"
    PRIVACY_REQUEST = "privacy_request"


class AnnotationStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class AnnotationSource(StrEnum):
    HUMAN = "human"
    MODEL = "model"
    IMPORTED = "imported"


class PromptSource(StrictModel):
    type: SourceType
    reference: str | None


class PromptLabels(StrictModel):
    genres: list[Genre]
    intents: list[Intent]
    roles: list[RoleType] = Field(min_length=1)
    risks: list[RiskType] = Field(min_length=1)

    @model_validator(mode="after")
    def validate_label_sets(self) -> Self:
        """Reject duplicate labels and invalid normal/risk combinations."""

        dimensions = {
            "genres": self.genres,
            "intents": self.intents,
            "roles": self.roles,
            "risks": self.risks,
        }
        for name, labels in dimensions.items():
            if len(labels) != len(set(labels)):
                raise ValueError(f"{name} 中不能包含重复标签")

        if RiskType.NORMAL in self.risks and len(self.risks) > 1:
            raise ValueError("normal 不能与其他风险标签同时出现")

        return self


class Annotation(StrictModel):
    status: AnnotationStatus
    source: AnnotationSource
    confidence: float | None = Field(ge=0, le=1)
    rationale: str
    annotator: str | None

    @model_validator(mode="after")
    def validate_human_approval(self) -> Self:
        """Ensure approved human labels retain an auditable annotation."""

        if self.status is AnnotationStatus.APPROVED and self.source is AnnotationSource.HUMAN:
            if self.confidence != 1.0:
                raise ValueError("人工确认样本的 confidence 必须为 1.0")
            if not self.annotator:
                raise ValueError("人工确认样本必须记录 annotator")
        return self


class PromptRecord(StrictModel):
    schema_version: Literal["1.0"]
    id: str = Field(pattern=r"^cbp-[0-9]{4,}$")
    prompt_text: str = Field(min_length=1)
    language: str = Field(min_length=2)
    scope: Scope
    source: PromptSource
    labels: PromptLabels
    annotation: Annotation
    created_at: datetime

    @model_validator(mode="after")
    def validate_scope_and_labels(self) -> Self:
        """Apply business rules that involve both scope and labels."""

        if self.scope is Scope.CREATIVE_WRITING:
            if not self.labels.genres:
                raise ValueError("创意写作样本至少需要一个文体标签")
            if not self.labels.intents:
                raise ValueError("创意写作样本至少需要一个创作意图标签")

        if self.scope is Scope.RISK_TEST and self.labels.risks == [RiskType.NORMAL]:
            raise ValueError("安全测试样本不能只标记为 normal")

        return self
