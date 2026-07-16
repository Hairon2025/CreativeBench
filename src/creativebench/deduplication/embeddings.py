"""Embedding provider abstraction used by semantic deduplication."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Minimal interface implemented by local or remote embedding services."""

    def encode(self, texts: list[str]) -> list[list[float]]:
        """Encode texts into vectors in the same order."""


class SentenceTransformerEmbeddingProvider:
    """Local sentence-transformers adapter loaded only when requested."""

    def __init__(self, model_name: str) -> None:
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as error:
            raise RuntimeError(
                '缺少语义去重依赖，请运行：pip install -e ".[semantic]"'
            ) from error

        self.model_name = model_name
        self._model = SentenceTransformer(model_name)

    def encode(self, texts: list[str]) -> list[list[float]]:
        embeddings = self._model.encode(
            texts,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return embeddings.tolist()
