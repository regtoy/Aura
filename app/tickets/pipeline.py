from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Sequence

from app.retrieval.embedding_pipeline import EmbeddingPipeline


_NORMALIZE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class TicketEmbeddingResult:
    """Result of passing ticket content through the normalization pipeline."""

    normalized_text: str
    embedding: list[float]


def normalize_ticket_text(text: str) -> str:
    """Collapse whitespace, lowercase and unicode-normalize a ticket body."""

    normalized = unicodedata.normalize("NFKC", text or "")
    normalized = normalized.lower().strip()
    normalized = _NORMALIZE_RE.sub(" ", normalized)
    return normalized


class TicketEmbeddingPipeline:
    """Pipeline that normalizes text and produces embeddings."""

    def __init__(self, embedder: EmbeddingPipeline | None = None) -> None:
        self._embedder = embedder or EmbeddingPipeline()

    def run(self, text: str) -> TicketEmbeddingResult:
        normalized = normalize_ticket_text(text)
        if not normalized:
            return TicketEmbeddingResult(normalized_text="", embedding=[])

        vectors = self._embedder.encode([normalized], normalize=True)
        if not vectors:
            return TicketEmbeddingResult(normalized_text=normalized, embedding=[])

        first = vectors[0]
        embedding: list[float] = [float(value) for value in first]
        return TicketEmbeddingResult(normalized_text=normalized, embedding=embedding)

    def encode_batch(self, texts: Sequence[str]) -> list[TicketEmbeddingResult]:
        normalized = [normalize_ticket_text(text) for text in texts]
        vectors = self._embedder.encode(normalized, normalize=True) if normalized else []
        results: list[TicketEmbeddingResult] = []
        for index, norm in enumerate(normalized):
            vector: Sequence[float] = vectors[index] if index < len(vectors) else []
            results.append(
                TicketEmbeddingResult(normalized_text=norm, embedding=[float(value) for value in vector])
            )
        return results
