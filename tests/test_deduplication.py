"""Tests for exact, near-text and semantic deduplication."""

from datetime import UTC, datetime

from creativebench.deduplication.fingerprint import (
    exact_fingerprint,
    hamming_distance,
    simhash,
)
from creativebench.deduplication.models import DuplicateMethod
from creativebench.deduplication.pipeline import deduplicate
from creativebench.ingestion.models import IngestedPromptRecord, IngestionMetadata
from creativebench.models import PromptSource, Scope, SourceType


class FakeEmbeddingProvider:
    def __init__(self, vectors: list[list[float]]) -> None:
        self.vectors = vectors

    def encode(self, texts: list[str]) -> list[list[float]]:
        assert len(texts) == len(self.vectors)
        return self.vectors


def make_record(identifier: int, text: str) -> IngestedPromptRecord:
    return IngestedPromptRecord(
        id=f"cbp-{identifier:04d}",
        prompt_text=text,
        language="zh-CN",
        scope=Scope.CREATIVE_WRITING,
        source=PromptSource(type=SourceType.SYNTHETIC, reference=None),
        ingestion=IngestionMetadata(
            external_id=f"raw-{identifier}",
            imported_at=datetime(2026, 7, 16, tzinfo=UTC),
            original_length=len(text),
            cleaned_length=len(text),
            cleaning_operations=[],
        ),
    )


def test_exact_fingerprint_is_stable() -> None:
    assert exact_fingerprint("同一条 Prompt") == exact_fingerprint("同一条 Prompt")
    assert exact_fingerprint("同一条 Prompt") != exact_fingerprint("另一条 Prompt")


def test_simhash_treats_small_edit_as_near_duplicate() -> None:
    left = simhash("请续写这个悬疑故事：午夜十二点，电话突然响了。")
    right = simhash("请续写这个悬疑故事，午夜十二点电话突然响了！")

    assert hamming_distance(left, right) <= 8


def test_pipeline_prioritizes_exact_before_near() -> None:
    records = [
        make_record(1, "请续写这个悬疑故事：午夜十二点，电话突然响了。"),
        make_record(2, "请续写这个悬疑故事：午夜十二点，电话突然响了。"),
        make_record(3, "请续写这个悬疑故事，午夜十二点电话突然响了！"),
    ]

    result = deduplicate(records, near_max_distance=8)

    assert len(result.unique_records) == 1
    assert [match.method for match in result.duplicates] == [
        DuplicateMethod.EXACT,
        DuplicateMethod.NEAR,
    ]


def test_semantic_provider_detects_paraphrase() -> None:
    records = [
        make_record(1, "设计一名被逐出师门的年轻剑客。"),
        make_record(2, "创建一个遭师门驱逐的少年侠客人设。"),
        make_record(3, "以唐代长安为背景设计故事情节。"),
    ]
    provider = FakeEmbeddingProvider(
        [
            [1.0, 0.0],
            [0.99, 0.05],
            [0.0, 1.0],
        ]
    )

    result = deduplicate(
        records,
        near_max_distance=0,
        semantic_provider=provider,
        semantic_threshold=0.95,
    )

    assert len(result.unique_records) == 2
    assert len(result.duplicates) == 1
    assert result.duplicates[0].method is DuplicateMethod.SEMANTIC
