"""Logging and tracing utilities for the Aura API."""

from __future__ import annotations

import logging
from logging.config import dictConfig

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from apps.api.core.config import Settings

_TRACER_INITIALISED = False


def _parse_headers(header_string: str | None) -> dict[str, str]:
    if not header_string:
        return {}
    headers: dict[str, str] = {}
    for item in header_string.split(","):
        if not item:
            continue
        if "=" not in item:
            continue
        key, value = item.split("=", 1)
        headers[key.strip()] = value.strip()
    return headers


def configure_logging(settings: Settings) -> logging.Logger:
    """Configure the application logger based on settings."""

    level = getattr(logging, settings.log_level.upper(), logging.INFO)
    dictConfig(
        {
            "version": 1,
            "disable_existing_loggers": False,
            "formatters": {
                "default": {
                    "format": settings.log_format,
                }
            },
            "handlers": {
                "default": {
                    "class": "logging.StreamHandler",
                    "formatter": "default",
                    "level": level,
                }
            },
            "root": {
                "handlers": ["default"],
                "level": level,
            },
        }
    )

    logger = logging.getLogger(settings.app_name)
    logger.setLevel(level)
    return logger


def init_tracer(settings: Settings) -> TracerProvider | None:
    """Initialise the OpenTelemetry tracer if enabled in settings."""

    global _TRACER_INITIALISED

    if _TRACER_INITIALISED or not settings.otel_enabled:
        return None

    resource = Resource(attributes={"service.name": settings.otel_service_name})
    provider = TracerProvider(resource=resource)

    exporter_kwargs: dict[str, object] = {}
    if settings.otel_exporter_otlp_endpoint:
        exporter_kwargs["endpoint"] = settings.otel_exporter_otlp_endpoint
    headers = _parse_headers(settings.otel_exporter_otlp_headers)
    if headers:
        exporter_kwargs["headers"] = headers

    exporter = OTLPSpanExporter(**exporter_kwargs)
    span_processor = BatchSpanProcessor(exporter)
    provider.add_span_processor(span_processor)

    trace.set_tracer_provider(provider)
    _TRACER_INITIALISED = True
    return provider


def shutdown_tracer(provider: TracerProvider | None) -> None:
    """Shut down the configured tracer provider."""

    if provider is None:
        return

    global _TRACER_INITIALISED
    provider.shutdown()
    _TRACER_INITIALISED = False

