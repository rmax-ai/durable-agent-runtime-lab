"""Baseline runtime — conventional model-driven agent loop (Section 19).

A deliberately simple baseline: goal → model → tool call → append to conversation → repeat.
Same provider, tools, tasks, and budget as the durable runtime.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import Any

from durable_agent_runtime.domain import ActionProposal, GoalSpecification
from durable_agent_runtime.domain.enums import FaultType, RiskLevel
from durable_agent_runtime.execution.process_executor import ProcessExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext
from durable_agent_runtime.experiments.fault_injection import FaultInjector
from durable_agent_runtime.models.base import MockProvider, ModelProvider, ModelRequest


class BaselineRuntime:
    """Conventional agent loop for comparison experiments.

    Uses the model provider to propose actions iteratively, building up
    a conversation history with each step's command + output.
    """

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

    # ── Public entry point ──────────────────────────────────────────────────

    def run_goal(self, goal: GoalSpecification) -> dict[str, Any]:
        """Execute a goal using a simple model→tool→repeat loop."""
        wf_id = uuid.uuid4()
        conversation: list[str] = []

        max_iterations = 5
        result_output = ""
        final_success = False
        tool_call_count = 0
        model_call_count = 0
        last_model_error = ""

        for iteration in range(max_iterations):
            # ── Ask the model to propose an action ──────────────────────────
            step_number = iteration + 1

            # Check for model-related faults BEFORE creating the proposal
            if self.fault_injector is not None:
                ft = self.fault_injector.get_fault("action_proposed")
                if ft == FaultType.MODEL_TIMEOUT:
                    raise TimeoutError("Model timeout injected by fault injector")
                if ft == FaultType.MALFORMED_MODEL_RESPONSE:
                    continue

            model_call_count += 1
            try:
                with asyncio.Runner() as runner:
                    proposal = runner.run(
                        self._propose_action(wf_id, goal, conversation, step_number)
                    )
            except (TimeoutError, Exception) as exc:
                # Skip this iteration on model failure, try again
                last_model_error = f"Model proposal failed: {exc}"
                continue

            # If the model says we're done and has already achieved the goal
            # we can exit early — but still execute the terminal command
            is_terminal = proposal.metadata.get("is_terminal", False)

            tool_call_count += 1

            # ── Execute tool ────────────────────────────────────────────────
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

            # Append to conversation history
            step_summary = (
                f"[Step {step_number}] {proposal.intention} "
                f"→ {'OK' if result.success else 'FAIL'}: "
                f"{result.output[:120] if result.output else result.error[:120]}"
            )
            conversation.append(step_summary)
            result_output = result.output

            # ── Decide whether to continue ──────────────────────────────────
            if result.success and is_terminal:
                final_success = True
                break

        return {
            "workflow_id": str(wf_id),
            "success": final_success,
            "iterations": len(conversation),
            "output": result_output,
            "error": "" if final_success else last_model_error,
            "model_calls": model_call_count,
            "tool_calls": tool_call_count,
            "conversation": conversation,
        }

    # ── Internal: model interaction ─────────────────────────────────────────

    async def _propose_action(
        self,
        wf_id: uuid.UUID,
        goal: GoalSpecification,
        conversation_history: list[str],
        step_number: int,
    ) -> ActionProposal:
        """Ask the model provider to propose the next action."""
        from durable_agent_runtime.models.prompts import ProposedAction, build_action_prompt

        system_prompt, user_prompt = build_action_prompt(
            goal_text=goal.normalized_goal,
            repository_path=goal.repository_path,
            tools=["run_command", "read_file", "write_file"],
            conversation_history=conversation_history if conversation_history else None,
            step_number=step_number,
        )

        request = ModelRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model_name="ProposedAction",
        )

        response = await self.provider.generate_structured(request, ProposedAction)
        action_data = response.content

        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }

        tool_name = action_data.get("tool_name", "run_command")
        arguments: dict[str, Any] = {}
        if tool_name == "run_command":
            arguments["command"] = action_data.get("command", "echo done")
        elif tool_name == "read_file":
            arguments["path"] = action_data.get("command", ".")
        elif tool_name == "write_file":
            arguments["path"] = action_data.get("command", "")
            arguments["content"] = action_data.get("file_content", "")
        else:
            arguments["command"] = action_data.get("command", "echo done")

        return ActionProposal(
            workflow_id=wf_id,
            task_id=uuid.uuid4(),
            actor_id=f"{getattr(self.provider, 'name', 'model')}-baseline-{step_number}",
            tool_name=tool_name,
            arguments=arguments,
            intention=action_data.get("intention", f"Step {step_number} toward goal"),
            expected_effects=action_data.get("expected_effects", []),
            idempotency_key=f"baseline-{wf_id}-{step_number}",
            risk_level=risk_map.get(
                action_data.get("risk_level", "low"),
                RiskLevel.LOW,
            ),
            metadata={"is_terminal": action_data.get("is_terminal", False)},
        )
