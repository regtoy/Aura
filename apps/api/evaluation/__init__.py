"""Evaluation utilities including CRAG confidence scoring."""

from .crag import CallableScoreBackend, CRAGConfidenceEvaluator, ScoreBackend
from .types import CandidateAnswer, EvaluationResult

__all__ = [
    "CallableScoreBackend",
    "CRAGConfidenceEvaluator",
    "ScoreBackend",
    "CandidateAnswer",
    "EvaluationResult",
]
