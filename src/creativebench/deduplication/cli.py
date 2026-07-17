"""Prompt 去重的命令行接口。"""

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
    """构造并配置 CLI 的参数解析器。

    返回:
        配置好的 ArgumentParser 实例。
    """
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
    """CLI 入口函数。

    流程:解析参数 -> 读取配置 -> 校验输入文件 -> 加载数据 ->
    (可选)构建语义提供者 -> 执行去重 -> 写入结果 -> 输出汇总。

    返回:
        进程退出码:0 表示成功,2 表示失败。
    """
    # 解析命令行参数并加载项目全局配置
    args = build_parser().parse_args()
    settings = get_settings()
    # 命令行参数优先,缺省时回退到配置中的默认路径
    unique_output = args.unique_output or settings.dedup_output_path
    report_output = args.report_output or settings.dedup_report_path

    # 输入文件必须存在,否则直接以退出码 2 结束
    if not args.input.is_file():
        print(f"去重失败：文件不存在：{args.input}")
        return 2

    try:
        # 加载已导入的 JSONL 数据
        records = load_ingested_jsonl(args.input)
        # 仅在启用 --semantic 时才实例化 Embedding 提供者,避免不必要的依赖加载
        provider = (
            SentenceTransformerEmbeddingProvider(settings.embedding_model)
            if args.semantic
            else None
        )
        # 调用去重管道,阈值由配置注入
        result = deduplicate(
            records,
            near_max_distance=settings.near_duplicate_max_distance,
            semantic_provider=provider,
            semantic_threshold=settings.semantic_duplicate_threshold,
        )
    except (RuntimeError, ValueError) as error:
        # 已知异常(运行时错误或参数错误)统一以退出码 2 报告
        print(f"去重失败：{error}")
        return 2

    # 将唯一记录与重复报告分别写入指定路径
    write_deduplication_result(
        result,
        unique_path=unique_output,
        report_path=report_output,
    )

    # 统计各去重方法的命中次数,便于用户在终端快速查看分布
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