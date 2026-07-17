from creativebench.classification.models import ClassificationPrediction
from creativebench.evaluation.metrics import evaluate_predictions
from creativebench.evaluation.models import (
    EvaluationCase,
    EvaluationPrediction,
)


def case() -> EvaluationCase:
    return EvaluationCase(
        id="eval-0001",
        prompt_text="续写火星故事",
        expected={
            "scope": "creative_writing",
            "genres": ["sci_fi"],
            "intents": ["story_continuation"],
            "roles": ["no_explicit_role"],
            "risks": ["normal"],
        },
        slice="creative",
    )


def prediction(genres: list[str]) -> ClassificationPrediction:
    return ClassificationPrediction(
        scope="creative_writing",
        genres=genres,
        intents=["story_continuation"],
        roles=["no_explicit_role"],
        risks=["normal"],
        confidence=0.9,
        rationale="测试预测",
    )


def test_perfect_prediction_has_perfect_metrics() -> None:
    report = evaluate_predictions(
        [case()],
        [
            EvaluationPrediction(
                case_id="eval-0001",
                strategy="rag",
                prediction=prediction(["sci_fi"]),
                latency_ms=120,
                prompt_tokens=100,
                completion_tokens=20,
            )
        ],
    )

    metrics = report.strategies[0]
    assert metrics.exact_match == 1
    assert metrics.micro.f1 == 1
    assert metrics.total_prompt_tokens == 100


def test_extra_label_reduces_precision_and_exact_match() -> None:
    report = evaluate_predictions(
        [case()],
        [
            EvaluationPrediction(
                case_id="eval-0001",
                strategy="zero_shot",
                prediction=prediction(["sci_fi", "suspense"]),
                latency_ms=80,
            )
        ],
    )

    metrics = report.strategies[0]
    assert metrics.exact_match == 0
    assert metrics.by_dimension["genres"].precision == 0.5


def test_incomplete_strategy_coverage_is_rejected() -> None:
    try:
        evaluate_predictions([case()], [])
    except ValueError as error:
        assert "预测结果不能为空" in str(error)
    else:
        raise AssertionError("空预测应被拒绝")
