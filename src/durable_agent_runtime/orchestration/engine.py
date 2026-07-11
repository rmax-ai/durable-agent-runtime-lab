"""Deterministic workflow orchestrator (Section 6.3).

Owns canonical workflow state. Enforces state transitions. Dispatches ready
tasks. Models propose actions; the orchestrator validates and commits.

This is the core deterministic boundary — all state transitions flow through
this engine. No model can directly alter workflow or task state.
"""

import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Optional
from uuid import UUID

from durable_agent_runtime.domain import Event, Plan
from durable_agent_runtime.domain.enums import EventType, TaskStatus, WorkflowStatus
from durable_agent_runtime.domain.state_machine import validate_transition
from durable_agent_runtime.persistence.event_store import EventStore
from durable_agent_runtime.persistence.state_store import StateStore


class OrchestratorEngine:
    """Deterministic workflow orchestrator.

    Each workflow runs through: CREATED → COMPILED → PLANNED → RUNNING → COMPLETED/FAILED.
    Tasks cycle through: PENDING → READY → CLAIMED → ... → COMMITTED.

    The engine is stateless between calls — all state lives in the EventStore
    and StateStore. This makes it restart-safe by design.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.events = EventStore(self.data_dir)
        self.state = StateStore(self.data_dir)

    # ── Workflow lifecycle ──────────────────────────────────────────────

    def create_workflow(
        self,
        goal_id: UUID,
        repository_path: str,
    ) -> UUID:
        """Initialize a new workflow. Returns workflow_id."""
        workflow_id = uuid.uuid4()
        event = self._append_event(
            workflow_id=workflow_id,
            event_type=EventType.WORKFLOW_CREATED,
            actor_id="orchestrator",
            payload={
                "goal_id": str(goal_id),
                "repository_path": repository_path,
            },
        )
        self.state.upsert_workflow(workflow_id, WorkflowStatus.CREATED)
        return workflow_id

    def transition_workflow(self, workflow_id: UUID, target: WorkflowStatus) -> None:
        """Transition workflow to target state. Validates and records the event."""
        current_row = self.state.get_workflow(workflow_id)
        current = WorkflowStatus(current_row.status) if current_row else WorkflowStatus.CREATED
        validate_transition(current, target, "workflow")

        event_type_map = {
            WorkflowStatus.COMPILED: EventType.GOAL_COMPILED,
            WorkflowStatus.PLANNED: EventType.PLAN_VALIDATED,
            WorkflowStatus.RUNNING: EventType.WORKFLOW_CREATED,  # Reused — we transition to RUNNING via task dispatch
            WorkflowStatus.PAUSED: EventType.HUMAN_APPROVAL_REQUESTED,
            WorkflowStatus.RECOVERING: EventType.RECOVERY_STARTED,
            WorkflowStatus.COMPLETED: EventType.WORKFLOW_COMPLETED,
            WorkflowStatus.FAILED: EventType.WORKFLOW_FAILED,
            WorkflowStatus.CANCELLED: EventType.WORKFLOW_FAILED,
        }
        ev_type = event_type_map.get(target, EventType.WORKFLOW_CREATED)

        self._append_event(
            workflow_id=workflow_id,
            event_type=ev_type,
            actor_id="orchestrator",
            payload={"from_status": current.value, "to_status": target.value},
        )
        self.state.upsert_workflow(workflow_id, target)

    def get_workflow_status(self, workflow_id: UUID) -> WorkflowStatus:
        """Get current workflow status from state projection."""
        row = self.state.get_workflow(workflow_id)
        return WorkflowStatus(row.status) if row else WorkflowStatus.CREATED

    # ── Task lifecycle ──────────────────────────────────────────────────

    def register_tasks(self, workflow_id: UUID, plan: Plan) -> None:
        """Register all tasks from a plan into the state store."""
        for task in plan.tasks:
            self.state.upsert_task(task.task_id, workflow_id, TaskStatus.PENDING)

    def get_ready_tasks(self, workflow_id: UUID) -> list[UUID]:
        """Return task IDs that are READY to be claimed."""
        all_tasks = self.state.get_tasks_by_workflow(workflow_id)
        return [
            UUID(row.task_id)
            for row in all_tasks
            if TaskStatus(row.status) == TaskStatus.READY
        ]

    def get_pending_tasks(self, workflow_id: UUID) -> list[UUID]:
        """Return task IDs that are PENDING (dependencies not yet met)."""
        all_tasks = self.state.get_tasks_by_workflow(workflow_id)
        return [
            UUID(row.task_id)
            for row in all_tasks
            if TaskStatus(row.status) == TaskStatus.PENDING
        ]

    def transition_task(self, task_id: UUID, workflow_id: UUID, target: TaskStatus) -> None:
        """Transition a task to a new state. Validates and records."""
        row = self.state.get_task(task_id)
        current = TaskStatus(row.status) if row else TaskStatus.PENDING
        validate_transition(current, target, "task")

        event_type_map = {
            TaskStatus.READY: EventType.TASK_READY,
            TaskStatus.CLAIMED: EventType.TASK_CLAIMED,
            TaskStatus.PROPOSING: EventType.ACTION_PROPOSED,
            TaskStatus.EXECUTING: EventType.ACTION_EXECUTION_STARTED,
            TaskStatus.COMMITTED: EventType.ACTION_COMMITTED,
            TaskStatus.REJECTED: EventType.ACTION_REJECTED,
            TaskStatus.FAILED: EventType.TASK_READY,  # Generic — will use REJECTED
            TaskStatus.RETRY_WAIT: EventType.ACTION_REJECTED,
        }
        ev_type = event_type_map.get(target, EventType.TASK_READY)

        self._append_event(
            workflow_id=workflow_id,
            task_id=task_id,
            event_type=ev_type,
            actor_id="orchestrator",
            payload={"from_status": current.value, "to_status": target.value},
        )
        self.state.upsert_task(task_id, workflow_id, target)

    # ── Event helpers ───────────────────────────────────────────────────

    def _append_event(
        self,
        workflow_id: UUID,
        event_type: EventType,
        actor_id: str,
        payload: dict | None = None,
        task_id: UUID | None = None,
    ) -> Event:
        """Create and append an event to the ledger."""
        latest_seq = self.events.get_latest_sequence(workflow_id)
        event = Event(
            sequence=latest_seq + 1,
            workflow_id=workflow_id,
            task_id=task_id,
            event_type=event_type,
            actor_id=actor_id,
            payload=payload or {},
            correlation_id=uuid.uuid4(),
        )
        return self.events.append(event)

    # ── Budget tracking ─────────────────────────────────────────────────

    def record_model_call(
        self,
        workflow_id: UUID,
        input_tokens: int,
        output_tokens: int,
        cached_tokens: int = 0,
    ) -> None:
        """Increment budget counters."""
        row = self.state.get_workflow(workflow_id)
        if row:
            self.state.upsert_workflow(
                workflow_id,
                WorkflowStatus(row.status),
                tokens_used=row.tokens_used + input_tokens + output_tokens,
                model_calls=row.model_calls + 1,
            )

    def record_tool_call(self, workflow_id: UUID) -> None:
        """Increment tool call counter."""
        row = self.state.get_workflow(workflow_id)
        if row:
            self.state.upsert_workflow(
                workflow_id,
                WorkflowStatus(row.status),
                tool_calls=row.tool_calls + 1,
            )
