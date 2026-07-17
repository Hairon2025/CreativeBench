"""Score saved strategy predictions without calling a model."""

import argparse
from pathlib import Path

from creativebench.classification.model import MissingGLMAPIKeyError
from creativebench.config import get_settings
from creativebench.evaluation.io import (
    load_evaluation_cases,
    load_evaluation_predictions,
)
from creativebench.evaluation.live import run_live_ablation
from creativebench.evaluation.metrics import evaluate_predictions


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="运行或计算 CreativeBench 离线评测")
    subparsers = parser.add_subparsers(dest="command", required=True)
    score = subparsers.add_parser("score", help="计算已有预测文件的指标")
    score.add_argument("--cases", type=Path)
    score.add_argument("--predictions", type=Path)
    score.add_argument("--output", type=Path)
    run = subparsers.add_parser("run", help="真实运行三种 GLM 分类策略")
    run.add_argument("--cases", type=Path)
    run.add_argument("--predictions", type=Path)
    run.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    cases_path = args.cases or settings.evaluation_cases_path
    predictions_path = args.predictions or settings.evaluation_predictions_path
    output_path = args.output or settings.evaluation_report_path
    if not cases_path.is_file():
        print("评测失败：cases 文件不存在")
        return 2
    if args.command == "run":
        try:
            predictions = run_live_ablation(
                settings,
                load_evaluation_cases(cases_path),
            )
        except MissingGLMAPIKeyError as error:
            print(f"评测未启动：{error}")
            return 2
        predictions_path.parent.mkdir(parents=True, exist_ok=True)
        predictions_path.write_text(
            "".join(item.model_dump_json() + "\n" for item in predictions),
            encoding="utf-8",
        )
    elif not predictions_path.is_file():
        print("评测失败：predictions 文件不存在")
        return 2
    try:
        report = evaluate_predictions(
            load_evaluation_cases(cases_path),
            load_evaluation_predictions(predictions_path),
        )
    except ValueError as error:
        print(f"评测失败：{error}")
        return 2
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2), encoding="utf-8")
    for metrics in report.strategies:
        print(
            f"{metrics.strategy.value}: exact={metrics.exact_match:.3f} "
            f"micro_f1={metrics.micro.f1:.3f} "
            f"latency_ms={metrics.average_latency_ms:.1f}"
        )
    print(f"报告：{output_path}")
    return 0
