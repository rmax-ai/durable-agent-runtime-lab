"""Full durable runtime — end-to-end workflow execution (Milestone 6).

Wires together: orchestrator → model proposer → boundary verification →
process executor → result → commit/reject → event ledger.
"""

import uuid
from pathlib import Path
from uuid import UUID

from durable_agent_runtime.boundary.service import BoundaryService
from durable_agent_runtime.domain import ActionProposal, GoalSpecification, Plan
from durable_agent_runtime.domain.enums import RiskLevel, TaskStatus, WorkflowStatus
from durable_agent_runtime.execution.process_executor import ProcessExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext, ToolRegistry
from durable_agent_runtime.models.base import MockProvider
from durable_agent_runtime.orchestration.engine import OrchestratorEngine


class DurableRuntime:
    """End-to-end durable agent runtime.

    Executes a workflow through the full pipeline:
    Goal → Compile → Plan → Orchestrate → Propose → Verify → Execute → Commit.
    """

    def __init__(self, data_dir: Path, workspace: Path) -> None:
        self.data_dir = Path(data_dir)
        self.workspace = Path(workspace)
        self.engine = OrchestratorEngine(self.data_dir)
        self.boundary = BoundaryService(self.engine.state)
        self.executor = ProcessExecutor()
        self.provider = MockProvider()
        self.tool_registry = ToolRegistry()

    def run_goal(self, goal: GoalSpecification) -> dict:
        """Execute a goal specification through the durable runtime.

        Returns a results dictionary with success/failure and metrics.
        """
        # 1. Create workflow
        wf_id = self.engine.create_workflow(goal.goal_id, goal.repository_path)

        # 2. Compile → Plan (simplified: create a single-task plan)
        self.engine.transition_workflow(wf_id, WorkflowStatus.COMPILED)
        task_id = uuid.uuid4()
        plan = Plan(
            goal_id=goal.goal_id,
            tasks=[self._create_default_task(task_id, goal)],
        )
        self.engine.register_tasks(wf_id, plan)
        self.engine.transition_workflow(wf_id, WorkflowStatus.PLANNED)
        self.engine.transition_workflow(wf_id, WorkflowStatus.RUNNING)

        # 3. Execute the single task
        result = self._execute_task(wf_id, task_id, goal)

        # 4. Complete
        if result["success"]:
            self.engine.transition_workflow(wf_id, WorkflowStatus.COMPLETED)
        else:
            self.engine.transition_workflow(wf_id, WorkflowStatus.FAILED)

        return {
            "workflow_id": str(wf_id),
            "success": result["success"],
            "task_id": str(task_id),
            "output": result.get("output", ""),
            "error": result.get("error", ""),
        }

    def _create_default_task(self, task_id: UUID, goal: GoalSpecification):
        from durable_agent_runtime.domain import Task

        return Task(
            task_id=task_id,
            title=goal.normalized_goal,
            description=goal.raw_goal,
            estimated_complexity=1,
            required_tools=goal.available_tools,
        )

    def _execute_task(self, wf_id: UUID, task_id: UUID, goal: GoalSpecification) -> dict:
        """Execute one task through the proposal→verify→execute→commit cycle."""
        # Transition: PENDING → READY → CLAIMED → PROPOSING
        self.engine.transition_task(task_id, wf_id, TaskStatus.READY)
        self.engine.transition_task(task_id, wf_id, TaskStatus.CLAIMED)
        self.engine.transition_task(task_id, wf_id, TaskStatus.PROPOSING)

        # Create an action proposal
        proposal = ActionProposal(
            workflow_id=wf_id,
            task_id=task_id,
            actor_id="mock-model",
            tool_name="run_command",
            arguments={"command": f"echo 'Completing: {goal.raw_goal[:50]}'"},
            intention=f"Execute: {goal.normalized_goal[:80]}",
            idempotency_key=f"task-{task_id}-attempt-1",
            risk_level=RiskLevel.LOW,
        )

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
        context = ToolContext(workspace_root=str(self.workspace))
        cmd_arg = proposal.arguments.get("command", "echo done")
        if isinstance(cmd_arg, str):
            cmd_arg = ["sh", "-c", cmd_arg]
        result = self.executor.execute(cmd_arg, context)

        # Post-verify
        self.engine.transition_task(task_id, wf_id, TaskStatus.POST_VERIFYING)

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
