"""Domain objects exported from human review for downstream knowledge use."""

from typing import Literal

from creativebench.classification.models import ClassificationPrediction
from creativebench.database.models import ClassificationDecision
from creativebench.models import StrictModel


class ReviewedClassification(StrictModel):
    """One completed human decision safe to use as an approved example."""

    review_task_id: int
    classification_run_id: int
    prompt_id: str
    prompt_text: str
    reviewer: str
    decision: Literal[
        ClassificationDecision.HUMAN_APPROVED,
        ClassificationDecision.HUMAN_CORRECTED,
    ]
    prediction: ClassificationPrediction
