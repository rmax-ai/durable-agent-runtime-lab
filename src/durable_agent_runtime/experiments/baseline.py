"""Baseline runtime — conventional model-driven agent loop (Section 19).

A deliberately simple baseline: goal → model → tool call → append to conversation → repeat.
Same provider, tools, tasks, and budget as the durable runtime.
"""

import uuid
from pathlib import Path

from durable_agent_runtime.domain import ActionProposal, GoalSpecification
from durable_agent_runtime.domain.enums import RiskLevel
from durable_agent_runtime.execution.process_executor import ProcessExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext
from durable_agent_runtime.models.base import MockProvider


class BaselineRuntime:
    """Conventional agent loop for comparison experiments."""

    def __init__(self, workspace: Path) -> None:
        self.workspace = Path(workspace)
        self.provider = MockProvider()
        self.executor = ProcessExecutor()

    def run_goal(self, goal: GoalSpecification) -> dict:
        """Execute a goal using a simple model→tool→repeat loop."""
        wf_id = uuid.uuid4()
        conversation: list[str] = []

        # Simple loop: get proposal, execute, repeat
        max_iterations = 5
        result_output = ""
        final_success = False

        for iteration in range(max_iterations):
            # Model proposes an action
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

            # Execute directly (no verification boundary)
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
