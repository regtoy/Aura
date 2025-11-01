import logging
from typing import Iterable

import pytest

from apps.api.agents.react_agent import AgentMemory, ObservationProcessor, Planner, ReactAgent, ToolSelector
from apps.api.security.whitelist import (
    WhitelistValidationError,
    extract_domains,
    validate_task_description,
)


class DummyTool:
    name = "dummy"

    def __call__(self, instruction: str) -> str:  # pragma: no cover - simple stub
        return f"processed: {instruction}"


def _build_agent(*, hooks: Iterable = ()):  # pragma: no cover - helper for tests
    tools = [DummyTool()]
    selector = ToolSelector(tools)
    processor = ObservationProcessor()
    memory = AgentMemory()
    return ReactAgent(Planner(), selector, processor, memory, pre_run_hooks=list(hooks))


def test_validate_task_description_allows_whitelisted_domains():
    validate_task_description(
        "Collect information from https://docs.python.org/3/tutorial/",
        allowed_domains=("docs.python.org",),
    )


def test_validate_task_description_supports_wildcard_domains():
    validate_task_description(
        "Visit https://sub.example.com/page",
        allowed_domains=("*.example.com",),
    )


def test_validate_task_description_raises_for_disallowed_domains(caplog):
    caplog.set_level(logging.ERROR)
    with pytest.raises(WhitelistValidationError) as exc:
        validate_task_description(
            "Summarise https://forbidden.example",
            allowed_domains=("allowed.example",),
        )
    assert "forbidden.example" in str(exc.value)
    assert "allowed.example" in str(exc.value)
    assert "forbidden.example" in caplog.text


def test_extract_domains_handles_www_prefix():
    domains = extract_domains("Check www.example.com and https://www.test.dev")
    assert domains == ["example.com", "test.dev"]


def test_react_agent_enforces_whitelist_on_run(monkeypatch, caplog):
    caplog.set_level(logging.ERROR)
    monkeypatch.setenv("AURA_WHITELIST", "trusted.example")
    agent = _build_agent()
    with pytest.raises(WhitelistValidationError):
        agent.run("Fetch https://malicious.example for data")
    assert "malicious.example" in caplog.text


def test_react_agent_allows_configured_domains(monkeypatch):
    monkeypatch.setenv("AURA_WHITELIST", "trusted.example")
    agent = _build_agent()
    history = agent.run("Fetch https://trusted.example/resource")
    assert history
