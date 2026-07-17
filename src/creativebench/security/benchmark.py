"""Evaluate deterministic security rules on a checked-in Red Team set."""

from pathlib import Path

from creativebench.security.models import SecurityBenchmarkReport, SecurityCase
from creativebench.security.scanner import scan_prompt


def load_security_cases(path: Path) -> list[SecurityCase]:
    cases: list[SecurityCase] = []
    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                cases.append(SecurityCase.model_validate_json(line))
            except ValueError as error:
                raise ValueError(f"安全用例第 {line_number} 行无效：{error}") from error
    return cases


def run_security_benchmark(cases: list[SecurityCase]) -> SecurityBenchmarkReport:
    if not cases:
        raise ValueError("安全评测集不能为空")
    tp = fp = fn = exact = 0
    false_negative_ids: list[str] = []
    for case in cases:
        expected = set(case.expected_risks)
        actual = set(scan_prompt(case.prompt_text).risks)
        tp += len(expected & actual)
        fp += len(actual - expected)
        fn += len(expected - actual)
        exact += actual == expected
        if expected - actual:
            false_negative_ids.append(case.id)
    precision = tp / (tp + fp) if tp + fp else 0
    recall = tp / (tp + fn) if tp + fn else 0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
    return SecurityBenchmarkReport(
        case_count=len(cases),
        exact_match=exact / len(cases),
        precision=precision,
        recall=recall,
        f1=f1,
        false_negative_case_ids=false_negative_ids,
    )
