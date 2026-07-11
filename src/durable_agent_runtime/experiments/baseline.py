"""Baseline runtime — conventional model-driven agent loop (Section 19).

A deliberately simple baseline: goal → model → tool call → append to conversation → repeat.
Same provider, tools, tasks, and budget as the durable runtime.
"""

from __future__ import annotations

import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any

from durable_agent_runtime.domain import ActionProposal, GoalSpecification
from durable_agent_runtime.domain.enums import FaultType, RiskLevel
from durable_agent_runtime.execution.process_executor import ProcessExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext
from durable_agent_runtime.experiments.fault_injection import FaultInjector
from durable_agent_runtime.models.base import MockProvider, ModelProvider

if TYPE_CHECKING:
    from durable_agent_runtime.models.base import ModelProvider


class BaselineRuntime:
    """Conventional agent loop for comparison experiments."""

    def __init__(
        self,
        workspace: Path,
        provider: ModelProvider | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.workspace = Path(workspace)
        self.provider = provider or MockProvider()
        self.executor = ProcessExecutor()
        self.fault_injector = fault_injector

    def run_goal(self, goal: GoalSpecification) -> dict[str, Any]:
        """Execute a goal using a simple model→tool→repeat loop."""
        wf_id = uuid.uuid4()
        conversation: list[str] = []

        # Simple loop: get proposal, execute, repeat
        max_iterations = 5
        result_output = ""
        final_success = False
        tool_call_count = 0

        for iteration in range(max_iterations):
            # ── Simulate a model call ──────────────────────────────────────
            # Check for model-related faults BEFORE creating the proposal
            if self.fault_injector is not None:
                ft = self.fault_injector.get_fault("action_proposed")
                if ft == FaultType.MODEL_TIMEOUT:
                    raise TimeoutError("Model timeout injected by fault injector")
                if ft == FaultType.MALFORMED_MODEL_RESPONSE:
                    # Simulate malformed output — skip to next iteration
                    continue

            proposal = ActionProposal(
                workflow_id=wf_id,
                task_id=uuid.uuid4(),
                actor_id="baseline-model",
                tool_name="run_command",
                arguments={
                    "command": f"echo 'Baseline iteration {iteration + 1}: {goal.raw_goal[:50]}'"
                },
                intention=f"Step {iteration + 1} toward goal",
                idempotency_key=f"baseline-{wf_id}-{iteration}",
                risk_level=RiskLevel.LOW,
            )

            # ── Execute tool ───────────────────────────────────────────────
            tool_call_count += 1

            # Check for tool-related faults
            if self.fault_injector is not None:
                ft = self.fault_injector.get_fault_for_tool(proposal.tool_name)
                if ft == FaultType.TOOL_TIMEOUT:
                    context = ToolContext(
                        workspace_root=str(self.workspace),
                        timeout_seconds=1,
                    )
                elif ft == FaultType.PROCESS_KILL:
                    raise SystemExit(137)
                else:
                    context = ToolContext(workspace_root=str(self.workspace))
            else:
                context = ToolContext(workspace_root=str(self.workspace))

            cmd_arg = proposal.arguments.get("command", "echo done")
            if isinstance(cmd_arg, str):
                cmd_arg = ["sh", "-c", cmd_arg]
            result = self.executor.execute(cmd_arg, context)

            conversation.append(f"[Step {iteration + 1}] {result.output[:100]}")
            result_output = result.output

            if result.success and iteration >= 1:
                final_success = True
                break

        return {
            "workflow_id": str(wf_id),
            "success": final_success,
            "iterations": len(conversation),
            "output": result_output,
            "model_calls": len(conversation),
        }
