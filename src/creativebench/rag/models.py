"""Structured intermediate results from the retrieval stage."""

from creativebench.knowledge.models import KnowledgeSearchHit
from creativebench.models import StrictModel


class RetrievalBundle(StrictModel):
    prompt_text: str
    label_hits: dict[str, list[KnowledgeSearchHit]]
    example_hits: list[KnowledgeSearchHit]
