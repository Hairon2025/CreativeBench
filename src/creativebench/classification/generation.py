"""Reusable model invocation, structured parsing and retry policy."""

from collections.abc import Callable
from time import sleep

from langchain_core.exceptions import OutputParserException
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.output_parsers import PydanticOutputParser
from langchain_core.runnables import Runnable
from openai import APIConnectionError, APITimeoutError, InternalServerError, RateLimitError

from creativebench.classification.models import (
    ClassificationPrediction,
    ClassificationRun,
)

RETRYABLE_MODEL_ERRORS = (
    OutputParserException,
    APIConnectionError,
    APITimeoutError,
    InternalServerError,
    RateLimitError,
)


class ClassificationError(RuntimeError):
    """Raised after all configured model attempts have failed."""


class StructuredPredictionRunner:
    """Generate one validated prediction from an already-built chat prompt."""

    def __init__(
        self,
        model: BaseChatModel | Runnable,
        *,
        model_name: str,
        max_attempts: int = 3,
        retry_delay_seconds: float = 1,
        sleep_fn: Callable[[float], None] = sleep,
    ) -> None:
        if max_attempts < 1:
            raise ValueError("max_attempts 必须至少为 1")
        self.model = model
        self.model_name = model_name
        self.max_attempts = max_attempts
        self.retry_delay_seconds = retry_delay_seconds
        self.sleep_fn = sleep_fn
        self.parser = PydanticOutputParser(pydantic_object=ClassificationPrediction)

    def generate(
        self,
        model_prompt,
        *,
        retrieved_document_ids: list[str] | None = None,
    ) -> ClassificationRun:
        last_error: Exception | None = None
        for attempt in range(1, self.max_attempts + 1):
            try:
                response = self.model.invoke(model_prompt)
                prediction = self.parser.invoke(response)
                return ClassificationRun(
                    prediction=prediction,
                    attempts=attempt,
                    model_name=self.model_name,
                    retrieved_document_ids=retrieved_document_ids or [],
                )
            except RETRYABLE_MODEL_ERRORS as error:
                last_error = error
                if attempt < self.max_attempts and self.retry_delay_seconds:
                    self.sleep_fn(self.retry_delay_seconds)
        raise ClassificationError(
            f"模型输出连续 {self.max_attempts} 次未通过校验：{last_error}"
        ) from last_error
