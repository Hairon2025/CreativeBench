"""Local Qdrant adapter for knowledge documents."""

from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from qdrant_client import QdrantClient, models

from creativebench.knowledge.models import (
    KnowledgeDocument,
    KnowledgeDocumentType,
    KnowledgeSearchHit,
)


class QdrantKnowledgeStore:
    def __init__(self, path: Path, collection_name: str) -> None:
        path.mkdir(parents=True, exist_ok=True)
        self.collection_name = collection_name
        self.client = QdrantClient(path=str(path))

    def rebuild(
        self,
        documents: list[KnowledgeDocument],
        embeddings: list[list[float]],
    ) -> None:
        if not documents:
            raise ValueError("知识文档不能为空")
        if len(documents) != len(embeddings):
            raise ValueError("文档数量与 Embedding 数量不一致")
        vector_size = len(embeddings[0])
        if vector_size == 0 or any(len(vector) != vector_size for vector in embeddings):
            raise ValueError("Embedding 维度不能为空且必须一致")

        if self.client.collection_exists(self.collection_name):
            self.client.delete_collection(self.collection_name)
        self.client.create_collection(
            collection_name=self.collection_name,
            vectors_config=models.VectorParams(
                size=vector_size,
                distance=models.Distance.COSINE,
            ),
        )
        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, document.id)),
                vector=embedding,
                payload={
                    "document_id": document.id,
                    "content": document.content,
                    "doc_type": document.doc_type.value,
                    "metadata": document.metadata,
                },
            )
            for document, embedding in zip(documents, embeddings, strict=True)
        ]
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def upsert(
        self,
        documents: list[KnowledgeDocument],
        embeddings: list[list[float]],
    ) -> None:
        """Insert or replace deterministic document IDs without rebuilding."""

        if not documents:
            return
        if not self.client.collection_exists(self.collection_name):
            raise ValueError("知识库尚未构建，请先执行 creativebench-knowledge build")
        if len(documents) != len(embeddings):
            raise ValueError("文档数量与 Embedding 数量不一致")
        vector_size = len(embeddings[0])
        if vector_size == 0 or any(len(vector) != vector_size for vector in embeddings):
            raise ValueError("Embedding 维度不能为空且必须一致")

        points = [
            models.PointStruct(
                id=str(uuid5(NAMESPACE_URL, document.id)),
                vector=embedding,
                payload={
                    "document_id": document.id,
                    "content": document.content,
                    "doc_type": document.doc_type.value,
                    "metadata": document.metadata,
                },
            )
            for document, embedding in zip(documents, embeddings, strict=True)
        ]
        self.client.upsert(
            collection_name=self.collection_name,
            points=points,
            wait=True,
        )

    def search(
        self,
        query_vector: list[float],
        *,
        top_k: int = 5,
        doc_type: KnowledgeDocumentType | None = None,
        dimension: str | None = None,
    ) -> list[KnowledgeSearchHit]:
        conditions = []
        if doc_type is not None:
            conditions.append(
                models.FieldCondition(
                    key="doc_type",
                    match=models.MatchValue(value=doc_type.value),
                )
            )
        if dimension is not None:
            conditions.append(
                models.FieldCondition(
                    key="metadata.dimension",
                    match=models.MatchValue(value=dimension),
                )
            )
        query_filter = models.Filter(must=conditions) if conditions else None
        points = self.client.query_points(
            collection_name=self.collection_name,
            query=query_vector,
            query_filter=query_filter,
            with_payload=True,
            limit=top_k,
        ).points
        return [
            KnowledgeSearchHit(
                document_id=str(point.payload["document_id"]),
                content=str(point.payload["content"]),
                doc_type=KnowledgeDocumentType(point.payload["doc_type"]),
                score=point.score,
                metadata=dict(point.payload["metadata"]),
            )
            for point in points
            if point.payload is not None
        ]

    def count(self) -> int:
        collection = self.client.get_collection(self.collection_name)
        return collection.points_count or 0

    def close(self) -> None:
        self.client.close()
