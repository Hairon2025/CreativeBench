"""Convert untrusted rows into canonical, cleaned Prompt records."""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from creativebench.ingestion.cleaning import normalize_prompt_text
from creativebench.ingestion.models import (
    CleaningOperation,
    IngestedPromptRecord,
    IngestionMetadata,
    RawPromptInput,
)
from creativebench.ingestion.readers import read_raw_rows
from creativebench.models import PromptSource


@dataclass(frozen=True)
class ImportIssue:
    line_number: int
    external_id: str | None
    message: str


@dataclass
class ImportReport:
    total: int = 0
    accepted: list[IngestedPromptRecord] = field(default_factory=list)
    rejected: list[ImportIssue] = field(default_factory=list)

    @property
    def operation_counts(self) -> Counter[CleaningOperation]:
        return Counter(
            operation
            for record in self.accepted
            for operation in record.ingestion.cleaning_operations
        )


def _format_prompt_id(sequence: int) -> str:
    return f"cbp-{sequence:04d}"


def import_prompts(
    path: Path,
    *,
    start_id: int = 1001,
    min_length: int = 5,
    max_length: int = 10_000,
    imported_at: datetime | None = None,
) -> ImportReport:
    """Import all valid rows while collecting per-line rejection reasons."""

    if min_length < 1 or max_length < min_length:
        raise ValueError("Prompt 长度范围配置无效")

    imported_at = imported_at or datetime.now(UTC)
    rows, read_issues = read_raw_rows(path)
    report = ImportReport(total=len(rows) + len(read_issues))
    report.rejected.extend(
        ImportIssue(issue.line_number, None, issue.message) for issue in read_issues
    )

    for row in rows:
        external_id = row.data.get("external_id")
        external_id_text = str(external_id) if external_id is not None else None

        try:
            raw = RawPromptInput.model_validate(row.data)
        except ValidationError as error:
            report.rejected.append(
                ImportIssue(row.line_number, external_id_text, str(error))
            )
            continue

        cleaned = normalize_prompt_text(raw.prompt_text)
        cleaned_length = len(cleaned.text)
        if cleaned_length < min_length:
            report.rejected.append(
                ImportIssue(
                    row.line_number,
                    raw.external_id,
                    f"清洗后长度 {cleaned_length} 小于最小值 {min_length}",
                )
            )
            continue
        if cleaned_length > max_length:
            report.rejected.append(
                ImportIssue(
                    row.line_number,
                    raw.external_id,
                    f"清洗后长度 {cleaned_length} 超过最大值 {max_length}",
                )
            )
            continue

        record = IngestedPromptRecord(
            id=_format_prompt_id(start_id + len(report.accepted)),
            prompt_text=cleaned.text,
            language=raw.language,
            scope=raw.scope,
            source=PromptSource(type=raw.source_type, reference=raw.source_reference),
            ingestion=IngestionMetadata(
                external_id=raw.external_id,
                imported_at=imported_at,
                original_length=len(raw.prompt_text),
                cleaned_length=cleaned_length,
                cleaning_operations=cleaned.operations,
            ),
        )
        report.accepted.append(record)

    return report


def write_imported_jsonl(records: list[IngestedPromptRecord], path: Path) -> None:
    """Write accepted records as UTF-8 JSONL."""

    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        for record in records:
            file.write(record.model_dump_json())
            file.write("\n")
