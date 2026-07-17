"""Dependency-free multilabel metrics for classification ablations."""

from collections import defaultdict

from creativebench.evaluation.models import (
    DimensionMetrics,
    EvaluationCase,
    EvaluationPrediction,
    EvaluationReport,
    StrategyMetrics,
)

DIMENSIONS = ("genres", "intents", "roles", "risks")


def _safe_divide(numerator: int, denominator: int) -> float:
    return numerator / denominator if denominator else 0.0


def _dimension_metrics(tp: int, fp: int, fn: int) -> DimensionMetrics:
    precision = _safe_divide(tp, tp + fp)
    recall = _safe_divide(tp, tp + fn)
    f1 = _safe_divide(2 * precision * recall, precision + recall)
    return DimensionMetrics(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
    )


def evaluate_predictions(
    cases: list[EvaluationCase],
    predictions: list[EvaluationPrediction],
) -> EvaluationReport:
    """Compare one or more strategy outputs against the same gold cases."""

    if not cases:
        raise ValueError("评测集不能为空")
    cases_by_id = {case.id: case for case in cases}
    if len(cases_by_id) != len(cases):
        raise ValueError("评测集中存在重复 case id")

    grouped: dict[str, list[EvaluationPrediction]] = defaultdict(list)
    seen_pairs: set[tuple[str, str]] = set()
    for prediction in predictions:
        if prediction.case_id not in cases_by_id:
            raise ValueError(f"预测引用了未知 case：{prediction.case_id}")
        pair = (prediction.strategy.value, prediction.case_id)
        if pair in seen_pairs:
            raise ValueError(f"策略和 case 组合重复：{pair}")
        seen_pairs.add(pair)
        grouped[prediction.strategy.value].append(prediction)

    if not grouped:
        raise ValueError("预测结果不能为空")

    reports: list[StrategyMetrics] = []
    expected_case_ids = set(cases_by_id)
    for strategy_name, strategy_predictions in sorted(grouped.items()):
        predicted_ids = {item.case_id for item in strategy_predictions}
        if predicted_ids != expected_case_ids:
            missing = sorted(expected_case_ids - predicted_ids)
            extra = sorted(predicted_ids - expected_case_ids)
            raise ValueError(
                f"策略 {strategy_name} 未覆盖完整评测集；missing={missing}, extra={extra}"
            )

        counts = {dimension: [0, 0, 0] for dimension in DIMENSIONS}
        scope_correct = 0
        exact_correct = 0
        for item in strategy_predictions:
            expected = cases_by_id[item.case_id].expected
            actual = item.prediction
            scope_correct += actual.scope == expected.scope
            all_equal = actual.scope == expected.scope
            for dimension in DIMENSIONS:
                expected_set = set(getattr(expected, dimension))
                actual_set = set(getattr(actual, dimension))
                tp = len(expected_set & actual_set)
                fp = len(actual_set - expected_set)
                fn = len(expected_set - actual_set)
                counts[dimension][0] += tp
                counts[dimension][1] += fp
                counts[dimension][2] += fn
                all_equal = all_equal and expected_set == actual_set
            exact_correct += all_equal

        by_dimension = {
            dimension: _dimension_metrics(*values)
            for dimension, values in counts.items()
        }
        totals = [sum(values[index] for values in counts.values()) for index in range(3)]
        prompt_tokens = [item.prompt_tokens for item in strategy_predictions]
        completion_tokens = [item.completion_tokens for item in strategy_predictions]
        count = len(strategy_predictions)
        reports.append(
            StrategyMetrics(
                strategy=strategy_name,
                case_count=count,
                scope_accuracy=scope_correct / count,
                exact_match=exact_correct / count,
                micro=_dimension_metrics(*totals),
                by_dimension=by_dimension,
                average_latency_ms=(
                    sum(item.latency_ms for item in strategy_predictions) / count
                ),
                total_prompt_tokens=(
                    sum(item for item in prompt_tokens if item is not None)
                    if all(item is not None for item in prompt_tokens)
                    else None
                ),
                total_completion_tokens=(
                    sum(item for item in completion_tokens if item is not None)
                    if all(item is not None for item in completion_tokens)
                    else None
                ),
            )
        )
    return EvaluationReport(strategies=reports)
