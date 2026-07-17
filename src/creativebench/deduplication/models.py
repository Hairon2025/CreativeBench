"""Prompt 去重的结果数据模型。"""

from enum import StrEnum

from pydantic import Field

from creativebench.ingestion.models import IngestedPromptRecord
from creativebench.models import StrictModel


class DuplicateMethod(StrEnum):
    """去重命中方法的枚举。"""

    EXACT = "exact"  # 精确重复:SHA-256 指纹完全一致
    NEAR = "near"  # 近似重复:SimHash 海明距离在阈值内
    SEMANTIC = "semantic"  # 语义重复:Embedding 余弦相似度在阈值内


class DuplicateMatch(StrictModel):
    """单条重复命中记录,描述一条 Prompt 与哪个代表记录重复。"""

    duplicate_id: str  # 被判定为重复的 Prompt ID
    representative_id: str  # 该重复项所对应的代表(首次出现)Prompt ID
    method: DuplicateMethod  # 命中的去重方法
    score: float = Field(ge=0, le=1)  # 命中分数,介于 0 到 1 之间


class DeduplicationResult(StrictModel):
    """完整的去重结果,包含代表记录与所有重复命中。"""

    total: int = Field(ge=0)  # 输入的总记录数
    unique_records: list[IngestedPromptRecord]  # 保留的代表记录列表
    duplicates: list[DuplicateMatch]  # 所有被判定为重复的命中记录