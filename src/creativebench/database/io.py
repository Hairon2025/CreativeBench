"""Load duplicate decisions produced by the previous pipeline step."""

from pathlib import Path

from pydantic import ValidationError

from creativebench.deduplication.models import DuplicateMatch


def load_duplicate_report(path: Path) -> list[DuplicateMatch]:
    matches: list[DuplicateMatch] = []
    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                match = DuplicateMatch.model_validate_json(line)
            except (ValidationError, ValueError) as error:
                raise ValueError(f"重复报告第 {line_number} 行无效：{error}") from error
            matches.append(match)
    return matches
