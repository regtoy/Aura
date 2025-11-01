from __future__ import annotations

import asyncio
from dataclasses import dataclass
from typing import Any, Awaitable, Callable, Mapping, Protocol, Sequence


@dataclass(slots=True)
class QueryContext:
    """Metadata describing the retrieval request to guide expansion strategies."""

    language: str | None = None
    filters: Mapping[str, Any] | None = None
    top_k: int | None = None
    metadata: Mapping[str, Any] | None = None


class QueryExpansionStrategy(Protocol):
    """Protocol that individual query expansion strategies must follow."""

    async def expand(self, query: str, context: QueryContext | None = None) -> Sequence[str]:
        ...


def _normalize_query(text: str) -> str:
    return " ".join(text.split())


@dataclass(slots=True)
class QueryExpander:
    """Coordinator that combines multiple expansion strategies."""

    strategies: Sequence[QueryExpansionStrategy]
    max_expansions: int = 8
    include_original: bool = False

    async def expand(self, query: str, context: QueryContext | None = None) -> list[str]:
        normalized_query = _normalize_query(query)
        seen: set[str] = {normalized_query}
        expansions: list[str] = []

        for strategy in self.strategies:
            suggestions = await strategy.expand(normalized_query, context)
            for suggestion in suggestions:
                normalized = _normalize_query(suggestion)
                if not normalized or normalized in seen:
                    continue
                seen.add(normalized)
                expansions.append(normalized)
                if len(expansions) >= self.max_expansions:
                    return expansions

        if self.include_original and normalized_query not in expansions:
            expansions.insert(0, normalized_query)

        return expansions


@dataclass(slots=True)
class KeywordSynonymExpansionStrategy:
    """Simple heuristic expansion using predefined synonym dictionaries."""

    synonyms_map: Mapping[str, Sequence[str]]
    max_replacements_per_term: int = 2

    async def expand(self, query: str, context: QueryContext | None = None) -> Sequence[str]:
        tokens = query.split()
        expansions: list[str] = []

        for index, token in enumerate(tokens):
            synonyms = self.synonyms_map.get(token.lower())
            if not synonyms:
                continue
            limit = min(self.max_replacements_per_term, len(synonyms))
            for synonym in synonyms[:limit]:
                alternative = tokens.copy()
                alternative[index] = synonym
                expansions.append(" ".join(alternative))

        return expansions


@dataclass(slots=True)
class LLMQueryExpansionStrategy:
    """LLM-backed query expansion strategy with pluggable generator."""

    generator: Callable[[str, QueryContext | None], Awaitable[Sequence[str]] | Sequence[str]]
    max_suggestions: int = 5

    async def expand(self, query: str, context: QueryContext | None = None) -> Sequence[str]:
        result = self.generator(query, context)
        if asyncio.iscoroutine(result) or isinstance(result, Awaitable):
            suggestions = await result  # type: ignore[arg-type]
        else:
            suggestions = result

        normalized: list[str] = []
        for suggestion in suggestions:
            cleaned = _normalize_query(str(suggestion))
            if cleaned:
                normalized.append(cleaned)
            if len(normalized) >= self.max_suggestions:
                break
        return normalized


def build_default_synonym_strategy() -> KeywordSynonymExpansionStrategy:
    """Factory that returns a Turkish/English synonym-based expander."""

    synonyms_map: dict[str, Sequence[str]] = {
        "öğrenci": ["öğrenciler", "öğrenci başvuru"],
        "üniversite": ["kampüs", "yüksekokul"],
        "kayıt": ["kayıt işlemi", "kaydolma"],
        "burs": ["scholarship", "maddi destek"],
        "exam": ["examination", "test"],
        "course": ["lecture", "ders"],
    }
    return KeywordSynonymExpansionStrategy(synonyms_map=synonyms_map)
