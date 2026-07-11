"""Recovery and replay utilities (Section 15).

Reconstructs workflow state from events. Supports replay without model calls.
"""

import contextlib
from uuid import UUID

from durable_agent_runtime.domain.enums import TaskStatus, WorkflowStatus
from durable_agent_runtime.persistence.event_store import EventStore
from durable_agent_runtime.persistence.state_store import StateStore


class RecoveryManager:
    """Handles workflow recovery after forced termination."""

    def __init__(self, event_store: EventStore, state_store: StateStore) -> None:
        self.events = event_store
        self.state = state_store

    def verify_integrity(self, workflow_id: UUID) -> bool:
        """Verify event ledger hash chain integrity."""
        valid, _ = self.events.verify_chain(workflow_id)
        return valid

    def reconstruct_state(self, workflow_id: UUID) -> None:
        """Reconstruct SQLite state projections from the event ledger."""
        events = self.events.read_all(workflow_id)
        if not events:
            return

        # Get initial workflow state from first event
        events[0]
        wf_status = WorkflowStatus.CREATED

        # Replay events to derive current state
        for event in events:
            payload = event.payload
            to_status = payload.get("to_status")
            if to_status:
                with contextlib.suppress(ValueError):
                    wf_status = WorkflowStatus(to_status)

            # Task state transitions
            if event.task_id:
                task_id = UUID(str(event.task_id))
                task_to = payload.get("to_status", "pending")
                try:
                    task_status = TaskStatus(task_to)
                    self.state.upsert_task(task_id, workflow_id, task_status)
                except ValueError:
                    pass

        self.state.upsert_workflow(workflow_id, wf_status, last_event_sequence=events[-1].sequence)

    def get_incomplete_tasks(self, workflow_id: UUID) -> list[UUID]:
        """Return task IDs that are not in a terminal state."""
        all_tasks = self.state.get_tasks_by_workflow(workflow_id)
        terminal = {TaskStatus.COMMITTED, TaskStatus.FAILED, TaskStatus.CANCELLED}
        return [UUID(t.task_id) for t in all_tasks if TaskStatus(t.status) not in terminal]
