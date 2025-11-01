from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class RetrievalResult:
    """Normalized representation of a document returned by a retriever."""

    document_id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)

    def with_metadata(self, **extra: Any) -> "RetrievalResult":
        """Return a copy with metadata merged with provided key/value pairs."""

        merged = dict(self.metadata)
        merged.update(extra)
        return RetrievalResult(document_id=self.document_id, score=self.score, metadata=merged)
