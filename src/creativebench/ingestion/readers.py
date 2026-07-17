"""Read untrusted rows from supported source file formats."""

import csv
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class RawRow:
    """
    表示从源文件中读取的原始数据行。

    Attributes:
        line_number: 该行在源文件中的行号（从 1 开始计数）。
        data: 解析后的字典数据，键为列名（CSV）或 JSON 对象的键。
    """
    line_number: int
    data: dict[str, object]


@dataclass(frozen=True)
class ReadIssue:
    """
    表示在读取过程中遇到的非致命问题（如格式错误、解析失败等）。

    Attributes:
        line_number: 问题所在的行号。
        message: 描述问题的中文错误信息。
    """
    line_number: int
    message: str


def _read_csv(path: Path) -> tuple[list[RawRow], list[ReadIssue]]:
    """
    读取 CSV 文件，返回有效行和问题列表。

    使用 csv.DictReader 自动将首行作为表头。若文件缺少表头，则返回空行列表并记录一条问题。

    Args:
        path: CSV 文件路径。

    Returns:
        元组 (rows, issues)，其中 rows 为 RawRow 列表，issues 为 ReadIssue 列表。
    """
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
    """
    读取 JSONL（每行一个 JSON 对象）文件，返回有效行和问题列表。

    空行会被跳过，不产生问题。若某行不是合法的 JSON 或解析后不是字典对象，则记录为问题。

    Args:
        path: JSONL 文件路径。

    Returns:
        元组 (rows, issues)。
    """
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
    """
    根据文件扩展名自动选择读取方式，并返回原始数据行和读取问题。

    支持的文件格式：
        - .csv  : 逗号分隔值，首行为表头
        - .jsonl 或 .ndjson : 每行一个 JSON 对象

    Args:
        path: 文件路径。

    Returns:
        元组 (rows, issues)。

    Raises:
        ValueError: 当文件扩展名不受支持时抛出。
    """

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _read_csv(path)
    if suffix in {".jsonl", ".ndjson"}:
        return _read_jsonl(path)
    raise ValueError(f"不支持的文件格式：{suffix or '无扩展名'}")
