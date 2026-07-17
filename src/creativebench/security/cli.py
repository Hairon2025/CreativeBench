"""Scan one Prompt or run the checked-in Red Team benchmark."""

import argparse

from creativebench.config import get_settings
from creativebench.security.benchmark import (
    load_security_cases,
    run_security_benchmark,
)
from creativebench.security.scanner import scan_prompt


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="CreativeBench 安全预扫描")
    subparsers = parser.add_subparsers(dest="command", required=True)
    scan = subparsers.add_parser("scan", help="扫描一个 Prompt")
    scan.add_argument("prompt_text")
    subparsers.add_parser("benchmark", help="运行 Red Team 规则基准")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.command == "scan":
        print(scan_prompt(args.prompt_text).model_dump_json(indent=2))
        return 0
    settings = get_settings()
    if not settings.security_benchmark_path.is_file():
        print(f"安全评测失败：文件不存在：{settings.security_benchmark_path}")
        return 2
    report = run_security_benchmark(
        load_security_cases(settings.security_benchmark_path)
    )
    print(report.model_dump_json(indent=2))
    return 0
