"""Primitive metric implementations used by the registry."""
from __future__ import annotations

from abc import ABC, abstractmethod
from collections import defaultdict
from contextlib import contextmanager
from dataclasses import dataclass
from threading import Lock
from time import perf_counter
from typing import Dict, Iterable, Iterator, Mapping, MutableMapping, Tuple

LabelValues = Tuple[str, ...]


class Metric(ABC):
    """Base class for concrete metric types."""

    def __init__(
        self, name: str, *, description: str = "", label_names: Iterable[str] | None = None
    ) -> None:
        self.name = name
        self.description = description
        self.label_names: Tuple[str, ...] = tuple(label_names or ())
        self._lock = Lock()

    def _normalise_labels(
        self, labels: Mapping[str, str] | None = None
    ) -> LabelValues:
        if not self.label_names:
            if labels:
                raise ValueError(f"Metric '{self.name}' does not accept labels")
            return ()
        if labels is None:
            raise ValueError(f"Metric '{self.name}' requires labels {self.label_names}")
        values = []
        for label in self.label_names:
            if label not in labels:
                raise ValueError(f"Missing label '{label}' for metric '{self.name}'")
            values.append(labels[label])
        return tuple(values)

    @abstractmethod
    def snapshot(self) -> Mapping[LabelValues, Mapping[str, float]]:
        """Return a snapshot of the metric values."""


class CounterMetric(Metric):
    """Simple counter metric."""

    def __init__(
        self, name: str, *, description: str = "", label_names: Iterable[str] | None = None
    ) -> None:
        super().__init__(name, description=description, label_names=label_names)
        self._values: MutableMapping[LabelValues, float] = defaultdict(float)

    def inc(self, amount: float = 1.0, *, labels: Mapping[str, str] | None = None) -> None:
        key = self._normalise_labels(labels)
        with self._lock:
            self._values[key] += amount

    def snapshot(self) -> Mapping[LabelValues, Mapping[str, float]]:
        with self._lock:
            return {key: {"value": value} for key, value in self._values.items()}


@dataclass
class DistributionStats:
    """Summary of observed values."""

    count: int = 0
    total: float = 0.0
    min: float | None = None
    max: float | None = None

    def observe(self, value: float) -> None:
        self.count += 1
        self.total += value
        self.min = value if self.min is None else min(self.min, value)
        self.max = value if self.max is None else max(self.max, value)

    def to_mapping(self) -> Mapping[str, float]:
        average = self.total / self.count if self.count else 0.0
        return {
            "count": float(self.count),
            "sum": self.total,
            "min": self.min if self.min is not None else 0.0,
            "max": self.max if self.max is not None else 0.0,
            "avg": average,
        }


class DistributionMetric(Metric):
    """Collect statistics for observed floating point values."""

    def __init__(
        self, name: str, *, description: str = "", label_names: Iterable[str] | None = None
    ) -> None:
        super().__init__(name, description=description, label_names=label_names)
        self._values: Dict[LabelValues, DistributionStats] = defaultdict(DistributionStats)

    def observe(self, value: float, *, labels: Mapping[str, str] | None = None) -> None:
        key = self._normalise_labels(labels)
        with self._lock:
            self._values[key].observe(value)

    def snapshot(self) -> Mapping[LabelValues, Mapping[str, float]]:
        with self._lock:
            return {key: stats.to_mapping() for key, stats in self._values.items()}


@contextmanager
def track_duration(metric: DistributionMetric, *, labels: Mapping[str, str] | None = None) -> Iterator[None]:
    """Context manager that records the duration into the provided metric."""

    start = perf_counter()
    try:
        yield
    finally:
        metric.observe(perf_counter() - start, labels=labels)
