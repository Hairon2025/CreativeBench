"""Schemas for gold cases, strategy predictions and metric reports."""

from enum import StrEnum
from typing import Self

from pydantic import Field, model_validator

from creativebench.classification.models import ClassificationPrediction
from creativebench.models import Genre, Intent, RiskType, RoleType, Scope, StrictModel


class EvaluationStrategy(StrEnum):
    ZERO_SHOT = "zero_shot"
    FIXED_FEW_SHOT = "fixed_few_shot"
    RAG = "rag"


class ExpectedLabels(StrictModel):
    scope: Scope
    genres: list[Genre]
    intents: list[Intent]
    roles: list[RoleType] = Field(min_length=1)
    risks: list[RiskType] = Field(min_length=1)


class EvaluationCase(StrictModel):
    id: str = Field(pattern=r"^eval-[0-9]{4,}$")
    prompt_text: str = Field(min_length=1)
    expected: ExpectedLabels
    slice: str = Field(min_length=1)


class EvaluationPrediction(StrictModel):
    case_id: str
    strategy: EvaluationStrategy
    prediction: ClassificationPrediction
    latency_ms: float = Field(ge=0)
    prompt_tokens: int | None = Field(default=None, ge=0)
    completion_tokens: int | None = Field(default=None, ge=0)


class DimensionMetrics(StrictModel):
    precision: float = Field(ge=0, le=1)
    recall: float = Field(ge=0, le=1)
    f1: float = Field(ge=0, le=1)
    true_positives: int = Field(ge=0)
    false_positives: int = Field(ge=0)
    false_negatives: int = Field(ge=0)


class StrategyMetrics(StrictModel):
    strategy: EvaluationStrategy
    case_count: int = Field(ge=1)
    scope_accuracy: float = Field(ge=0, le=1)
    exact_match: float = Field(ge=0, le=1)
    micro: DimensionMetrics
    by_dimension: dict[str, DimensionMetrics]
    average_latency_ms: float = Field(ge=0)
    total_prompt_tokens: int | None = Field(default=None, ge=0)
    total_completion_tokens: int | None = Field(default=None, ge=0)


class EvaluationReport(StrictModel):
    strategies: list[StrategyMetrics] = Field(min_length=1)

    @model_validator(mode="after")
    def strategy_names_are_unique(self) -> Self:
        names = [item.strategy for item in self.strategies]
        if len(names) != len(set(names)):
            raise ValueError("评测报告中策略不能重复")
        return self
