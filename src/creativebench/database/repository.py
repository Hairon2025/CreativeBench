"""Transactional persistence operations for the current pipeline outputs."""

from collections.abc import Sequence

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from creativebench.database.models import (
    DuplicateMatchORM,
    PromptIngestionORM,
    PromptORM,
    PromptStatus,
)
from creativebench.deduplication.models import DuplicateMatch
from creativebench.ingestion.models import IngestedPromptRecord


class PromptRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def synchronize_deduplication(
        self,
        records: Sequence[IngestedPromptRecord],
        duplicates: Sequence[DuplicateMatch],
    ) -> None:
        """Upsert Prompts and replace duplicate decisions for this batch."""

        records_by_id = {record.id: record for record in records}
        if len(records_by_id) != len(records):
            raise ValueError("待写入 Prompt 中存在重复 ID")

        for match in duplicates:
            if match.duplicate_id not in records_by_id:
                raise ValueError(f"重复项不存在于本批数据：{match.duplicate_id}")
            if match.representative_id not in records_by_id:
                raise ValueError(f"代表项不存在于本批数据：{match.representative_id}")

        for record in records:
            self._upsert_prompt(record)
        self.session.flush()

        record_ids = list(records_by_id)
        if record_ids:
            self.session.execute(
                delete(DuplicateMatchORM).where(
                    DuplicateMatchORM.duplicate_prompt_id.in_(record_ids)
                )
            )
            for prompt in self.session.scalars(
                select(PromptORM).where(PromptORM.id.in_(record_ids))
            ):
                if prompt.status == PromptStatus.DUPLICATE:
                    prompt.status = PromptStatus.READY_FOR_LABELING.value

        for match in duplicates:
            self.session.add(
                DuplicateMatchORM(
                    duplicate_prompt_id=match.duplicate_id,
                    representative_prompt_id=match.representative_id,
                    method=match.method.value,
                    score=match.score,
                )
            )
            duplicate_prompt = self.session.get(PromptORM, match.duplicate_id)
            if duplicate_prompt is None:
                raise ValueError(f"数据库中不存在重复项：{match.duplicate_id}")
            duplicate_prompt.status = PromptStatus.DUPLICATE.value

    def _upsert_prompt(self, record: IngestedPromptRecord) -> None:
        prompt = self.session.get(PromptORM, record.id)
        if prompt is None:
            prompt = PromptORM(id=record.id)
            self.session.add(prompt)

        prompt.prompt_text = record.prompt_text
        prompt.language = record.language
        prompt.scope = record.scope.value
        prompt.source_type = record.source.type.value
        prompt.source_reference = record.source.reference
        prompt.created_at = record.ingestion.imported_at

        ingestion = prompt.ingestion
        if ingestion is None:
            ingestion = PromptIngestionORM(prompt_id=record.id)
            prompt.ingestion = ingestion

        ingestion.external_id = record.ingestion.external_id
        ingestion.imported_at = record.ingestion.imported_at
        ingestion.original_length = record.ingestion.original_length
        ingestion.cleaned_length = record.ingestion.cleaned_length
        ingestion.cleaning_operations = [
            operation.value for operation in record.ingestion.cleaning_operations
        ]

    def statistics(self) -> dict[str, object]:
        total = self.session.scalar(select(func.count()).select_from(PromptORM)) or 0
        duplicate_count = (
            self.session.scalar(select(func.count()).select_from(DuplicateMatchORM)) or 0
        )
        status_rows = self.session.execute(
            select(PromptORM.status, func.count()).group_by(PromptORM.status)
        )
        method_rows = self.session.execute(
            select(DuplicateMatchORM.method, func.count()).group_by(
                DuplicateMatchORM.method
            )
        )
        return {
            "total_prompts": total,
            "duplicate_relations": duplicate_count,
            "status_counts": {
                status: count for status, count in status_rows
            },
            "method_counts": {
                method: count for method, count in method_rows
            },
        }
