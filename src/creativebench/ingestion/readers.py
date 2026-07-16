"""Read untrusted rows from supported source file formats."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawRow:
    line_number: int
    data: dict[str, object]


@dataclass(frozen=True)
class ReadIssue:
    line_number: int
    message: str


def _read_csv(path: Path) -> tuple[list[RawRow], list[ReadIssue]]:
    rows: list[RawRow] = []
    issues: list[ReadIssue] = []

    with path.open(encoding="utf-8-sig", newline="") as file:
        reader = csv.DictReader(file)
        if reader.fieldnames is None:
            return rows, [ReadIssue(1, "CSV 缺少表头")]

        for data in reader:
            rows.append(RawRow(reader.line_num, dict(data)))

    return rows, issues


def _read_jsonl(path: Path) -> tuple[list[RawRow], list[ReadIssue]]:
    rows: list[RawRow] = []
    issues: list[ReadIssue] = []

    with path.open(encoding="utf-8-sig") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                data = json.loads(line)
            except json.JSONDecodeError as error:
                issues.append(ReadIssue(line_number, f"JSON 解析失败：{error.msg}"))
                continue

            if not isinstance(data, dict):
                issues.append(ReadIssue(line_number, "每行必须是 JSON 对象"))
                continue

            rows.append(RawRow(line_number, data))

    return rows, issues


def read_raw_rows(path: Path) -> tuple[list[RawRow], list[ReadIssue]]:
    """Read CSV or JSONL and preserve source line numbers."""

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in {".jsonl", ".ndjson"}:
        return _read_jsonl(path)
    raise ValueError(f"不支持的文件格式：{suffix or '无扩展名'}")
