"""Application wide metrics utilities."""
from .registry import MetricsRegistry
from .definitions import DEFAULT_METRIC_DEFINITIONS, MetricDefinition

metrics_registry = MetricsRegistry()


def register_default_metrics(registry: MetricsRegistry | None = None) -> None:
    """Ensure all default metric definitions exist in the registry."""
    target = registry or metrics_registry
    for definition in DEFAULT_METRIC_DEFINITIONS:
        if definition.metric_type == "counter":
            target.counter(
                definition.name,
                description=definition.description,
                label_names=definition.label_names,
            )
        elif definition.metric_type == "distribution":
            target.distribution(
                definition.name,
                description=definition.description,
                label_names=definition.label_names,
            )
        else:  # pragma: no cover - defensive
            raise ValueError(f"Unsupported metric type: {definition.metric_type}")


# eagerly register the defaults for convenience
register_default_metrics()

__all__ = [
    "MetricDefinition",
    "MetricsRegistry",
    "metrics_registry",
    "register_default_metrics",
]
