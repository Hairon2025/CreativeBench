"""Database initialization, loading and inspection commands."""

import argparse
import json
from pathlib import Path

from creativebench.config import get_settings
from creativebench.database.io import load_duplicate_report
from creativebench.database.repository import PromptRepository
from creativebench.database.session import create_database, create_session_factory
from creativebench.deduplication.pipeline import load_ingested_jsonl


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 CreativeBench 数据库")
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("init", help="创建当前数据库表")

    load_parser = subparsers.add_parser("load", help="写入 Prompt 和重复关系")
    load_parser.add_argument("--prompts", type=Path, required=True)
    load_parser.add_argument("--duplicates", type=Path, required=True)

    subparsers.add_parser("stats", help="查看数据库统计")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    engine = create_database(settings.database_url)
    session_factory = create_session_factory(engine)

    if args.command == "init":
        print(f"数据库初始化完成：{settings.database_url}")
        return 0

    if args.command == "load":
        if not args.prompts.is_file() or not args.duplicates.is_file():
            print("写入失败：Prompt 文件或重复报告不存在")
            return 2
        try:
            records = load_ingested_jsonl(args.prompts)
            duplicates = load_duplicate_report(args.duplicates)
            with session_factory.begin() as session:
                PromptRepository(session).synchronize_deduplication(records, duplicates)
        except ValueError as error:
            print(f"写入失败：{error}")
            return 2
        print(f"写入完成：Prompt {len(records)} 条，重复关系 {len(duplicates)} 条")
        return 0

    with session_factory() as session:
        statistics = PromptRepository(session).statistics()
    print(json.dumps(statistics, ensure_ascii=False, indent=2))
    return 0
