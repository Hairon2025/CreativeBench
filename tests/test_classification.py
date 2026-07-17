import json

import pytest
from langchain_core.messages import AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.runnables import RunnableLambda
from pydantic import ValidationError

from creativebench.classification.model import MissingGLMAPIKeyError, build_glm_model
from creativebench.classification.models import ClassificationPrediction
from creativebench.classification.service import ClassificationError, ClassificationService
from creativebench.config import Settings
from creativebench.knowledge.models import KnowledgeDocumentType, KnowledgeSearchHit
from creativebench.rag.models import RetrievalBundle


def valid_prediction_json() -> str:
    return json.dumps(
        {
            "scope": "creative_writing",
            "genres": ["sci_fi"],
            "intents": ["story_continuation"],
            "roles": ["no_explicit_role"],
            "risks": ["normal"],
            "confidence": 0.91,
            "rationale": "要求续写科幻故事，无明显风险。",
        },
        ensure_ascii=False,
    )


def fake_rag_result(counter: dict[str, int]) -> RunnableLambda:
    prompt = ChatPromptTemplate.from_messages([("human", "{text}")])

    def invoke(text: str) -> dict:
        counter["rag"] += 1
        hit = KnowledgeSearchHit(
            document_id="label-genres-sci-fi",
            score=0.9,
            content="科幻文体",
            doc_type=KnowledgeDocumentType.LABEL_DEFINITION,
            metadata={"dimension": "genres"},
        )
        return {
            "context": RetrievalBundle(
                prompt_text=text,
                label_hits={
                    "genres": [hit],
                    "intents": [],
                    "roles": [],
                    "risks": [],
                },
                example_hits=[],
            ),
            "prompt": prompt.invoke({"text": text}),
        }

    return RunnableLambda(invoke)


def test_prediction_rejects_normal_mixed_with_risk() -> None:
    with pytest.raises(ValidationError, match="normal 不能与其他风险标签"):
        ClassificationPrediction.model_validate_json(
            valid_prediction_json().replace(
                '"risks": ["normal"]',
                '"risks": ["normal", "prompt_injection"]',
            )
        )


def test_retry_does_not_repeat_rag() -> None:
    counter = {"rag": 0, "model": 0}
    responses = iter([AIMessage(content="not json"), AIMessage(content=valid_prediction_json())])

    def invoke_model(_prompt):
        counter["model"] += 1
        return next(responses)

    service = ClassificationService(
        fake_rag_result(counter),
        RunnableLambda(invoke_model),
        model_name="fake-glm",
        max_attempts=3,
        retry_delay_seconds=0,
    )

    result = service.classify("请续写一个火星故事")

    assert [label.value for label in result.prediction.genres] == ["sci_fi"]
    assert result.attempts == 2
    assert result.retrieved_document_ids == ["label-genres-sci-fi"]
    assert counter == {"rag": 1, "model": 2}


def test_exhausted_parse_retries_raise_classification_error() -> None:
    counter = {"rag": 0, "model": 0}

    def invalid_model(_prompt):
        counter["model"] += 1
        return AIMessage(content="still not json")

    service = ClassificationService(
        fake_rag_result(counter),
        RunnableLambda(invalid_model),
        model_name="fake-glm",
        max_attempts=2,
        retry_delay_seconds=0,
    )

    with pytest.raises(ClassificationError, match="连续 2 次"):
        service.classify("请续写一个火星故事")

    assert counter == {"rag": 1, "model": 2}


def test_missing_api_key_fails_before_client_construction() -> None:
    settings = Settings(_env_file=None, glm_api_key=None)

    with pytest.raises(MissingGLMAPIKeyError, match="CREATIVEBENCH_GLM_API_KEY"):
        build_glm_model(settings)
