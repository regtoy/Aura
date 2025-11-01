from __future__ import annotations

import inspect
from dataclasses import dataclass
from typing import Awaitable, Protocol, Sequence

from .types import CandidateAnswer, EvaluationResult
from apps.api.services.confidence import ConfidenceStatsRepository


class ScoreBackend(Protocol):
    """Protocol describing the scoring backend used for CRAG evaluation."""

    def score(self, *, question: str, context: str, answer: str) -> Awaitable[float] | float:
        """Return a confidence score for the provided triplet."""


@dataclass(slots=True)
class CallableScoreBackend:
    """Adapter that turns a synchronous callable into a scoring backend."""

    func: callable

    def score(self, *, question: str, context: str, answer: str) -> float:
        return float(self.func(question=question, context=context, answer=answer))


class CRAGConfidenceEvaluator:
    """CRAG evaluator that leverages a scoring backend and adaptive thresholds."""

    def __init__(
        self,
        *,
        backend: ScoreBackend,
        repository: ConfidenceStatsRepository,
        metric: str = "retrieval",
    ) -> None:
        self._backend = backend
        self._repository = repository
        self._metric = metric

    async def _call_backend(self, candidate: CandidateAnswer) -> float:
        result = self._backend.score(
            question=candidate.question,
            context=candidate.context,
            answer=candidate.answer,
        )
        if inspect.isawaitable(result):
            value = await result  # type: ignore[assignment]
        else:
            value = result
        return float(value)

    async def evaluate(self, candidate: CandidateAnswer, *, update_stats: bool = True) -> EvaluationResult:
        """Evaluate a single candidate answer and update confidence stats."""

        stats_before = await self._repository.ensure_metric(self._metric)
        threshold_before = stats_before.rolling_threshold
        score = await self._call_backend(candidate)
        passed = score >= threshold_before

        if update_stats:
            stats_after = await self._repository.record_outcome(
                self._metric, score=score, passed=passed
            )
        else:
            stats_after = stats_before

        metadata = dict(candidate.metadata)
        metadata.update({"metric": self._metric, "passed": passed})

        return EvaluationResult(
            candidate=candidate,
            score=score,
            passed=passed,
            applied_threshold=threshold_before,
            updated_threshold=stats_after.rolling_threshold,
            metadata=metadata,
        )

    async def batch_evaluate(
        self, candidates: Sequence[CandidateAnswer], *, update_stats: bool = True
    ) -> list[EvaluationResult]:
        """Evaluate multiple candidates sequentially, updating stats per item."""

        results: list[EvaluationResult] = []
        for candidate in candidates:
            results.append(await self.evaluate(candidate, update_stats=update_stats))
        return results
