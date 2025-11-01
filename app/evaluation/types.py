from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(slots=True)
class CandidateAnswer:
    """Input payload that will be evaluated by the CRAG model."""

    question: str
    context: str
    answer: str
    metadata: Mapping[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class EvaluationResult:
    """Result of the CRAG evaluation, including thresholds."""

    candidate: CandidateAnswer
    score: float
    passed: bool
    applied_threshold: float
    updated_threshold: float
    metadata: Mapping[str, Any] = field(default_factory=dict)
