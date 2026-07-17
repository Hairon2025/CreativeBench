"""FastAPI application factory with injectable runtime dependencies."""

from typing import Protocol

from fastapi import FastAPI, HTTPException

from creativebench.api.runtime import GLMClassificationRuntime
from creativebench.api.schemas import (
    ClassificationRequest,
    ClassificationResponse,
    ReviewSubmission,
)
from creativebench.classification.model import MissingGLMAPIKeyError
from creativebench.classification.models import ClassificationRun
from creativebench.classification.service import ClassificationError
from creativebench.config import Settings, get_settings
from creativebench.database.classification_repository import (
    ClassificationReviewRepository,
)
from creativebench.database.repository import PromptRepository
from creativebench.database.session import create_database, create_session_factory
from creativebench.security.scanner import scan_prompt


class Classifier(Protocol):
    def classify(self, prompt_text: str) -> ClassificationRun: ...


def create_app(
    *,
    settings: Settings | None = None,
    classifier: Classifier | None = None,
    session_factory=None,
) -> FastAPI:
    """Create an app without requiring a configured API key."""

    resolved_settings = settings or get_settings()
    if session_factory is None:
        engine = create_database(resolved_settings.database_url)
        session_factory = create_session_factory(engine)
    resolved_classifier = classifier or GLMClassificationRuntime(resolved_settings)

    app = FastAPI(
        title="CreativeBench API",
        version="0.1.0",
        description="创意写作 Prompt 分类、审核和安全扫描 Demo",
    )

    @app.get("/health")
    def health() -> dict[str, object]:
        api_key = resolved_settings.glm_api_key
        configured = bool(
            api_key is not None and api_key.get_secret_value().strip()
        )
        return {
            "status": "ok",
            "glm_configured": configured,
            "model": resolved_settings.glm_model,
        }

    @app.post("/api/v1/security/scan")
    def security_scan(request: ClassificationRequest):
        return scan_prompt(request.prompt_text)

    @app.post(
        "/api/v1/classifications",
        response_model=ClassificationResponse,
    )
    def classify(request: ClassificationRequest) -> ClassificationResponse:
        security = scan_prompt(request.prompt_text)
        try:
            run = resolved_classifier.classify(request.prompt_text)
        except MissingGLMAPIKeyError as error:
            raise HTTPException(status_code=503, detail=str(error)) from error
        except ClassificationError as error:
            raise HTTPException(status_code=502, detail=str(error)) from error

        classification_id = None
        routed_to_review = (
            security.requires_review
            or run.prediction.confidence < resolved_settings.low_confidence_threshold
        )
        if request.prompt_id is not None:
            try:
                with session_factory.begin() as session:
                    stored = ClassificationReviewRepository(
                        session
                    ).record_classification(
                        request.prompt_id,
                        run,
                        low_confidence_threshold=(
                            resolved_settings.low_confidence_threshold
                        ),
                        force_review=security.requires_review,
                    )
                    classification_id = stored.id
                    routed_to_review = stored.review_task is not None
            except ValueError as error:
                raise HTTPException(status_code=409, detail=str(error)) from error
        return ClassificationResponse(
            run=run,
            security=security,
            classification_id=classification_id,
            routed_to_review=routed_to_review,
        )

    @app.get("/api/v1/reviews")
    def list_reviews() -> list[dict[str, object]]:
        with session_factory() as session:
            tasks = ClassificationReviewRepository(session).list_pending_reviews()
            return [
                {
                    "task_id": task.id,
                    "prompt_id": task.classification_run.prompt_id,
                    "prompt_text": task.classification_run.prompt.prompt_text,
                    "confidence": task.classification_run.confidence,
                    "prediction": task.classification_run.prediction,
                    "model_name": task.classification_run.model_name,
                }
                for task in tasks
            ]

    @app.post("/api/v1/reviews/{task_id}")
    def submit_review(task_id: int, submission: ReviewSubmission) -> dict[str, object]:
        try:
            with session_factory.begin() as session:
                task = ClassificationReviewRepository(session).complete_review(
                    task_id,
                    reviewer=submission.reviewer,
                    corrected_prediction=submission.corrected_prediction,
                    notes=submission.notes,
                )
                return {
                    "task_id": task.id,
                    "status": task.status,
                    "decision": task.classification_run.decision,
                    "reviewer": task.reviewer,
                }
        except ValueError as error:
            raise HTTPException(status_code=409, detail=str(error)) from error

    @app.get("/api/v1/stats")
    def statistics() -> dict[str, object]:
        with session_factory() as session:
            return {
                **PromptRepository(session).statistics(),
                **ClassificationReviewRepository(session).statistics(),
            }

    return app
