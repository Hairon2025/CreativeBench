"""语义去重所使用的 Embedding 提供者抽象。"""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """由本地或远端 Embedding 服务实现的最小接口契约。"""

    def encode(self, texts: list[str]) -> list[list[float]]:
        """将文本列表编码为向量列表,顺序与输入一一对应。

        参数:
            texts: 待编码的文本列表。

        返回:
            与输入等长的向量列表,每个向量以 float 列表形式给出。
        """


class SentenceTransformerEmbeddingProvider:
    """基于 sentence-transformers 的本地 Embedding 适配器,仅在需要时加载。"""

    def __init__(self, model_name: str) -> None:
        # 延迟导入:仅在用户真正需要语义去重时才加载较重的依赖,
        # 避免对仅使用精确/近似去重的用户造成不必要的安装负担。
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            # 抛出更友好的运行时错误,指引用户安装语义去重所需的额外依赖
            raise RuntimeError(
                '缺少语义去重依赖，请运行：pip install -e ".[semantic]"'
            ) from error

        self.model_name = model_name
        # 加载指定的 SentenceTransformer 模型,后续 encode 调用会复用该模型
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        """调用底层模型将文本列表编码为 L2 归一化的向量列表。

        参数:
            texts: 待编码的文本列表。

        返回:
            与输入等长的 float 列表,每个内部列表即为一个向量。
        """
        embeddings = self._model.encode(
            texts,
            # 启用 L2 归一化,使后续可直接用点积衡量余弦相似度
            normalize_embeddings=True,
            # 以 numpy 数组形式返回结果,便于调用 .tolist()
            convert_to_numpy=True,
            # 在 CLI/库调用场景中关闭进度条,避免污染输出
            show_progress_bar=False,
        )
        return embeddings.tolist()