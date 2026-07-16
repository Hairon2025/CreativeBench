"""Command-line entry point for validating CreativeBench data."""

import argparse
from pathlib import Path

from creativebench.config import get_settings
from creativebench.validation import validate_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="校验 CreativeBench JSONL 数据")
    parser.add_argument(
        "path",
        nargs="?",
        type=Path,
        help="待校验 JSONL 路径；默认读取配置中的 examples_path",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    path = args.path or settings.examples_path

    if not path.is_file():
        print(f"校验失败：文件不存在：{path}")
        return 2

    report = validate_jsonl(path)
    print(f"文件：{path}")
    print(f"总记录数：{report.total}")
    print(f"有效记录数：{report.valid}")
    print(f"错误记录数：{len(report.issues)}")

    for issue in report.issues:
        print(f"- 第 {issue.line_number} 行：{issue.message}")

    if report.is_valid:
        print("校验结果：通过")
        return 0

    print("校验结果：未通过")
    return 1
