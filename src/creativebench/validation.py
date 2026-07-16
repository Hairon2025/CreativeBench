"""Read and validate line-delimited Prompt records."""

from dataclasses import dataclass, field
from pathlib import Path

from pydantic import ValidationError

from creativebench.models import PromptRecord


@dataclass(frozen=True)
class ValidationIssue:
    line_number: int
    message: str


@dataclass
class ValidationReport:
    total: int = 0
    valid: int = 0
    records: list[PromptRecord] = field(default_factory=list)
    issues: list[ValidationIssue] = field(default_factory=list)

    @property
    def is_valid(self) -> bool:
        return not self.issues


def validate_jsonl(path: Path) -> ValidationReport:
    """Validate every non-empty line and report all errors at once."""

    report = ValidationReport()
    seen_ids: set[str] = set()

    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue

            report.total += 1
            try:
                record = PromptRecord.model_validate_json(line)
            except (ValidationError, ValueError) as error:
                report.issues.append(ValidationIssue(line_number, str(error)))
                continue

            if record.id in seen_ids:
                report.issues.append(
                    ValidationIssue(line_number, f"Prompt ID 重复：{record.id}")
                )
                continue

            seen_ids.add(record.id)
            report.valid += 1
            report.records.append(record)

    return report
