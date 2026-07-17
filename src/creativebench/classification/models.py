"""Validated input and output models for model-assisted classification."""

from typing import Self

from pydantic import Field, model_validator

from creativebench.models import (
    Genre,
    Intent,
    RiskType,
    RoleType,
    Scope,
    StrictModel,
)


class ClassificationPrediction(StrictModel):
    """The only JSON shape accepted from GLM."""

    scope: Scope
    genres: list[Genre]
    intents: list[Intent]
    roles: list[RoleType] = Field(min_length=1)
    risks: list[RiskType] = Field(min_length=1)
    confidence: float = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=500)

    @model_validator(mode="after")
    def validate_business_rules(self) -> Self:
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

        if self.scope is Scope.CREATIVE_WRITING:
            if not self.genres:
                raise ValueError("创意写作结果至少需要一个文体标签")
            if not self.intents:
                raise ValueError("创意写作结果至少需要一个创作意图标签")

        if self.scope is Scope.RISK_TEST and self.risks == [RiskType.NORMAL]:
            raise ValueError("安全测试结果不能只标记为 normal")

        return self


class ClassificationRun(StrictModel):
    """Auditable result returned by the classification application service."""

    prediction: ClassificationPrediction
    attempts: int = Field(ge=1)
    model_name: str
    retrieved_document_ids: list[str]
