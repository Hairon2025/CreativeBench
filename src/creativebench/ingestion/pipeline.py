"""将不可信的原始行转换为规范化的、清洗后的 Prompt 记录。"""

from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path

from pydantic import ValidationError

from creativebench.ingestion.cleaning import normalize_prompt_text
from creativebench.ingestion.models import (
    CleaningOperation,
    IngestedPromptRecord,
    IngestionMetadata,
    RawPromptInput,
)
from creativebench.ingestion.readers import read_raw_rows
from creativebench.models import PromptSource


@dataclass(frozen=True)
class ImportIssue:
    """单条导入问题记录,用于描述某行数据被拒绝的原因。

    属性:
        line_number: 出问题的原始行号。
        external_id: 对应的外部 ID(若原始数据中提供),便于追溯。
        message: 拒绝原因的描述信息。
    """

    line_number: int
    external_id: str | None
    message: str


@dataclass
class ImportReport:
    """导入报告,汇总本次导入的总体情况。

    属性:
        total: 总共处理的数据条数(包括接受与拒绝)。
        accepted: 通过校验并被接受的 Prompt 记录列表。
        rejected: 被拒绝的导入问题列表。
    """

    total: int = 0
    accepted: list[IngestedPromptRecord] = field(default_factory=list)
    rejected: list[ImportIssue] = field(default_factory=list)

    @property
    def operation_counts(self) -> Counter[CleaningOperation]:
        """统计所有被接受记录中各项清洗操作出现的次数。"""
        return Counter(
            operation
            for record in self.accepted
            for operation in record.ingestion.cleaning_operations
        )


def _format_prompt_id(sequence: int) -> str:
    """将序列号格式化为 4 位补零的 Prompt ID,例如 1001 -> 'cbp-1001'。"""
    return f"cbp-{sequence:04d}"


def import_prompts(
    path: Path,
    *,
    start_id: int = 1001,
    min_length: int = 5,
    max_length: int = 10_000,
    imported_at: datetime | None = None,
) -> ImportReport:
    """导入全部合法行,同时按行收集被拒绝的原因。

    参数:
        path: 待导入的原始数据文件路径。
        start_id: 生成的 Prompt ID 的起始序列号,默认为 1001。
        min_length: 清洗后 Prompt 文本允许的最小长度,小于该值将被拒绝。
        max_length: 清洗后 Prompt 文本允许的最大长度,大于该值将被拒绝。
        imported_at: 导入时间戳;若为 None 则使用当前 UTC 时间。

    返回:
        ImportReport 对象,包含接受与拒绝的记录及统计信息。
    """

    # 参数合法性校验:最小长度必须 >= 1,且最大长度必须不小于最小长度
    if min_length < 1 or max_length < min_length:
        raise ValueError("Prompt 长度范围配置无效")

    # 若未提供导入时间,则使用当前 UTC 时间作为统一的导入时刻
    imported_at = imported_at or datetime.now(UTC)
    # 调用 reader 读取原始行及读取阶段产生的问题
    rows, read_issues = read_raw_rows(path)
    # 构造导入报告,总数 = 有效行数 + 读取阶段已失败的问题数
    report = ImportReport(total=len(rows) + len(read_issues))
    # 将读取阶段的问题全部纳入报告(无 external_id,因为读取阶段无法关联到具体记录)
    report.rejected.extend(
        ImportIssue(issue.line_number, None, issue.message) for issue in read_issues
    )

    # 逐行处理原始数据
    for row in rows:
        # 提取外部 ID(若存在),用于在拒绝时回填便于排查
        external_id = row.data.get("external_id")
        external_id_text = str(external_id) if external_id is not None else None

        # 使用 Pydantic 对原始数据进行结构化校验,捕获字段缺失或类型错误
        try:
            raw = RawPromptInput.model_validate(row.data)
        except ValidationError as error:
            report.rejected.append(
                ImportIssue(row.line_number, external_id_text, str(error))
            )
            continue

        # 对 prompt_text 执行确定性文本规范化(换行、Unicode、空白、修剪等)
        cleaned = normalize_prompt_text(raw.prompt_text)
        cleaned_length = len(cleaned.text)

        # 长度下限校验:清洗后过短的内容没有评估价值,直接拒绝
        if cleaned_length < min_length:
            report.rejected.append(
                ImportIssue(
                    row.line_number,
                    raw.external_id,
                    f"清洗后长度 {cleaned_length} 小于最小值 {min_length}",
                )
            )
            continue
        # 长度上限校验:过长内容可能含有噪声或超出存储/评估能力,直接拒绝
        if cleaned_length > max_length:
            report.rejected.append(
                ImportIssue(
                    row.line_number,
                    raw.external_id,
                    f"清洗后长度 {cleaned_length} 超过最大值 {max_length}",
                )
            )
            continue

        # 构造规范化后的 Prompt 记录,分配递增的内部 ID
        record = IngestedPromptRecord(
            id=_format_prompt_id(start_id + len(report.accepted)),
            prompt_text=cleaned.text,
            language=raw.language,
            scope=raw.scope,
            source=PromptSource(type=raw.source_type, reference=raw.source_reference),
            ingestion=IngestionMetadata(
                external_id=raw.external_id,
                imported_at=imported_at,
                original_length=len(raw.prompt_text),
                cleaned_length=cleaned_length,
                cleaning_operations=cleaned.operations,
            ),
        )
        # 将通过的记录加入报告
        report.accepted.append(record)

    return report


def write_imported_jsonl(records: list[IngestedPromptRecord], path: Path) -> None:
    """将被接受的记录以 UTF-8 编码的 JSONL 格式写入文件。

    JSONL 每行一条 JSON,便于流式读取与后续处理。

    参数:
        records: 待写入的 Prompt 记录列表。
        path: 输出文件路径。
    """

    # 确保父目录存在,缺失时自动创建
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as file:
        # 逐条记录序列化为 JSON 并写入,每行末尾追加换行符保持 JSONL 格式
        for record in records:
            file.write(record.model_dump_json())
            file.write("\n")