"""Metric definitions used across the application."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Tuple


@dataclass(frozen=True)
class MetricDefinition:
    """Describe a metric that should exist in the registry."""

    name: str
    metric_type: str
    description: str
    label_names: Tuple[str, ...] = ()


DEFAULT_METRIC_DEFINITIONS: Tuple[MetricDefinition, ...] = (
    MetricDefinition(
        name="react_agent_runs_total",
        metric_type="counter",
        description="Total number of ReAct agent runs started.",
    ),
    MetricDefinition(
        name="react_agent_run_failures_total",
        metric_type="counter",
        description="Number of failed ReAct agent runs.",
    ),
    MetricDefinition(
        name="react_agent_run_duration_seconds",
        metric_type="distribution",
        description="Duration of ReAct agent runs in seconds.",
    ),
    MetricDefinition(
        name="react_agent_steps_total",
        metric_type="counter",
        description="Total number of steps executed by the ReAct agent.",
    ),
    MetricDefinition(
        name="react_agent_step_duration_seconds",
        metric_type="distribution",
        description="Duration of individual ReAct steps in seconds.",
        label_names=("tool",),
    ),
    MetricDefinition(
        name="react_agent_tool_failures_total",
        metric_type="counter",
        description="Number of tool execution failures in the ReAct workflow.",
        label_names=("tool",),
    ),
    MetricDefinition(
        name="react_agent_tool_success_total",
        metric_type="counter",
        description="Number of successful tool executions in the ReAct workflow.",
        label_names=("tool",),
    ),
    MetricDefinition(
        name="react_agent_whitelist_failures_total",
        metric_type="counter",
        description="Number of tasks rejected by whitelist validation.",
    ),
)
