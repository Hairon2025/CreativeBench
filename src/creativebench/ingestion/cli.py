"""Command-line interface for importing raw Prompt data."""

import argparse
from pathlib import Path

from creativebench.config import get_settings
from creativebench.ingestion.pipeline import import_prompts, write_imported_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="导入并清洗原始 Prompt 数据")
    parser.add_argument("input", type=Path, help="CSV、JSONL 或 NDJSON 原始数据")
    parser.add_argument("--output", type=Path, help="清洗后 JSONL 输出路径")
    parser.add_argument("--start-id", type=int, default=1001, help="内部 ID 起始序号")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    output = args.output or settings.import_output_path

    if not args.input.is_file():
        print(f"导入失败：文件不存在：{args.input}")
        return 2

    try:
        report = import_prompts(
            args.input,
            start_id=args.start_id,
            min_length=settings.min_prompt_length,
            max_length=settings.max_prompt_length,
        )
    except ValueError as error:
        print(f"导入失败：{error}")
        return 2

    write_imported_jsonl(report.accepted, output)

    print(f"输入文件：{args.input}")
    print(f"输出文件：{output}")
    print(f"总记录数：{report.total}")
    print(f"接收记录数：{len(report.accepted)}")
    print(f"拒绝记录数：{len(report.rejected)}")

    for operation, count in sorted(
        report.operation_counts.items(), key=lambda item: item[0].value
    ):
        print(f"- 清洗操作 {operation.value}：{count}")

    for issue in report.rejected:
        identifier = issue.external_id or "未知 ID"
        print(f"- 第 {issue.line_number} 行（{identifier}）：{issue.message}")

    if report.rejected:
        print("导入结果：部分记录未通过")
        return 1

    print("导入结果：通过")
    return 0
