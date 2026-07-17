"""HTTP request and response schemas."""

from pydantic import Field

from creativebench.classification.models import (
    ClassificationPrediction,
    ClassificationRun,
)
from creativebench.models import StrictModel
from creativebench.security.models import SecurityFinding


class ClassificationRequest(StrictModel):
    prompt_text: str = Field(min_length=1, max_length=10_000)
    prompt_id: str | None = Field(default=None, pattern=r"^cbp-[0-9]{4,}$")


class ClassificationResponse(StrictModel):
    run: ClassificationRun
    security: SecurityFinding
    classification_id: int | None
    routed_to_review: bool


class ReviewSubmission(StrictModel):
    reviewer: str = Field(min_length=1, max_length=128)
    notes: str | None = Field(default=None, max_length=2_000)
    corrected_prediction: ClassificationPrediction | None = None
