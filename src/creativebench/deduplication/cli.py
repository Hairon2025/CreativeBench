"""Command-line interface for Prompt deduplication."""

import argparse
from collections import Counter
from pathlib import Path

from creativebench.config import get_settings
from creativebench.deduplication.embeddings import (
    SentenceTransformerEmbeddingProvider,
)
from creativebench.deduplication.pipeline import (
    deduplicate,
    load_ingested_jsonl,
    write_deduplication_result,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="对已清洗 Prompt 执行分层去重")
    parser.add_argument("input", type=Path, help="creativebench-import 生成的 JSONL")
    parser.add_argument("--unique-output", type=Path, help="唯一记录输出路径")
    parser.add_argument("--report-output", type=Path, help="重复关系报告路径")
    parser.add_argument(
        "--semantic",
        action="store_true",
        help="启用本地 Embedding 语义去重",
    )
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    unique_output = args.unique_output or settings.dedup_output_path
    report_output = args.report_output or settings.dedup_report_path

    if not args.input.is_file():
        print(f"去重失败：文件不存在：{args.input}")
        return 2

    try:
        records = load_ingested_jsonl(args.input)
        provider = (
            SentenceTransformerEmbeddingProvider(settings.embedding_model)
            if args.semantic
            else None
        )
        result = deduplicate(
            records,
            near_max_distance=settings.near_duplicate_max_distance,
            semantic_provider=provider,
            semantic_threshold=settings.semantic_duplicate_threshold,
        )
    except (RuntimeError, ValueError) as error:
        print(f"去重失败：{error}")
        return 2

    write_deduplication_result(
        result,
        unique_path=unique_output,
        report_path=report_output,
    )

    method_counts = Counter(match.method for match in result.duplicates)
    print(f"输入记录数：{result.total}")
    print(f"唯一记录数：{len(result.unique_records)}")
    print(f"重复记录数：{len(result.duplicates)}")
    print(f"- 完全重复：{method_counts['exact']}")
    print(f"- 近似重复：{method_counts['near']}")
    print(f"- 语义重复：{method_counts['semantic']}")
    print(f"唯一记录输出：{unique_output}")
    print(f"重复报告输出：{report_output}")
    return 0
