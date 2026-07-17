"""三阶段 Prompt 去重管道。"""

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
    """在不依赖 NumPy 的前提下计算两个 Embedding 向量的余弦相似度。

    参数:
        left: 第一个向量。
        right: 第二个向量。

    返回:
        介于 [-1, 1] 的余弦相似度;若任一向量为零向量则返回 0.0。

    异常:
        ValueError: 当任一向量为空或两个向量维度不一致时抛出。
    """

    # 校验向量非空且维度一致,避免后续 zip 截断或除零等异常
    if not left or len(left) != len(right):
        raise ValueError("Embedding 向量不能为空且维度必须一致")

    # 分别计算点积与两个向量的 L2 范数
    dot_product = sum(a * b for a, b in zip(left, right, strict=True))
    left_norm = math.sqrt(sum(value * value for value in left))
    right_norm = math.sqrt(sum(value * value for value in right))
    if left_norm == 0 or right_norm == 0:
        # 任一向量为零向量时相似度未定义,按 0.0 处理
        return 0.0
    return dot_product / (left_norm * right_norm)


def deduplicate(
    records: list[IngestedPromptRecord],
    *,
    near_max_distance: int = 8,
    semantic_provider: EmbeddingProvider | None = None,
    semantic_threshold: float = 0.80,
) -> DeduplicationResult:
    """保留首次出现的代表记录,并将后续重复项分类归入对应命中方法。

    三阶段匹配优先级:精确 > 近似 > 语义。
    每个新记录会依次与已确定的代表记录比较,命中即停止,保证每条记录
    最多只有一个 DuplicateMatch。

    参数:
        records: 待去重的 Prompt 记录列表(顺序敏感,先出现者优先)。
        near_max_distance: 近似重复允许的最大海明距离,默认为 8,范围 0-64。
        semantic_provider: 语义 Embedding 提供者;若为 None 则跳过语义去重。
        semantic_threshold: 语义重复所需的最小余弦相似度,默认为 0.80,范围 0-1。

    返回:
        DeduplicationResult: 包含总数、唯一记录与所有重复命中。
    """

    # 参数合法性校验
    if near_max_distance < 0 or near_max_distance > 64:
        raise ValueError("near_max_distance 必须在 0 到 64 之间")
    if not 0 <= semantic_threshold <= 1:
        raise ValueError("semantic_threshold 必须在 0 到 1 之间")

    # 一次性预计算所有记录的指纹,避免在循环中重复计算以提升性能
    exact_hashes = [exact_fingerprint(record.prompt_text) for record in records]
    simhashes = [simhash(record.prompt_text) for record in records]
    # 若提供了语义提供者,批量编码所有 Prompt 得到 Embedding
    embeddings = (
        semantic_provider.encode([record.prompt_text for record in records])
        if semantic_provider
        else None
    )

    # 防御性检查:Embedding 数量必须与输入记录数量一致
    if embeddings is not None and len(embeddings) != len(records):
        raise ValueError("Embedding 数量必须与 Prompt 数量一致")

    # 代表记录的索引列表(按出现顺序)与重复命中列表
    representative_indexes: list[int] = []
    duplicates: list[DuplicateMatch] = []

    for index, record in enumerate(records):
        match: DuplicateMatch | None = None

        # 阶段 1:精确重复检测 —— SHA-256 哈希完全相等
        for representative_index in representative_indexes:
            representative = records[representative_index]
            if exact_hashes[index] == exact_hashes[representative_index]:
                match = DuplicateMatch(
                    duplicate_id=record.id,
                    representative_id=representative.id,
                    method=DuplicateMethod.EXACT,
                    score=1.0,  # 精确命中,分数为 1.0
                )
                break

        # 阶段 2:近似重复检测 —— SimHash 海明距离在阈值内
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
                        # 将海明距离归一化为 0-1 范围的相似度分数
                        score=1 - distance / 64,
                    )
                    break

        # 阶段 3:语义重复检测 —— 余弦相似度在阈值内
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
                        # 截断到不超过 1.0,避免浮点误差越界
                        score=min(similarity, 1.0),
                    )
                    break

        # 若三阶段均未命中,则该记录作为新的代表保留;否则归入重复列表
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
    """加载此前由导入阶段生成的 JSONL 文件。

    参数:
        path: 待加载的 JSONL 文件路径。

    返回:
        解析得到的 IngestedPromptRecord 列表,顺序与文件中行顺序一致。

    异常:
        ValueError: 当文件中存在空行以外的数据格式错误或 ID 重复时抛出。
    """

    records: list[IngestedPromptRecord] = []
    seen_ids: set[str] = set()
    with path.open(encoding="utf-8") as file:
        # enumerate 从 1 开始计数,便于在错误信息中提示真实行号
        for line_number, raw_line in enumerate(file, start=1):
            line = raw_line.strip()
            if not line:
                # 跳过空行,容忍文件末尾换行
                continue
            try:
                record = IngestedPromptRecord.model_validate_json(line)
            except (ValidationError, ValueError) as error:
                # 抛出包含行号的友好错误信息,便于定位问题
                raise ValueError(f"第 {line_number} 行数据无效：{error}") from error
            if record.id in seen_ids:
                # Prompt ID 必须唯一,重复说明上游导入或文件被破坏
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
    """将唯一记录与重复判定结果分别写入两个 JSONL 文件。

    参数:
        result: 去重结果对象。
        unique_path: 唯一记录(JSONL)输出路径。
        report_path: 重复命中(JSONL)输出路径。
    """

    # 确保两个输出文件的父目录存在,缺失时自动创建
    unique_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    # 写入唯一记录,每行一条 JSON
    with unique_path.open("w", encoding="utf-8") as file:
        for record in result.unique_records:
            file.write(record.model_dump_json())
            file.write("\n")

    # 写入重复命中报告,每行一条 JSON
    with report_path.open("w", encoding="utf-8") as file:
        for duplicate in result.duplicates:
            file.write(duplicate.model_dump_json())
            file.write("\n")