"""Three-stage Prompt deduplication pipeline."""

import math
from pathlib import Path

from pydantic import ValidationError

from creativebench.deduplication.embeddings import EmbeddingProvider
from creativebench.deduplication.fingerprint import (
    exact_fingerprint,
    hamming_distance,
    simhash,
)
from creativebench.deduplication.models import (
    DeduplicationResult,
    DuplicateMatch,
    DuplicateMethod,
)
from creativebench.ingestion.models import IngestedPromptRecord


def cosine_similarity(left: list[float], right: list[float]) -> float:
    """Calculate cosine similarity without requiring NumPy in the core package."""

    if not left or len(left) != len(right):
        raise ValueError("Embedding 向量不能为空且维度必须一致")

    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def deduplicate(
    records: list[IngestedPromptRecord],
    *,
    near_max_distance: int = 8,
    semantic_provider: EmbeddingProvider | None = None,
    semantic_threshold: float = 0.80,
) -> DeduplicationResult:
    """Keep first-seen representatives and classify later duplicates."""

    if near_max_distance < 0 or near_max_distance > 64:
        raise ValueError("near_max_distance 必须在 0 到 64 之间")
    if not 0 <= semantic_threshold <= 1:
        raise ValueError("semantic_threshold 必须在 0 到 1 之间")

    exact_hashes = [exact_fingerprint(record.prompt_text) for record in records]
    simhashes = [simhash(record.prompt_text) for record in records]
    embeddings = (
        semantic_provider.encode([record.prompt_text for record in records])
        if semantic_provider
        else None
    )

    if embeddings is not None and len(embeddings) != len(records):
        raise ValueError("Embedding 数量必须与 Prompt 数量一致")

    representative_indexes: list[int] = []
    duplicates: list[DuplicateMatch] = []

    for index, record in enumerate(records):
        match: DuplicateMatch | None = None

        for representative_index in representative_indexes:
            representative = records[representative_index]
            if exact_hashes[index] == exact_hashes[representative_index]:
                match = DuplicateMatch(
                    duplicate_id=record.id,
                    representative_id=representative.id,
                    method=DuplicateMethod.EXACT,
                    score=1.0,
                )
                break

        if match is None:
            for representative_index in representative_indexes:
                representative = records[representative_index]
                distance = hamming_distance(
                    simhashes[index], simhashes[representative_index]
                )
                if distance <= near_max_distance:
                    match = DuplicateMatch(
                        duplicate_id=record.id,
                        representative_id=representative.id,
                        method=DuplicateMethod.NEAR,
                        score=1 - distance / 64,
                    )
                    break

        if match is None and embeddings is not None:
            for representative_index in representative_indexes:
                representative = records[representative_index]
                similarity = cosine_similarity(
                    embeddings[index], embeddings[representative_index]
                )
                if similarity >= semantic_threshold:
                    match = DuplicateMatch(
                        duplicate_id=record.id,
                        representative_id=representative.id,
                        method=DuplicateMethod.SEMANTIC,
                        score=min(similarity, 1.0),
                    )
                    break

        if match is None:
            representative_indexes.append(index)
        else:
            duplicates.append(match)

    return DeduplicationResult(
        total=len(records),
        unique_records=[records[index] for index in representative_indexes],
        duplicates=duplicates,
    )


def load_ingested_jsonl(path: Path) -> list[IngestedPromptRecord]:
    """Load a previously imported JSONL file."""

    records: list[IngestedPromptRecord] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as file:
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                continue
            try:
                record = IngestedPromptRecord.model_validate_json(line)
            except (ValidationError, ValueError) as error:
                raise ValueError(f"第 {line_number} 行数据无效：{error}") from error
            if record.id in seen_ids:
                raise ValueError(f"第 {line_number} 行 ID 重复：{record.id}")
            seen_ids.add(record.id)
            records.append(record)
    return records


def write_deduplication_result(
    result: DeduplicationResult,
    *,
    unique_path: Path,
    report_path: Path,
) -> None:
    """Write unique records and duplicate decisions to separate JSONL files."""

    unique_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    with unique_path.open("w", encoding="utf-8") as file:
        for record in result.unique_records:
            file.write(record.model_dump_json())
            file.write("\n")

    with report_path.open("w", encoding="utf-8") as file:
        for duplicate in result.duplicates:
            file.write(duplicate.model_dump_json())
            file.write("\n")
