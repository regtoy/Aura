"""Adapters for exporting metrics to external monitoring systems."""
from __future__ import annotations

import http.client
import json
import logging
from typing import MutableMapping
from urllib.parse import urlparse

from .base import CounterMetric
from .registry import MetricsRegistry

logger = logging.getLogger(__name__)


class MetricsExporter:
    """Base class for metrics exporters."""

    def __init__(self, registry: MetricsRegistry | None = None) -> None:
        self.registry = registry or MetricsRegistry()

    def build_payload(self) -> str:  # pragma: no cover - interface
        """Create a serialised representation of the current metrics."""

        raise NotImplementedError

    def export(self) -> str:
        """Return the serialised payload (hook for tests or logging)."""

        payload = self.build_payload()
        logger.debug("Generated metrics payload: %s", payload)
        return payload


class PrometheusExporter(MetricsExporter):
    """Generate Prometheus compatible text format output."""

    def build_payload(self) -> str:
        lines: list[str] = []
        for metric in self.registry.metrics():
            metric_type = "counter" if isinstance(metric, CounterMetric) else "summary"
            lines.append(f"# HELP {metric.name} {metric.description}")
            lines.append(f"# TYPE {metric.name} {metric_type}")
            for labels, values in metric.snapshot().items():
                label_text = ""
                if labels:
                    label_pairs = [
                        f"{name}=\"{value}\"" for name, value in zip(metric.label_names, labels)
                    ]
                    label_text = "{" + ",".join(label_pairs) + "}"  # noqa: P103
                if "value" in values:
                    lines.append(f"{metric.name}{label_text} {values['value']}")
                else:
                    lines.append(f"{metric.name}_count{label_text} {values['count']}")
                    lines.append(f"{metric.name}_sum{label_text} {values['sum']}")
        return "\n".join(lines)

    def push_to_gateway(self, endpoint: str, timeout: int = 5) -> None:
        """Push metrics to a Prometheus push gateway compatible endpoint."""

        payload = self.build_payload()
        parsed = urlparse(endpoint)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("Only HTTP(S) endpoints are supported for Prometheus push gateways")
        connection_class = http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
        connection = connection_class(parsed.netloc, timeout=timeout)
        try:
            path = parsed.path or "/metrics"
            connection.request(
                "POST",
                path,
                body=payload.encode("utf-8"),
                headers={"Content-Type": "text/plain"},
            )
            response = connection.getresponse()
            if response.status >= 400:
                raise RuntimeError(
                    f"Push gateway returned {response.status}: {response.read().decode('utf-8')}"
                )
            logger.info("Pushed metrics to %s", endpoint)
        finally:
            connection.close()


class ElasticsearchExporter(MetricsExporter):
    """Generate Elasticsearch/ELK bulk API compatible payload."""

    def __init__(
        self,
        registry: MetricsRegistry | None = None,
        *,
        index_name: str = "aura-metrics",
    ) -> None:
        super().__init__(registry)
        self.index_name = index_name

    def build_payload(self) -> str:
        lines: list[str] = []
        for metric in self.registry.metrics():
            snapshot = metric.snapshot()
            for label_values, values in snapshot.items():
                metadata = {"index": {"_index": self.index_name}}
                document: MutableMapping[str, object] = {
                    "metric": metric.name,
                    "labels": dict(zip(metric.label_names, label_values)) if label_values else {},
                    "values": values,
                }
                lines.append(json.dumps(metadata))
                lines.append(json.dumps(document))
        return "\n".join(lines) + ("\n" if lines else "")

    def export(self) -> str:
        payload = self.build_payload()
        logger.debug("Generated Elasticsearch payload for index '%s'", self.index_name)
        return payload
