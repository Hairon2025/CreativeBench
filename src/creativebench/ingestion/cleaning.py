"""用于原始 Prompt 数据的确定性文本规范化模块。"""

import re
import unicodedata
from dataclasses import dataclass

from creativebench.ingestion.models import CleaningOperation

# 不可见字符集合:零宽空格、零宽非连接符、零宽连接符、字节顺序标记(BOM)
INVISIBLE_CHARACTERS = {"\u200b", "\u200c", "\u200d", "\ufeff"}
# 全角字符到半角字符的转换表,用于将全角字母数字转换为半角
# 包括全角数字(0-9)、全角大写字母(A-Z)、全角小写字母(a-z)以及全角空格
FULLWIDTH_ALPHANUMERIC_TRANSLATION = str.maketrans(
    {
        # 全角数字 ０-９ 转换为半角 0-9
        **{chr(code): chr(code - 0xFEE0) for code in range(0xFF10, 0xFF1A)},
        # 全角大写字母 Ａ-Ｚ 转换为半角 A-Z
        **{chr(code): chr(code - 0xFEE0) for code in range(0xFF21, 0xFF3B)},
        # 全角小写字母 ａ-ｚ 转换为半角 a-z
        **{chr(code): chr(code - 0xFEE0) for code in range(0xFF41, 0xFF5B)},
        # 全角空格转换为半角空格
        "\u3000": " ",
    }
)


@dataclass(frozen=True)
class CleaningResult:
    """清洗结果数据类。

    属性:
        text: 清洗后的文本内容。
        operations: 实际执行过的清洗操作列表,便于追踪每一步的处理记录。
    """

    text: str
    operations: list[CleaningOperation]


def _apply(
    text: str,
    operation: CleaningOperation,
    transform,
    operations: list[CleaningOperation],
) -> str:
    """应用单个清洗操作,并在文本发生变化时记录该操作。

    参数:
        text: 待处理的文本。
        operation: 当前执行的清洗操作类型。
        transform: 实际执行转换的函数。
        operations: 用于累计记录所有清洗操作的列表。

    返回:
        转换后的文本。
    """
    updated = transform(text)
    # 仅当文本确实发生变化时才记录该操作,避免冗余记录
    if updated != text:
        operations.append(operation)
    return updated


def _normalize_unicode(text: str) -> str:
    """对文本进行 Unicode 规范化处理。

    1. 使用 NFC 规范化形式将组合字符序列转换为预组合字符。
    2. 将全角字母数字转换为对应的半角字符。

    参数:
        text: 待规范化的文本。

    返回:
        规范化后的文本。
    """
    normalized = unicodedata.normalize("NFC", text)
    return normalized.translate(FULLWIDTH_ALPHANUMERIC_TRANSLATION)


def normalize_prompt_text(text: str) -> CleaningResult:
    """对 Prompt 文本进行规范化,在不改变其语义的前提下清除格式噪声。

    处理流程按以下顺序执行:
    1. 统一换行符:将 \r\n 和 \r 转换为 \n。
    2. Unicode 规范化:使用 NFC 形式并转换全角字符。
    3. 移除不可见字符:如零宽空格、零宽连接符等。
    4. 移除控制字符:除换行符和制表符外的其他控制字符。
    5. 规范化空白字符:合并连续空白,限制连续换行不超过两个。
    6. 修剪文本:去除每行首尾空白以及文本首尾空白。

    参数:
        text: 原始 Prompt 文本。

    返回:
        包含清洗后文本及实际执行操作的 CleaningResult 对象。
    """

    operations: list[CleaningOperation] = []

    # 步骤 1: 将所有换行符统一为 \n,兼容 Windows(\r\n)和旧版 Mac(\r)的格式
    text = _apply(
        text,
        CleaningOperation.NORMALIZED_LINE_ENDINGS,
        lambda value: value.replace("\r\n", "\n").replace("\r", "\n"),
        operations,
    )
    # 步骤 2: Unicode 规范化与全角转半角
    text = _apply(
        text,
        CleaningOperation.NORMALIZED_UNICODE,
        _normalize_unicode,
        operations,
    )
    # 步骤 3: 移除零宽空格等不可见字符,避免影响后续处理或比较
    text = _apply(
        text,
        CleaningOperation.REMOVED_INVISIBLE_CHARACTERS,
        lambda value: "".join(char for char in value if char not in INVISIBLE_CHARACTERS),
        operations,
    )
    # 步骤 4: 移除控制字符(Cc 类别),但保留换行符(\n)和制表符(\t)
    text = _apply(
        text,
        CleaningOperation.REMOVED_CONTROL_CHARACTERS,
        lambda value: "".join(
            char
            for char in value
            if char in {"\n", "\t"} or unicodedata.category(char) != "Cc"
        ),
        operations,
    )
    # 步骤 5: 规范化空白字符
    # 内层正则将所有非换行的空白字符(包括全角空格等)替换为单个半角空格
    # 外层正则将连续 3 个或以上的换行符压缩为 2 个,避免过多空行
    text = _apply(
        text,
        CleaningOperation.NORMALIZED_WHITESPACE,
        lambda value: re.sub(r"\n{3,}", "\n\n", re.sub(r"[^\S\n]+", " ", value)),
        operations,
    )
    # 步骤 6: 去除每行首尾空白以及整个文本首尾的空白
    text = _apply(
        text,
        CleaningOperation.TRIMMED_TEXT,
        lambda value: "\n".join(line.strip() for line in value.splitlines()).strip(),
        operations,
    )

    return CleaningResult(text=text, operations=operations)