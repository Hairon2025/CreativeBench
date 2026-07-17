"""Application service combining one RAG run with retryable model parsing."""

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.runnables import Runnable

from creativebench.classification.generation import (
    ClassificationError,
    StructuredPredictionRunner,
)
from creativebench.classification.models import ClassificationRun
from creativebench.rag.models import RetrievalBundle

__all__ = ["ClassificationError", "ClassificationService"]


class ClassificationService:
    """Run retrieval once, then retry only model generation and parsing."""

    def __init__(
        self,
        rag_chain: Runnable,
        model: BaseChatModel | Runnable,
        *,
        model_name: str,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1,
        sleep_fn=None,
    ) -> None:
        self.rag_chain = rag_chain
        runner_kwargs = {
            "model_name": model_name,
            "max_attempts": max_attempts,
            "retry_delay_seconds": retry_delay_seconds,
        }
        if sleep_fn is not None:
            runner_kwargs["sleep_fn"] = sleep_fn
        self.runner = StructuredPredictionRunner(model, **runner_kwargs)

    def classify(self, prompt_text: str) -> ClassificationRun:
        """Classify one Prompt and return a validated, auditable result."""

        rag_result = self.rag_chain.invoke(prompt_text)
        context: RetrievalBundle = rag_result["context"]
        return self.runner.generate(
            rag_result["prompt"],
            retrieved_document_ids=_document_ids(context),
        )


def _document_ids(context: RetrievalBundle) -> list[str]:
    ids = [
        hit.document_id
        for dimension_hits in context.label_hits.values()
        for hit in dimension_hits
    ]
    ids.extend(hit.document_id for hit in context.example_hits)
    return list(dict.fromkeys(ids))
