"""Simple in-memory metrics registry."""
from __future__ import annotations

from contextlib import contextmanager
from threading import Lock
from typing import Dict, Iterable, Iterator, Mapping, MutableMapping, Tuple

from .base import CounterMetric, DistributionMetric, Metric, track_duration


class MetricsRegistry:
    """Registry that holds metric instances and offers helper utilities."""

    def __init__(self) -> None:
        self._metrics: MutableMapping[str, Metric] = {}
        self._lock = Lock()

    def _get_or_create(self, name: str, factory) -> Metric:
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = factory()
            return self._metrics[name]

    def counter(
        self,
        name: str,
        *,
        description: str = "",
        label_names: Iterable[str] | None = None,
    ) -> CounterMetric:
        metric = self._get_or_create(
            name,
            lambda: CounterMetric(name, description=description, label_names=label_names),
        )
        if not isinstance(metric, CounterMetric):
            raise TypeError(f"Metric '{name}' already exists with a different type")
        return metric

    def distribution(
        self,
        name: str,
        *,
        description: str = "",
        label_names: Iterable[str] | None = None,
    ) -> DistributionMetric:
        metric = self._get_or_create(
            name,
            lambda: DistributionMetric(name, description=description, label_names=label_names),
        )
        if not isinstance(metric, DistributionMetric):
            raise TypeError(f"Metric '{name}' already exists with a different type")
        return metric

    def metrics(self) -> Tuple[Metric, ...]:
        with self._lock:
            return tuple(self._metrics.values())

    def snapshot(self) -> Dict[str, Mapping[Tuple[str, ...], Mapping[str, float]]]:
        """Return a serialisable snapshot of all registered metrics."""

        with self._lock:
            return {name: metric.snapshot() for name, metric in self._metrics.items()}

    @contextmanager
    def time_distribution(
        self,
        name: str,
        *,
        description: str = "",
        label_names: Iterable[str] | None = None,
        labels: Mapping[str, str] | None = None,
    ) -> Iterator[None]:
        metric = self.distribution(name, description=description, label_names=label_names)
        with track_duration(metric, labels=labels):
            yield
