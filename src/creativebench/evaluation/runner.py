"""Strategy-agnostic runner used later for live Zero/Few-shot/RAG calls."""

from collections.abc import Callable
from time import perf_counter

from creativebench.classification.models import ClassificationRun
from creativebench.evaluation.models import (
    EvaluationCase,
    EvaluationPrediction,
    EvaluationStrategy,
)

Classifier = Callable[[str], ClassificationRun]


def run_strategies(
    cases: list[EvaluationCase],
    classifiers: dict[EvaluationStrategy, Classifier],
) -> list[EvaluationPrediction]:
    """Run injectable classifiers; callers decide whether they use GLM or fakes."""

    predictions: list[EvaluationPrediction] = []
    for strategy, classifier in classifiers.items():
        for case in cases:
            started = perf_counter()
            result = classifier(case.prompt_text)
            predictions.append(
                EvaluationPrediction(
                    case_id=case.id,
                    strategy=strategy,
                    prediction=result.prediction,
                    latency_ms=(perf_counter() - started) * 1000,
                )
            )
    return predictions
