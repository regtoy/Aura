from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, Sequence


@dataclass(slots=True)
class RetrievedDocument:
    """Lightweight representation of a ranked document.

    The compiler accepts instances of this dataclass to remain agnostic to the
    retrieval backend. Only the `document_id`, `score` and `metadata` fields are
    required, mirroring the :class:`~app.retrieval.rrf.FusedDocument` shape while
    avoiding a hard dependency on that module.
    """

    document_id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Citation:
    """Citation selected for inclusion in the final answer."""

    document_id: str
    route: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class CompiledAnswer:
    """Container returning the answer text along with selected citations."""

    answer: str
    citations: Sequence[Citation]


class ResponseCompiler:
    """Select top sources and attach routing metadata for the final answer."""

    def __init__(
        self,
        *,
        max_citations: int = 3,
        route_keys: Sequence[str] | None = None,
    ) -> None:
        if max_citations <= 0:
            raise ValueError("max_citations must be greater than zero")

        self.max_citations = max_citations
        self.route_keys = tuple(route_keys or ("route", "retriever", "source"))

    def compile(
        self,
        *,
        answer: str,
        documents: Sequence[RetrievedDocument],
    ) -> CompiledAnswer:
        citations = tuple(self.select_citations(documents))
        return CompiledAnswer(answer=answer, citations=citations)

    def select_citations(
        self, documents: Sequence[RetrievedDocument]
    ) -> Iterable[Citation]:
        """Yield citations ordered by fused score and filtered to top-N."""

        sorted_documents = sorted(documents, key=lambda item: item.score, reverse=True)
        seen: set[str] = set()

        for document in sorted_documents:
            if document.document_id in seen:
                continue

            route = self._resolve_route(document.metadata)
            citation = Citation(
                document_id=document.document_id,
                route=route,
                score=document.score,
                metadata=dict(document.metadata),
            )
            yield citation

            seen.add(document.document_id)
            if len(seen) >= self.max_citations:
                break

    def _resolve_route(self, metadata: Mapping[str, Any]) -> str:
        for key in self.route_keys:
            value = metadata.get(key)
            if value:
                return str(value)
        return "unknown"
