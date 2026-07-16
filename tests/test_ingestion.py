"""Tests for raw Prompt cleaning and ingestion."""

from datetime import UTC, datetime
from pathlib import Path

from creativebench.ingestion.cleaning import normalize_prompt_text
from creativebench.ingestion.models import CleaningOperation
from creativebench.ingestion.pipeline import import_prompts

ROOT = Path(__file__).resolve().parents[1]
RAW_EXAMPLES_PATH = ROOT / "data/examples/raw_prompts.csv"


def test_normalize_prompt_text_records_changes() -> None:
    result = normalize_prompt_text("  ＡＩ\u200b  写作\r\n\r\n\r\n测试  ")

    assert result.text == "AI 写作\n\n测试"
    assert CleaningOperation.NORMALIZED_LINE_ENDINGS in result.operations
    assert CleaningOperation.NORMALIZED_UNICODE in result.operations
    assert CleaningOperation.REMOVED_INVISIBLE_CHARACTERS in result.operations
    assert CleaningOperation.NORMALIZED_WHITESPACE in result.operations
    assert CleaningOperation.TRIMMED_TEXT in result.operations


def test_normalize_prompt_text_preserves_chinese_punctuation() -> None:
    result = normalize_prompt_text("中文逗号，中文冒号：保持原样。")

    assert result.text == "中文逗号，中文冒号：保持原样。"
    assert CleaningOperation.NORMALIZED_UNICODE not in result.operations


def test_example_csv_is_imported() -> None:
    imported_at = datetime(2026, 7, 16, tzinfo=UTC)
    report = import_prompts(RAW_EXAMPLES_PATH, start_id=2001, imported_at=imported_at)

    assert report.total == 6
    assert len(report.accepted) == 6
    assert not report.rejected
    assert report.accepted[0].id == "cbp-2001"
    assert report.accepted[-1].id == "cbp-2006"
    assert report.accepted[0].ingestion.imported_at == imported_at


def test_invalid_rows_are_rejected_without_stopping_file(tmp_path: Path) -> None:
    source = tmp_path / "raw.jsonl"
    source.write_text(
        "\n".join(
            [
                '{"external_id":"ok","prompt_text":"请写一个科幻故事","source_type":"manual"}',
                '{"external_id":"bad","prompt_text":"  ","source_type":"manual"}',
                '{"external_id":"broken"',
            ]
        ),
        encoding="utf-8",
    )

    report = import_prompts(source)

    assert report.total == 3
    assert len(report.accepted) == 1
    assert len(report.rejected) == 2
    assert {issue.line_number for issue in report.rejected} == {2, 3}
