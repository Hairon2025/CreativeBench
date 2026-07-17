"""Low-confidence routing and human-review persistence tests."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from creativebench.classification.models import (
    ClassificationPrediction,
    ClassificationRun,
)
from creativebench.database.classification_repository import (
    ClassificationReviewRepository,
)
from creativebench.database.models import (
    ClassificationDecision,
    PromptORM,
    PromptStatus,
    ReviewStatus,
)
from creativebench.database.repository import PromptRepository
from creativebench.database.session import create_database, create_session_factory
from creativebench.ingestion.models import IngestedPromptRecord, IngestionMetadata
from creativebench.models import PromptSource, Scope, SourceType


def make_record() -> IngestedPromptRecord:
    text = "请续写一个发生在火星殖民地的故事。"
    return IngestedPromptRecord(
        id="cbp-9001",
        prompt_text=text,
        language="zh-CN",
        scope=Scope.CREATIVE_WRITING,
        source=PromptSource(type=SourceType.SYNTHETIC, reference=None),
        ingestion=IngestionMetadata(
            external_id="review-demo",
            imported_at=datetime(2026, 7, 17, tzinfo=UTC),
            original_length=len(text),
            cleaned_length=len(text),
            cleaning_operations=[],
        ),
    )


def make_run(confidence: float = 0.6) -> ClassificationRun:
    return ClassificationRun(
        prediction=ClassificationPrediction(
            scope="creative_writing",
            genres=["sci_fi"],
            intents=["story_continuation"],
            roles=["no_explicit_role"],
            risks=["normal"],
            confidence=confidence,
            rationale="火星殖民地属于科幻题材。",
        ),
        attempts=1,
        model_name="fake-glm",
        retrieved_document_ids=["label-genres-sci-fi"],
    )


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database(f"sqlite:///{tmp_path / 'review.db'}")
    factory = create_session_factory(engine)
    with factory.begin() as session:
        PromptRepository(session).synchronize_deduplication([make_record()], [])
    return factory


def test_low_confidence_creates_pending_review(session_factory) -> None:
    with session_factory.begin() as session:
        classification = ClassificationReviewRepository(session).record_classification(
            "cbp-9001",
            make_run(0.6),
            low_confidence_threshold=0.7,
        )
        task_id = classification.review_task.id

    with session_factory() as session:
        prompt = session.get(PromptORM, "cbp-9001")
        tasks = ClassificationReviewRepository(session).list_pending_reviews()
        assert prompt.status == PromptStatus.PENDING_REVIEW
        assert classification.decision == ClassificationDecision.REVIEW_PENDING
        assert [task.id for task in tasks] == [task_id]


def test_high_confidence_is_auto_accepted(session_factory) -> None:
    with session_factory.begin() as session:
        classification = ClassificationReviewRepository(session).record_classification(
            "cbp-9001",
            make_run(0.9),
            low_confidence_threshold=0.7,
        )

    with session_factory() as session:
        prompt = session.get(PromptORM, "cbp-9001")
        assert prompt.status == PromptStatus.LABELED
        assert classification.decision == ClassificationDecision.AUTO_ACCEPTED
        assert ClassificationReviewRepository(session).list_pending_reviews() == []


def test_human_can_approve_original_prediction(session_factory) -> None:
    with session_factory.begin() as session:
        repository = ClassificationReviewRepository(session)
        classification = repository.record_classification(
            "cbp-9001",
            make_run(),
            low_confidence_threshold=0.7,
        )
        task_id = classification.review_task.id

    with session_factory.begin() as session:
        task = ClassificationReviewRepository(session).complete_review(
            task_id,
            reviewer="reviewer-a",
            notes="模型判断正确",
        )

    assert task.status == ReviewStatus.COMPLETED
    assert task.classification_run.decision == ClassificationDecision.HUMAN_APPROVED
    assert task.final_prediction == task.classification_run.prediction
    assert task.classification_run.prompt.status == PromptStatus.LABELED


def test_human_correction_preserves_original_prediction(session_factory) -> None:
    with session_factory.begin() as session:
        repository = ClassificationReviewRepository(session)
        classification = repository.record_classification(
            "cbp-9001",
            make_run(),
            low_confidence_threshold=0.7,
        )
        task_id = classification.review_task.id
        original = dict(classification.prediction)

    corrected = ClassificationPrediction(
        scope="creative_writing",
        genres=["sci_fi", "suspense"],
        intents=["story_continuation"],
        roles=["no_explicit_role"],
        risks=["normal"],
        confidence=1,
        rationale="人工确认同时包含科幻和悬疑线索。",
    )
    with session_factory.begin() as session:
        task = ClassificationReviewRepository(session).complete_review(
            task_id,
            reviewer="reviewer-b",
            corrected_prediction=corrected,
        )

    assert task.classification_run.prediction == original
    assert task.final_prediction["genres"] == ["sci_fi", "suspense"]
    assert task.classification_run.decision == ClassificationDecision.HUMAN_CORRECTED


def test_completed_review_cannot_be_submitted_twice(session_factory) -> None:
    with session_factory.begin() as session:
        repository = ClassificationReviewRepository(session)
        classification = repository.record_classification(
            "cbp-9001",
            make_run(),
            low_confidence_threshold=0.7,
        )
        task_id = classification.review_task.id

    with session_factory.begin() as session:
        ClassificationReviewRepository(session).complete_review(
            task_id,
            reviewer="reviewer-a",
        )

    with pytest.raises(ValueError, match="已经完成"):
        with session_factory.begin() as session:
            ClassificationReviewRepository(session).complete_review(
                task_id,
                reviewer="reviewer-b",
            )


def test_deduplication_rerun_preserves_labeled_status(session_factory) -> None:
    with session_factory.begin() as session:
        ClassificationReviewRepository(session).record_classification(
            "cbp-9001",
            make_run(0.9),
            low_confidence_threshold=0.7,
        )

    with session_factory.begin() as session:
        PromptRepository(session).synchronize_deduplication([make_record()], [])

    with session_factory() as session:
        assert session.get(PromptORM, "cbp-9001").status == PromptStatus.LABELED


def test_only_completed_human_reviews_are_exported(session_factory) -> None:
    with session_factory.begin() as session:
        repository = ClassificationReviewRepository(session)
        low = repository.record_classification(
            "cbp-9001",
            make_run(0.6),
            low_confidence_threshold=0.7,
        )
        task_id = low.review_task.id
        repository.complete_review(task_id, reviewer="reviewer-a")

    with session_factory() as session:
        reviewed = ClassificationReviewRepository(
            session
        ).list_reviewed_classifications()

    assert len(reviewed) == 1
    assert reviewed[0].review_task_id == task_id
    assert reviewed[0].decision == ClassificationDecision.HUMAN_APPROVED
