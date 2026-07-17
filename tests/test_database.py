"""Database persistence tests using an isolated SQLite file."""

from datetime import UTC, datetime
from pathlib import Path

import pytest

from creativebench.database.models import DuplicateMatchORM, PromptORM, PromptStatus
from creativebench.database.repository import PromptRepository
from creativebench.database.session import create_database, create_session_factory
from creativebench.deduplication.models import DuplicateMatch, DuplicateMethod
from creativebench.ingestion.models import IngestedPromptRecord, IngestionMetadata
from creativebench.models import PromptSource, Scope, SourceType


def make_record(identifier: int, text: str) -> IngestedPromptRecord:
    return IngestedPromptRecord(
        id=f"cbp-{identifier:04d}",
        prompt_text=text,
        language="zh-CN",
        scope=Scope.CREATIVE_WRITING,
        source=PromptSource(type=SourceType.SYNTHETIC, reference=None),
        ingestion=IngestionMetadata(
            external_id=f"raw-{identifier}",
            imported_at=datetime(2026, 7, 17, tzinfo=UTC),
            original_length=len(text),
            cleaned_length=len(text),
            cleaning_operations=[],
        ),
    )


@pytest.fixture
def session_factory(tmp_path: Path):
    engine = create_database(f"sqlite:///{tmp_path / 'test.db'}")
    return create_session_factory(engine)


def test_synchronize_persists_prompts_metadata_and_duplicate(session_factory) -> None:
    records = [
        make_record(1, "请续写一个悬疑故事。"),
        make_record(2, "请续写一个悬疑故事。"),
    ]
    matches = [
        DuplicateMatch(
            duplicate_id="cbp-0002",
            representative_id="cbp-0001",
            method=DuplicateMethod.EXACT,
            score=1.0,
        )
    ]

    with session_factory.begin() as session:
        PromptRepository(session).synchronize_deduplication(records, matches)

    with session_factory() as session:
        representative = session.get(PromptORM, "cbp-0001")
        duplicate = session.get(PromptORM, "cbp-0002")
        relation = session.query(DuplicateMatchORM).one()

        assert representative is not None
        assert representative.status == PromptStatus.READY_FOR_LABELING
        assert representative.ingestion.external_id == "raw-1"
        assert duplicate is not None
        assert duplicate.status == PromptStatus.DUPLICATE
        assert relation.representative_prompt_id == "cbp-0001"


def test_synchronize_is_idempotent(session_factory) -> None:
    records = [
        make_record(1, "请续写一个悬疑故事。"),
        make_record(2, "请续写一个悬疑故事。"),
    ]
    matches = [
        DuplicateMatch(
            duplicate_id="cbp-0002",
            representative_id="cbp-0001",
            method=DuplicateMethod.EXACT,
            score=1.0,
        )
    ]

    for _ in range(2):
        with session_factory.begin() as session:
            PromptRepository(session).synchronize_deduplication(records, matches)

    with session_factory() as session:
        stats = PromptRepository(session).statistics()

    assert stats["total_prompts"] == 2
    assert stats["duplicate_relations"] == 1


def test_unknown_representative_is_rejected(session_factory) -> None:
    records = [make_record(1, "请续写一个悬疑故事。")]
    matches = [
        DuplicateMatch(
            duplicate_id="cbp-0001",
            representative_id="cbp-9999",
            method=DuplicateMethod.SEMANTIC,
            score=0.9,
        )
    ]

    with pytest.raises(ValueError, match="代表项不存在"):
        with session_factory.begin() as session:
            PromptRepository(session).synchronize_deduplication(records, matches)
