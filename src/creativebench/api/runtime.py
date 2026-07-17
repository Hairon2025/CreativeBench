"""Lazy production classifier; no GLM client is created at API startup."""

from creativebench.classification.model import build_glm_model
from creativebench.classification.models import ClassificationRun
from creativebench.classification.service import ClassificationService
from creativebench.config import Settings
from creativebench.deduplication.embeddings import SentenceTransformerEmbeddingProvider
from creativebench.knowledge.store import QdrantKnowledgeStore
from creativebench.rag.chain import build_rag_chain


class GLMClassificationRuntime:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self._embedding_provider: SentenceTransformerEmbeddingProvider | None = None

    def classify(self, prompt_text: str) -> ClassificationRun:
        """Build the network client lazily and close Qdrant after one request."""

        model = build_glm_model(self.settings)
        if self._embedding_provider is None:
            self._embedding_provider = SentenceTransformerEmbeddingProvider(
                self.settings.embedding_model
            )
        store = QdrantKnowledgeStore(
            self.settings.vector_store_path,
            self.settings.knowledge_collection,
        )
        try:
            rag_chain = build_rag_chain(
                store,
                self._embedding_provider,
                query_instruction=self.settings.embedding_query_instruction,
                label_top_k=self.settings.rag_label_top_k,
                example_top_k=self.settings.rag_example_top_k,
            )
            return ClassificationService(
                rag_chain,
                model,
                model_name=self.settings.glm_model,
                max_attempts=self.settings.glm_max_attempts,
                retry_delay_seconds=self.settings.glm_retry_delay_seconds,
            ).classify(prompt_text)
        finally:
            store.close()
