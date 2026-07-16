"""Tests for Prompt data models and the checked-in example dataset."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from creativebench.models import Genre, Intent, PromptRecord, RiskType, RoleType
from creativebench.validation import validate_jsonl

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES_PATH = ROOT / "data/examples/prompts.jsonl"
TAXONOMY_PATH = ROOT / "data/taxonomy.json"


def load_first_example() -> dict:
    first_line = EXAMPLES_PATH.read_text(encoding="utf-8").splitlines()[0]
    return json.loads(first_line)


def test_checked_in_examples_are_valid() -> None:
    report = validate_jsonl(EXAMPLES_PATH)

    assert report.is_valid
    assert report.total == 12
    assert report.valid == 12


def test_taxonomy_codes_match_python_enums() -> None:
    taxonomy = json.loads(TAXONOMY_PATH.read_text(encoding="utf-8"))
    dimensions = taxonomy["dimensions"]

    expected = {
        "genres": {item.value for item in Genre},
        "intents": {item.value for item in Intent},
        "roles": {item.value for item in RoleType},
        "risks": {item.value for item in RiskType},
    }
    actual = {
        name: {item["code"] for item in items}
        for name, items in dimensions.items()
    }

    assert actual == expected


def test_normal_risk_cannot_be_combined_with_other_risks() -> None:
    data = load_first_example()
    data["labels"]["risks"] = ["normal", "prompt_injection"]

    with pytest.raises(ValidationError, match="normal 不能与其他风险标签同时出现"):
        PromptRecord.model_validate(data)


def test_creative_writing_requires_an_intent() -> None:
    data = load_first_example()
    data["labels"]["intents"] = []

    with pytest.raises(ValidationError, match="至少需要一个创作意图标签"):
        PromptRecord.model_validate(data)
