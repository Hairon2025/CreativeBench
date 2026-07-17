"""JSONL readers for reproducible offline evaluation."""

from pathlib import Path
from typing import TypeVar

from pydantic import BaseModel

from creativebench.evaluation.models import EvaluationCase, EvaluationPrediction

ModelT = TypeVar("ModelT", bound=BaseModel)


def _load_jsonl(path: Path, model_type: type[ModelT]) -> list[ModelT]:
    records: list[ModelT] = []
    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                records.append(model_type.model_validate_json(line))
            except ValueError as error:
                raise ValueError(f"{path} 第 {line_number} 行无效：{error}") from error
    return records


def load_evaluation_cases(path: Path) -> list[EvaluationCase]:
    return _load_jsonl(path, EvaluationCase)


def load_evaluation_predictions(path: Path) -> list[EvaluationPrediction]:
    return _load_jsonl(path, EvaluationPrediction)
