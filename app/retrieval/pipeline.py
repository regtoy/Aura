from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Awaitable, Protocol, Sequence

from .query_expansion import QueryContext, QueryExpander
from .rrf import FusedDocument, ScoredDocument, reciprocal_rank_fusion
from .types import RetrievalResult


class Retriever(Protocol):
    async def retrieve(self, query: str, *, top_k: int) -> Sequence[RetrievalResult]:
        ...


def _maybe_await(value: Awaitable[Sequence[RetrievalResult]] | Sequence[RetrievalResult]) -> Awaitable[Sequence[RetrievalResult]]:
    if asyncio.iscoroutine(value) or isinstance(value, Awaitable):
        return value  # type: ignore[return-value]

    async def _wrapper() -> Sequence[RetrievalResult]:
        return value

    return _wrapper()


@dataclass(slots=True)
class RetrieverConfig:
    name: str
    retriever: Retriever
    weight: float = 1.0


class RAGFusionPipeline:
    """Pipeline that performs query expansion, multi-retriever querying and RRF fusion."""

    def __init__(
        self,
        query_expander: QueryExpander | None,
        retrievers: Sequence[RetrieverConfig],
        *,
        rrf_k: int = 60,
        per_retriever_limit: int = 8,
    ) -> None:
        if not retrievers:
            raise ValueError("At least one retriever must be provided")

        self.query_expander = query_expander
        self.retrievers = retrievers
        self.rrf_k = rrf_k
        self.per_retriever_limit = per_retriever_limit

    async def retrieve(
        self,
        query: str,
        *,
        top_k: int = 5,
        context: QueryContext | None = None,
        use_expansion: bool = True,
    ) -> list[FusedDocument]:
        context = context or QueryContext()
        queries = [query]

        if use_expansion and self.query_expander is not None:
            expansions = await self.query_expander.expand(query, context)
            queries.extend(expansions)

        result_lists: list[Sequence[ScoredDocument]] = []
        weights: list[float] = []

        for retriever_config in self.retrievers:
            for query_variant in queries:
                retrieval = retriever_config.retriever.retrieve(query_variant, top_k=self.per_retriever_limit)
                results = await _maybe_await(retrieval)
                if not results:
                    continue
                scored = [
                    ScoredDocument(
                        document_id=item.document_id,
                        score=item.score,
                        metadata={
                            **dict(item.metadata),
                            "retriever": retriever_config.name,
                            "query_variant": query_variant,
                        },
                    )
                    for item in results
                ]
                result_lists.append(scored)
                weights.append(retriever_config.weight)

        fused = reciprocal_rank_fusion(result_lists, k=self.rrf_k, limit=top_k, weights=weights or None)
        return fused
