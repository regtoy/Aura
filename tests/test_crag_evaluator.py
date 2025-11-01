import pytest

from app.evaluation import CallableScoreBackend, CRAGConfidenceEvaluator, CandidateAnswer
from app.services.confidence import ConfidenceStats, ConfidenceStatsRepository


class InMemoryConfidenceRepo(ConfidenceStatsRepository):
    def __init__(self):  # type: ignore[call-arg]
        self.stats = ConfidenceStats.with_default("retrieval", 0.6)

    async def ensure_metric(self, metric: str) -> ConfidenceStats:  # type: ignore[override]
        return self.stats

    async def record_outcome(self, metric: str, *, score: float, passed: bool) -> ConfidenceStats:  # type: ignore[override]
        self.stats = self.stats.updated(
            score=score,
            passed=passed,
            smoothing_factor=0.3,
            min_threshold=0.2,
            max_threshold=0.95,
        )
        return self.stats


@pytest.mark.asyncio
async def test_evaluate_updates_stats_and_metadata():
    backend = CallableScoreBackend(lambda question, context, answer: 0.75)
    repo = InMemoryConfidenceRepo()
    evaluator = CRAGConfidenceEvaluator(backend=backend, repository=repo)

    candidate = CandidateAnswer(
        question="Nedir?",
        context="Test bağlamı",
        answer="Bu bir cevaptır",
        metadata={"source": "kb"},
    )

    result = await evaluator.evaluate(candidate)

    assert result.score == pytest.approx(0.75)
    assert result.passed is True
    assert result.applied_threshold == pytest.approx(0.6)
    assert result.updated_threshold >= result.applied_threshold
    assert result.metadata["metric"] == "retrieval"
    assert result.metadata["passed"] is True


@pytest.mark.asyncio
async def test_batch_evaluate_returns_all_results():
    repo = InMemoryConfidenceRepo()
    scores = [0.55, 0.65, 0.9]

    class SequenceBackend:
        def __init__(self):
            self._index = 0

        def score(self, *, question: str, context: str, answer: str) -> float:
            value = scores[self._index]
            self._index += 1
            return value

    evaluator = CRAGConfidenceEvaluator(backend=SequenceBackend(), repository=repo)

    candidates = [
        CandidateAnswer(question="q1", context="c1", answer="a1"),
        CandidateAnswer(question="q2", context="c2", answer="a2"),
        CandidateAnswer(question="q3", context="c3", answer="a3"),
    ]

    results = await evaluator.batch_evaluate(candidates)

    assert len(results) == 3
    assert results[0].score == pytest.approx(0.55)
    assert results[1].score == pytest.approx(0.65)
    assert results[2].score == pytest.approx(0.9)
