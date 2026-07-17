"""用于精确与近似重复检测的稳定文本指纹。"""

import hashlib
import unicodedata
from collections import Counter


def exact_fingerprint(text: str) -> str:
    """返回清洗后文本的稳定 SHA-256 指纹。

    该指纹对完全相同的输入产生相同结果,可直接用于精确重复检测。

    参数:
        text: 已被规范化(去除空白、Unicode 归一化等)的文本。

    返回:
        64 位十六进制的 SHA-256 哈希字符串。
    """

    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _fingerprint_text(text: str) -> str:
    """将文本折叠为统一的比较形式。

    处理步骤:
    1. 使用 Unicode casefold 进行大小写无关的折叠。
    2. 去除所有空白字符。
    3. 去除所有标点符号(Unicode 类别以 'P' 开头)。

    参数:
        text: 待处理的文本。

    返回:
        经过折叠后的字符串。
    """
    return "".join(
        char.casefold()
        for char in text
        if not char.isspace() and not unicodedata.category(char).startswith("P")
    )


def _character_ngrams(text: str, size: int = 3) -> list[str]:
    """生成字符级 n-gram 列表。

    先对文本进行折叠(去空白、去标点、统一大小写),再以滑窗方式
    切分为指定长度的字符片段,适用于中文等不以空格分词的语言。

    参数:
        text: 待处理的文本。
        size: n-gram 的长度,默认为 3。

    返回:
        字符 n-gram 列表;若文本折叠后为空则返回空列表;若文本长度
        不超过 size,则返回包含整个文本的单元素列表。
    """
    normalized = _fingerprint_text(text)
    if len(normalized) <= size:
        # 文本过短时,直接以整体作为一个 n-gram(若非空)
        return [normalized] if normalized else []
    return [normalized[index : index + size] for index in range(len(normalized) - size + 1)]


def simhash(text: str, *, bits: int = 64, ngram_size: int = 3) -> int:
    """基于字符 n-gram 生成 SimHash,适用于中文等文本。

    SimHash 的核心思想是:为每个 token 计算哈希,按位累加权重(正/负),
    最终通过符号位得到一个紧凑指纹。两个指纹的海明距离越小,文本越相似。

    参数:
        text: 待生成指纹的文本。
        bits: 指纹位数,必须介于 1 到 256 之间,默认为 64。
        ngram_size: 字符 n-gram 的长度,默认为 3。

    返回:
        一个整数形式的 SimHash 指纹;若文本无有效 token 则返回 0。
    """

    # 限制指纹位数,避免过低精度或过高内存开销
    if bits < 1 or bits > 256:
        raise ValueError("SimHash bits 必须在 1 到 256 之间")

    # 使用 Counter 统计每个 n-gram 的出现频次,作为加权依据
    tokens = Counter(_character_ngrams(text, ngram_size))
    if not tokens:
        return 0

    # 初始化位累加向量,并按字节长度截取 SHA-256 输出
    vector = [0] * bits
    byte_count = (bits + 7) // 8
    for token, weight in tokens.items():
        # 对每个 n-gram 计算哈希值,并截取到所需字节数
        digest = hashlib.sha256(token.encode("utf-8")).digest()[:byte_count]
        hashed = int.from_bytes(digest, byteorder="big")
        # 遍历每一位:该位为 1 时累加权重,为 0 时减去权重
        for bit in range(bits):
            vector[bit] += weight if hashed & (1 << bit) else -weight

    # 根据累加值的符号生成最终指纹:非负位置 1
    fingerprint = 0
    for bit, value in enumerate(vector):
        if value >= 0:
            fingerprint |= 1 << bit
    return fingerprint


def hamming_distance(left: int, right: int) -> int:
    """计算两个 SimHash 指纹之间的海明距离(不同位的个数)。

    参数:
        left: 第一个 SimHash 指纹。
        right: 第二个 SimHash 指纹。

    返回:
        两个指纹在二进制表示下不同位的数量,数值越小代表越相似。
    """

    # 利用 Python 内置的 bit_count 直接统计异或结果中 1 的个数
    return (left ^ right).bit_count()