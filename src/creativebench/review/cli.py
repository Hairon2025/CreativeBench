"""Inspect and complete low-confidence review tasks."""

import argparse
from pathlib import Path

from pydantic import ValidationError

from creativebench.classification.models import ClassificationPrediction
from creativebench.config import get_settings
from creativebench.database.classification_repository import (
    ClassificationReviewRepository,
)
from creativebench.database.session import create_database, create_session_factory


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="管理 CreativeBench 人工审核队列")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("list", help="列出待审核任务")

    approve = subparsers.add_parser("approve", help="确认模型原始预测")
    approve.add_argument("task_id", type=int)
    approve.add_argument("--reviewer", required=True)
    approve.add_argument("--notes")

    correct = subparsers.add_parser("correct", help="提交人工修正后的预测 JSON")
    correct.add_argument("task_id", type=int)
    correct.add_argument("--reviewer", required=True)
    correct.add_argument("--prediction", type=Path, required=True)
    correct.add_argument("--notes")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    settings = get_settings()
    engine = create_database(settings.database_url)
    session_factory = create_session_factory(engine)

    if args.command == "list":
        with session_factory() as session:
            tasks = ClassificationReviewRepository(session).list_pending_reviews()
            if not tasks:
                print("当前没有待审核任务")
                return 0
            for task in tasks:
                run = task.classification_run
                print(
                    f"task={task.id} prompt={run.prompt_id} "
                    f"confidence={run.confidence:.3f} model={run.model_name}"
                )
        return 0

    corrected_prediction = None
    if args.command == "correct":
        if not args.prediction.is_file():
            print(f"审核失败：修正文件不存在：{args.prediction}")
            return 2
        try:
            corrected_prediction = ClassificationPrediction.model_validate_json(
                args.prediction.read_text(encoding="utf-8")
            )
        except (OSError, ValidationError) as error:
            print(f"审核失败：修正结果未通过校验：{error}")
            return 2

    try:
        with session_factory.begin() as session:
            task = ClassificationReviewRepository(session).complete_review(
                args.task_id,
                reviewer=args.reviewer,
                corrected_prediction=corrected_prediction,
                notes=args.notes,
            )
        print(f"审核完成：task={task.id} reviewer={task.reviewer}")
        return 0
    except ValueError as error:
        print(f"审核失败：{error}")
        return 2
