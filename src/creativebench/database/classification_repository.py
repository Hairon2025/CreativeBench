"""Persistence boundary for model predictions and human review."""

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from creativebench.classification.models import (
    ClassificationPrediction,
    ClassificationRun,
)
from creativebench.database.models import (
    ClassificationDecision,
    ClassificationRunORM,
    PromptORM,
    PromptStatus,
    ReviewStatus,
    ReviewTaskORM,
    utc_now,
)
from creativebench.review.models import ReviewedClassification


class ClassificationReviewRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def record_classification(
        self,
        prompt_id: str,
        run: ClassificationRun,
        *,
        low_confidence_threshold: float,
        force_review: bool = False,
    ) -> ClassificationRunORM:
        """Persist a prediction and route low-confidence results to review."""

        if not 0 <= low_confidence_threshold <= 1:
            raise ValueError("low_confidence_threshold 必须在 0 到 1 之间")

        prompt = self.session.get(PromptORM, prompt_id)
        if prompt is None:
            raise ValueError(f"Prompt 不存在：{prompt_id}")
        if prompt.status == PromptStatus.DUPLICATE:
            raise ValueError("重复 Prompt 不应再次分类")
        if prompt.status == PromptStatus.PENDING_REVIEW:
            raise ValueError("Prompt 已存在待审核任务，不能重复创建")

        requires_review = (
            force_review or run.prediction.confidence < low_confidence_threshold
        )
        classification = ClassificationRunORM(
            prompt_id=prompt_id,
            model_name=run.model_name,
            attempts=run.attempts,
            confidence=run.prediction.confidence,
            review_threshold=low_confidence_threshold,
            prediction=run.prediction.model_dump(mode="json"),
            retrieved_document_ids=run.retrieved_document_ids,
            decision=(
                ClassificationDecision.REVIEW_PENDING.value
                if requires_review
                else ClassificationDecision.AUTO_ACCEPTED.value
            ),
        )
        self.session.add(classification)

        if requires_review:
            classification.review_task = ReviewTaskORM(
                status=ReviewStatus.PENDING.value
            )
            prompt.status = PromptStatus.PENDING_REVIEW.value
        else:
            prompt.status = PromptStatus.LABELED.value

        self.session.flush()
        return classification

    def list_pending_reviews(self) -> list[ReviewTaskORM]:
        """Return pending tasks with prediction and Prompt preloaded."""

        statement = (
            select(ReviewTaskORM)
            .where(ReviewTaskORM.status == ReviewStatus.PENDING.value)
            .options(
                selectinload(ReviewTaskORM.classification_run).selectinload(
                    ClassificationRunORM.prompt
                )
            )
            .order_by(ReviewTaskORM.created_at, ReviewTaskORM.id)
        )
        return list(self.session.scalars(statement))

    def complete_review(
        self,
        review_task_id: int,
        *,
        reviewer: str,
        corrected_prediction: ClassificationPrediction | None = None,
        notes: str | None = None,
    ) -> ReviewTaskORM:
        """Approve the model output or save a corrected final prediction."""

        reviewer = reviewer.strip()
        if not reviewer:
            raise ValueError("reviewer 不能为空")

        task = self.session.get(ReviewTaskORM, review_task_id)
        if task is None:
            raise ValueError(f"审核任务不存在：{review_task_id}")
        if task.status != ReviewStatus.PENDING:
            raise ValueError("审核任务已经完成，不能重复提交")

        classification = task.classification_run
        if corrected_prediction is None:
            task.final_prediction = classification.prediction
            classification.decision = ClassificationDecision.HUMAN_APPROVED.value
        else:
            task.final_prediction = corrected_prediction.model_dump(mode="json")
            classification.decision = ClassificationDecision.HUMAN_CORRECTED.value

        task.status = ReviewStatus.COMPLETED.value
        task.reviewer = reviewer
        task.notes = notes.strip() if notes and notes.strip() else None
        task.reviewed_at = utc_now()
        classification.prompt.status = PromptStatus.LABELED.value
        self.session.flush()
        return task

    def list_reviewed_classifications(self) -> list[ReviewedClassification]:
        """Export only completed human decisions for knowledge feedback."""

        statement = (
            select(ReviewTaskORM)
            .join(ReviewTaskORM.classification_run)
            .where(
                ReviewTaskORM.status == ReviewStatus.COMPLETED.value,
                ClassificationRunORM.decision.in_(
                    [
                        ClassificationDecision.HUMAN_APPROVED.value,
                        ClassificationDecision.HUMAN_CORRECTED.value,
                    ]
                ),
            )
            .options(
                selectinload(ReviewTaskORM.classification_run).selectinload(
                    ClassificationRunORM.prompt
                )
            )
            .order_by(ReviewTaskORM.id)
        )
        reviewed: list[ReviewedClassification] = []
        for task in self.session.scalars(statement):
            run = task.classification_run
            if task.final_prediction is None or task.reviewer is None:
                raise ValueError(f"已完成审核任务数据不完整：{task.id}")
            reviewed.append(
                ReviewedClassification(
                    review_task_id=task.id,
                    classification_run_id=run.id,
                    prompt_id=run.prompt_id,
                    prompt_text=run.prompt.prompt_text,
                    reviewer=task.reviewer,
                    decision=run.decision,
                    prediction=task.final_prediction,
                )
            )
        return reviewed

    def statistics(self) -> dict[str, object]:
        """Return classification and review counts for the application dashboard."""

        from sqlalchemy import func

        run_count = (
            self.session.scalar(
                select(func.count()).select_from(ClassificationRunORM)
            )
            or 0
        )
        pending_count = (
            self.session.scalar(
                select(func.count())
                .select_from(ReviewTaskORM)
                .where(ReviewTaskORM.status == ReviewStatus.PENDING.value)
            )
            or 0
        )
        decision_rows = self.session.execute(
            select(ClassificationRunORM.decision, func.count()).group_by(
                ClassificationRunORM.decision
            )
        )
        return {
            "classification_runs": run_count,
            "pending_reviews": pending_count,
            "decision_counts": {
                decision: count for decision, count in decision_rows
            },
        }
