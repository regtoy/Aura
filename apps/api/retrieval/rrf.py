from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Iterable, Mapping, MutableMapping, Sequence


@dataclass(slots=True)
class ScoredDocument:
    """Single retrieval result with metadata."""

    document_id: str
    score: float
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class FusedDocument:
    """Document enriched with the fused score and contributing evidence."""

    document_id: str
    score: float
    metadata: Mapping[str, Any]
    contributions: Sequence[ScoredDocument]


def reciprocal_rank_fusion(
    result_sets: Sequence[Sequence[ScoredDocument]],
    *,
    k: int = 60,
    limit: int | None = None,
    weights: Sequence[float] | None = None,
) -> list[FusedDocument]:
    """Combine ranked lists into a single ordering using Reciprocal Rank Fusion."""

    if not result_sets:
        return []

    if weights is not None and len(weights) != len(result_sets):
        raise ValueError("weights length must match the number of result sets")

    fused_scores: MutableMapping[str, float] = {}
    contributions: MutableMapping[str, list[ScoredDocument]] = {}

    for list_index, results in enumerate(result_sets):
        if not results:
            continue
        weight = weights[list_index] if weights is not None else 1.0
        for rank, result in enumerate(results, start=1):
            rr_score = weight / (k + rank)
            fused_scores[result.document_id] = fused_scores.get(result.document_id, 0.0) + rr_score
            contributions.setdefault(result.document_id, []).append(result)

    fused_documents: list[FusedDocument] = []
    for document_id, fused_score in fused_scores.items():
        merged_metadata = _merge_metadata(contributions.get(document_id, []))
        fused_documents.append(
            FusedDocument(
                document_id=document_id,
                score=fused_score,
                metadata=merged_metadata,
                contributions=tuple(contributions.get(document_id, [])),
            )
        )

    fused_documents.sort(key=lambda item: item.score, reverse=True)

    if limit is not None:
        fused_documents = fused_documents[:limit]

    return fused_documents


def _merge_metadata(documents: Iterable[ScoredDocument]) -> Mapping[str, Any]:
    merged: dict[str, Any] = {}
    for result in documents:
        for key, value in result.metadata.items():
            if key not in merged:
                merged[key] = value
            else:
                existing = merged[key]
                if isinstance(existing, list):
                    if value not in existing:
                        existing.append(value)
                elif existing != value:
                    merged[key] = [existing, value]
    return merged
