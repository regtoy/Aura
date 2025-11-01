"""Reactive agent implementation with planning, action selection, and observation handling.

The module is designed around a simple ReAct (Reasoning + Acting) loop and
showcases how to build a maintainable agent architecture. Each public class is
accompanied by pseudo-code describing its usage to keep the documentation close
to the implementation.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Callable, Dict, Iterable, List, Optional, Protocol

from app.security.whitelist import WhitelistValidationError, whitelist_pre_run_hook

from app.metrics import MetricsRegistry, metrics_registry as default_metrics_registry

logger = logging.getLogger(__name__)


class Tool(Protocol):
    """Protocol describing callable tools available to the agent."""

    name: str

    def __call__(self, *args: Any, **kwargs: Any) -> Any:  # pragma: no cover - protocol
        ...


@dataclass
class AgentMemory:
    """State container used by :class:`ReactAgent`.

    Attributes
    ----------
    plan:
        The current high-level plan generated for the task.
    history:
        Chronological list of (thought, action, observation) tuples.
    scratchpad:
        Free-form notes the agent keeps while reasoning.

    Pseudo-code
    -----------
    .. code-block:: text

        memory = AgentMemory()
        memory.update_plan([...])
        memory.record_step(thought="Need weather", action="call weather_tool", observation="sunny")
        memory.scratchpad.append("Remember umbrella")
    """

    plan: List[str] = field(default_factory=list)
    history: List[Dict[str, Any]] = field(default_factory=list)
    scratchpad: List[str] = field(default_factory=list)

    def update_plan(self, steps: Iterable[str]) -> None:
        """Persist a new plan while logging the change."""

        self.plan = list(steps)
        logger.debug("Plan updated: %s", self.plan)

    def record_step(self, *, thought: str, action: str, observation: str) -> None:
        """Record a single reasoning/acting loop iteration."""

        entry = {
            "thought": thought,
            "action": action,
            "observation": observation,
        }
        logger.debug("Recording step: %s", entry)
        self.history.append(entry)


class Planner:
    """Generate a high-level plan for the given task description.

    Pseudo-code
    -----------
    .. code-block:: text

        planner = Planner()
        plan = planner.create_plan("Book a flight")
        # plan -> ["Search flights", "Compare prices", "Select best option"]
    """

    def create_plan(self, task_description: str) -> List[str]:
        """Create a simple plan by splitting the task description."""

        logger.info("Creating plan for task: %s", task_description)
        if not task_description.strip():
            raise ValueError("Task description cannot be empty.")
        steps = [step.strip() for step in task_description.split(" and ") if step.strip()]
        if not steps:
            steps = [task_description.strip()]
        logger.debug("Generated plan: %s", steps)
        return steps


class ToolSelector:
    """Select the best tool for the current plan step.

    Pseudo-code
    -----------
    .. code-block:: text

        selector = ToolSelector([weather_tool, travel_tool])
        tool = selector.pick_tool("Check weather")
        # -> returns weather_tool or raises ToolNotFoundError
    """

    def __init__(self, tools: Iterable[Tool]):
        self._tools: Dict[str, Tool] = {tool.name: tool for tool in tools}
        logger.debug("Registered tools: %s", list(self._tools))

    def pick_tool(self, instruction: str) -> Tool:
        """Choose a tool based on keywords in the instruction."""

        logger.info("Selecting tool for instruction: %s", instruction)
        for name, tool in self._tools.items():
            if name.lower() in instruction.lower():
                logger.debug("Selected tool '%s' for instruction '%s'", name, instruction)
                return tool
        raise ToolNotFoundError(instruction, available=list(self._tools))


class ObservationProcessor:
    """Post-process tool outputs before they are stored in memory.

    Pseudo-code
    -----------
    .. code-block:: text

        processor = ObservationProcessor()
        clean = processor.process(raw_observation)
        # -> normalize strings, truncate long outputs, etc.
    """

    def process(self, observation: Any) -> str:
        """Normalize observations to a human-readable string."""

        if observation is None:
            logger.warning("Received empty observation")
            return "No observation"
        if isinstance(observation, str):
            normalized = observation.strip()
        else:
            normalized = str(observation)
        logger.debug("Processed observation: %s", normalized)
        return normalized


class ToolExecutionError(RuntimeError):
    """Raised when a tool fails during execution."""


class ToolNotFoundError(LookupError):
    """Raised when no registered tool matches the instruction."""

    def __init__(self, instruction: str, *, available: Optional[List[str]] = None) -> None:
        message = f"No tool found for instruction: {instruction}"
        if available:
            message += f". Available tools: {', '.join(available)}"
        super().__init__(message)
        self.instruction = instruction
        self.available = available or []


PreRunHook = Callable[[str], None]


class ReactAgent:
    """High-level agent that orchestrates planning, acting, and observing.

    Pseudo-code
    -----------
    .. code-block:: text

        agent = ReactAgent(planner, selector, processor, memory)
        result = agent.run("Collect project status and summarize")

        while agent.has_more_steps():
            agent.step()

    The class also exposes hooks for debugging and integrates detailed logging
    for traceability. Errors are caught and reported while keeping the agent
    state consistent.
    """

    def __init__(
        self,
        planner: Planner,
        tool_selector: ToolSelector,
        observation_processor: ObservationProcessor,
        memory: Optional[AgentMemory] = None,
        *,
        max_steps: int = 10,
        pre_run_hooks: Optional[Iterable[PreRunHook]] = None,
        metrics: Optional[MetricsRegistry] = None,
    ) -> None:
        self.planner = planner
        self.tool_selector = tool_selector
        self.observation_processor = observation_processor
        self.memory = memory or AgentMemory()
        self.max_steps = max_steps
        self._current_step = 0
        self._current_instruction: Optional[str] = None
        self._finished = False
        self._pre_run_hooks: List[PreRunHook] = list(pre_run_hooks or [])
        self.metrics = metrics or default_metrics_registry

        if whitelist_pre_run_hook not in self._pre_run_hooks:
            self._pre_run_hooks.append(whitelist_pre_run_hook)

    def add_pre_run_hook(self, hook: PreRunHook) -> None:
        """Register a hook executed before the workflow starts."""

        self._pre_run_hooks.append(hook)

    def _run_pre_run_hooks(self, task_description: str) -> None:
        for hook in self._pre_run_hooks:
            hook(task_description)

    def run(self, task_description: str) -> List[Dict[str, Any]]:
        """Run the agent loop until completion.

        The method generates a plan and iterates over the steps, selecting and
        executing tools while storing the results in the agent memory.
        """

        logger.info("Agent run started with task: %s", task_description)
        run_start = perf_counter()
        self.metrics.counter("react_agent_runs_total").inc()
        try:
            self._run_pre_run_hooks(task_description)
        except WhitelistValidationError:
            logger.error("Whitelist validation failed for task: %s", task_description)
            self.metrics.counter("react_agent_run_failures_total").inc()
            self.metrics.counter("react_agent_whitelist_failures_total").inc()
            raise
        except Exception:  # pragma: no cover - defensive
            logger.exception("Pre-run hook failed for task: %s", task_description)
            self.metrics.counter("react_agent_run_failures_total").inc()
            raise
        try:
            self.memory.update_plan(self.planner.create_plan(task_description))
            for instruction in self.memory.plan:
                if self._current_step >= self.max_steps:
                    logger.warning("Max steps reached; stopping execution")
                    break
                self._execute_instruction(instruction)
            self._finished = True
            logger.info("Agent run completed after %d steps", self._current_step)
            return self.memory.history
        except Exception:
            self.metrics.counter("react_agent_run_failures_total").inc()
            raise
        finally:
            self.metrics.distribution("react_agent_run_duration_seconds").observe(
                perf_counter() - run_start
            )

    def step(self) -> Optional[Dict[str, Any]]:
        """Advance the agent by a single step.

        This method is useful when the caller needs fine-grained control over
        execution and logging. It returns the recorded step or ``None`` when the
        plan has been fully processed.
        """

        if self._finished:
            logger.debug("Agent already finished; no more steps")
            return None
        if not self.memory.plan:
            raise RuntimeError("No plan available; call run() first or provide a plan.")
        if self._current_step >= len(self.memory.plan):
            self._finished = True
            logger.debug("All plan steps executed")
            return None
        instruction = self.memory.plan[self._current_step]
        return self._execute_instruction(instruction)

    def has_more_steps(self) -> bool:
        """Return whether there are remaining steps to execute."""

        return not self._finished and self._current_step < len(self.memory.plan)

    def _execute_instruction(self, instruction: str) -> Dict[str, Any]:
        """Execute a single instruction from the plan."""

        self._current_instruction = instruction
        thought = f"Considering: {instruction}"
        logger.debug("Step %d thought: %s", self._current_step + 1, thought)
        step_start = perf_counter()
        tool_label = {"tool": "unknown"}
        try:
            tool = self.tool_selector.pick_tool(instruction)
            tool_label = {"tool": tool.name}
            raw_result = tool(instruction)
        except ToolNotFoundError:
            logger.exception("Tool selection failed")
            observation = self.observation_processor.process("No suitable tool")
            self.memory.record_step(thought=thought, action="none", observation=observation)
            self._current_step += 1
            failure_labels = {"tool": "unmatched"}
            self.metrics.counter("react_agent_tool_failures_total").inc(labels=failure_labels)
            self.metrics.distribution("react_agent_step_duration_seconds").observe(
                perf_counter() - step_start,
                labels=failure_labels,
            )
            self.metrics.counter("react_agent_steps_total").inc()
            return self.memory.history[-1]
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Unexpected error during tool selection")
            self.metrics.counter("react_agent_tool_failures_total").inc(labels=tool_label)
            self.metrics.distribution("react_agent_step_duration_seconds").observe(
                perf_counter() - step_start,
                labels=tool_label,
            )
            raise ToolExecutionError("Failed during tool selection") from exc

        try:
            observation = self.observation_processor.process(raw_result)
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Observation processing failed")
            self.metrics.counter("react_agent_tool_failures_total").inc(labels=tool_label)
            self.metrics.distribution("react_agent_step_duration_seconds").observe(
                perf_counter() - step_start,
                labels=tool_label,
            )
            raise ToolExecutionError("Observation processing failed") from exc

        self.memory.record_step(thought=thought, action=tool.name, observation=observation)
        self._current_step += 1
        logger.info("Step %d completed with tool '%s'", self._current_step, tool.name)
        self.metrics.counter("react_agent_tool_success_total").inc(labels=tool_label)
        self.metrics.distribution("react_agent_step_duration_seconds").observe(
            perf_counter() - step_start,
            labels=tool_label,
        )
        self.metrics.counter("react_agent_steps_total").inc()
        return self.memory.history[-1]


def default_agent_factory(tools: Iterable[Tool], *, max_steps: int = 10) -> ReactAgent:
    """Helper function returning a :class:`ReactAgent` with default components."""

    planner = Planner()
    selector = ToolSelector(tools)
    processor = ObservationProcessor()
    memory = AgentMemory()
    return ReactAgent(planner, selector, processor, memory, max_steps=max_steps)
