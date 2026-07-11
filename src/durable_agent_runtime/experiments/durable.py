"""Full durable runtime — end-to-end workflow execution (Milestone 6).

Wires together: orchestrator → model proposer → boundary verification →
process executor → result → commit/reject → event ledger.
"""

from __future__ import annotations

import asyncio
import uuid
from pathlib import Path
from typing import TYPE_CHECKING, Any
from uuid import UUID

from durable_agent_runtime.boundary.service import BoundaryService
from durable_agent_runtime.domain import ActionProposal, GoalSpecification, Plan
from durable_agent_runtime.domain.enums import FaultType, RiskLevel, TaskStatus, WorkflowStatus
from durable_agent_runtime.execution.process_executor import ProcessExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext, ToolRegistry
from durable_agent_runtime.models.base import MockProvider, ModelProvider
from durable_agent_runtime.orchestration.engine import OrchestratorEngine
from durable_agent_runtime.orchestration.scheduler import TaskScheduler

if TYPE_CHECKING:
    from durable_agent_runtime.experiments.fault_injection import FaultInjector
    from durable_agent_runtime.models.base import ModelProvider


class DurableRuntime:
    """End-to-end durable agent runtime.

    Executes a workflow through the full pipeline:
    Goal → Compile → Plan → Orchestrate → Propose → Verify → Execute → Commit.
    Supports single-task (backward-compat) and multi-task DAG plans.
    """

    def __init__(
        self,
        data_dir: Path,
        workspace: Path,
        provider: ModelProvider | None = None,
        fault_injector: FaultInjector | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.workspace = Path(workspace)
        self.engine = OrchestratorEngine(self.data_dir)
        self.boundary = BoundaryService(self.engine.state)
        self.executor = ProcessExecutor()
        self.provider = provider or MockProvider()
        self.tool_registry = ToolRegistry()
        self.scheduler = TaskScheduler(self.engine.state, self.engine)
        self.fault_injector = fault_injector

    # ── Public entry point ──────────────────────────────────────────────────

    def run_goal(self, goal: GoalSpecification, plan: Plan | None = None) -> dict[str, Any]:
        """Execute a goal specification through the durable runtime.

        If *plan* is provided it is used directly (multi-task DAG support).
        If *plan* is None a default single-task plan is created (backward-compat).

        Returns a results dictionary with success/failure and metrics.
        """
        model_call_count = 0  # track actual provider calls

        # 1. Create workflow
        wf_id = self.engine.create_workflow(goal.goal_id, goal.repository_path)

        # Check for fault after workflow creation
        self._check_event_fault("workflow_created")

        # 2. Compile → Plan
        self.engine.transition_workflow(wf_id, WorkflowStatus.COMPILED)
        self._check_event_fault("goal_compiled")

        if plan is not None:
            # Use the provided multi-task plan
            self.engine.register_tasks(wf_id, plan)
        else:
            # Backward-compatible single-task plan
            task_id = uuid.uuid4()
            plan = Plan(
                goal_id=goal.goal_id,
                tasks=[self._create_default_task(task_id, goal)],
            )
            self.engine.register_tasks(wf_id, plan)

        self.engine.transition_workflow(wf_id, WorkflowStatus.PLANNED)
        self.engine.transition_workflow(wf_id, WorkflowStatus.RUNNING)

        # 3. Detect circular dependencies
        cycles = self.scheduler.detect_circular_deps(plan)
        if cycles:
            self.engine.transition_workflow(wf_id, WorkflowStatus.FAILED)
            return {
                "workflow_id": str(wf_id),
                "success": False,
                "error": f"Circular dependencies detected: {cycles}",
            }

        # 4. Multi-task DAG execution loop
        results: dict[str, dict] = {}
        max_iterations = len(plan.tasks) * 10  # safety bound
        iteration = 0

        while iteration < max_iterations:
            iteration += 1

            # Promote tasks whose deps are now satisfied
            promoted = self.scheduler.promote_pending(wf_id, plan)
            ready = self.scheduler.get_ready(wf_id, plan)

            if not ready and promoted == 0:
                # No progress — check if we're done or stuck
                break

            # Execute each READY task
            for task_id in ready:
                result = self._execute_task(wf_id, task_id, goal)
                results[str(task_id)] = result
                model_call_count += 1

        # 5. Determine final status
        all_tasks = self.engine.state.get_tasks_by_workflow(wf_id)
        task_statuses = {UUID(row.task_id): TaskStatus(row.status) for row in all_tasks}

        committed = [tid for tid, s in task_statuses.items() if s == TaskStatus.COMMITTED]
        failed = [tid for tid, s in task_statuses.items() if s == TaskStatus.FAILED]
        blocked = [tid for tid, s in task_statuses.items() if s == TaskStatus.BLOCKED]

        all_done = len(committed) == len(plan.tasks)
        unrecoverable = len(failed) + len(blocked) == len(plan.tasks)

        if all_done:
            self.engine.transition_workflow(wf_id, WorkflowStatus.COMPLETED)
            overall_success = True
            error_msg = ""
        elif unrecoverable:
            self.engine.transition_workflow(wf_id, WorkflowStatus.FAILED)
            overall_success = False
            error_msg = (
                f"Tasks: {len(committed)} committed, {len(failed)} failed, {len(blocked)} blocked"
            )
        else:
            # Mixed — some still in progress or PENDING
            self.engine.transition_workflow(wf_id, WorkflowStatus.FAILED)
            overall_success = False
            error_msg = "Execution halted with incomplete tasks"

        return {
            "workflow_id": str(wf_id),
            "success": overall_success,
            "error": error_msg,
            "task_results": results,
            "task_summary": {
                "total": len(plan.tasks),
                "committed": len(committed),
                "failed": len(failed),
                "blocked": len(blocked),
            },
            # Backward-compat fields for single-task mode
            "task_id": str(plan.tasks[0].task_id) if plan.tasks else "",
            "output": (next(iter(results.values())).get("output", "") if results else ""),
            "model_calls": model_call_count,
        }

    # ── Fault injection helpers ─────────────────────────────────────────────

    def _check_event_fault(self, event_type: str) -> None:
        """Check the fault injector for an event-based fault and react."""
        if self.fault_injector is None:
            return
        ft = self.fault_injector.get_fault(event_type)
        if ft is None:
            return
        if ft == FaultType.PROCESS_KILL:
            raise SystemExit(137)
        if ft == FaultType.MODEL_TIMEOUT:
            raise TimeoutError(f"Model timeout injected at event {event_type!r}")
        # Other fault types are handled at the tool/execution level

    # ── Helpers ─────────────────────────────────────────────────────────────

    def _create_default_task(self, task_id: UUID, goal: GoalSpecification):
        from durable_agent_runtime.domain import Task

        return Task(
            task_id=task_id,
            title=goal.normalized_goal,
            description=goal.raw_goal,
            estimated_complexity=1,
            required_tools=goal.available_tools,
        )

    async def _propose_action(
        self,
        wf_id: UUID,
        task_id: UUID,
        goal: GoalSpecification,
        attempt: int = 1,
    ) -> ActionProposal:
        """Ask the model provider to propose an action for the given goal.

        Uses structured output to get a typed ``ProposedAction``, then
        converts it to a domain ``ActionProposal``.
        """
        from durable_agent_runtime.models.base import ModelRequest
        from durable_agent_runtime.models.prompts import ProposedAction, build_action_prompt

        system_prompt, user_prompt = build_action_prompt(
            goal_text=goal.normalized_goal,
            repository_path=goal.repository_path,
            tools=self.tool_registry.list_names() or ["run_command", "read_file", "write_file"],
        )

        request = ModelRequest(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_model_name="ProposedAction",
        )

        response = await self.provider.generate_structured(request, ProposedAction)
        action_data = response.content

        # Convert ProposedAction → ActionProposal
        risk_map = {
            "low": RiskLevel.LOW,
            "medium": RiskLevel.MEDIUM,
            "high": RiskLevel.HIGH,
            "critical": RiskLevel.CRITICAL,
        }

        # Build arguments dict based on tool
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
            task_id=task_id,
            actor_id=f"{getattr(self.provider, 'name', 'model')}-step-{attempt}",
            tool_name=tool_name,
            arguments=arguments,
            intention=action_data.get("intention", f"Execute: {goal.normalized_goal[:80]}"),
            expected_effects=action_data.get("expected_effects", []),
            idempotency_key=f"task-{task_id}-attempt-{attempt}",
            risk_level=risk_map.get(
                action_data.get("risk_level", "low"),
                RiskLevel.LOW,
            ),
        )

    def _execute_task(self, wf_id: UUID, task_id: UUID, goal: GoalSpecification) -> dict[str, Any]:
        """Execute one task through the proposal→verify→execute→commit cycle.

        NOTE: The task is expected to already be in READY state (the scheduler
        promotes PENDING→READY before calling this method).
        """
        # Transition: READY → CLAIMED → PROPOSING
        self.engine.transition_task(task_id, wf_id, TaskStatus.CLAIMED)
        self.engine.transition_task(task_id, wf_id, TaskStatus.PROPOSING)

        # Check for model-related faults before creating proposal
        self._check_event_fault("action_proposed")

        # Ask the model to propose an action (run async inside sync context)
        try:
            proposal = asyncio.run(self._propose_action(wf_id, task_id, goal))
        except (TimeoutError, Exception) as exc:
            self.engine.transition_task(task_id, wf_id, TaskStatus.REJECTED)
            return {
                "success": False,
                "error": f"Model proposal failed: {exc}",
            }

        # Verify
        self.engine.transition_task(task_id, wf_id, TaskStatus.VERIFYING)
        verification = self.boundary.verify(proposal)

        if not verification.passed:
            self.engine.transition_task(task_id, wf_id, TaskStatus.REJECTED)
            return {
                "success": False,
                "error": verification.rejection_message or "Verification failed",
            }

        # Execute
        self.engine.transition_task(task_id, wf_id, TaskStatus.EXECUTING)

        # Check for execution-level faults before tool call
        self._check_event_fault("action_execution_started")

        context = ToolContext(workspace_root=str(self.workspace))

        # Check for tool-level faults
        if self.fault_injector is not None:
            ft = self.fault_injector.get_fault_for_tool(proposal.tool_name)
            if ft == FaultType.TOOL_TIMEOUT:
                context = ToolContext(
                    workspace_root=str(self.workspace),
                    timeout_seconds=1,
                )
            elif ft == FaultType.PROCESS_KILL:
                raise SystemExit(137)

        cmd_arg = proposal.arguments.get("command", "echo done")
        if isinstance(cmd_arg, str):
            cmd_arg = ["sh", "-c", cmd_arg]
        result = self.executor.execute(cmd_arg, context)

        # Post-verify
        self.engine.transition_task(task_id, wf_id, TaskStatus.POST_VERIFYING)
        self._check_event_fault("action_execution_succeeded")

        if result.success:
            # Record idempotency and commit
            self.engine.state.record_idempotency(
                proposal.idempotency_key,
                wf_id,
                execution_status="committed",
            )
            self.engine.transition_task(task_id, wf_id, TaskStatus.COMMITTED)
            return {"success": True, "output": result.output}
        else:
            self.engine.transition_task(task_id, wf_id, TaskStatus.RETRY_WAIT)
            return {"success": False, "error": result.error}
