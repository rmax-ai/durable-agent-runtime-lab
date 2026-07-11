"""Tests for enum definitions."""

from durable_agent_runtime.domain.enums import (
    EventType,
    ExecutionStatus,
    TaskStatus,
    WorkflowStatus,
)


class TestWorkflowStatus:
    """WorkflowStatus enum integrity."""

    def test_terminal_states_are_completed_failed_cancelled(self) -> None:
        terminal = {WorkflowStatus.COMPLETED, WorkflowStatus.FAILED, WorkflowStatus.CANCELLED}
        for state in WorkflowStatus:
            if state in terminal:
                assert True  # terminal
            else:
                assert state in {
                    WorkflowStatus.CREATED,
                    WorkflowStatus.COMPILED,
                    WorkflowStatus.PLANNED,
                    WorkflowStatus.RUNNING,
                    WorkflowStatus.PAUSED,
                    WorkflowStatus.RECOVERING,
                }


class TestTaskStatus:
    """TaskStatus enum integrity."""

    def test_all_states_present(self) -> None:
        expected = {
            "pending",
            "ready",
            "claimed",
            "proposing",
            "verifying",
            "executing",
            "post_verifying",
            "committed",
            "rejected",
            "retry_wait",
            "blocked",
            "failed",
            "cancelled",
        }
        actual = {s.value for s in TaskStatus}
        assert actual == expected


class TestEventType:
    """EventType enum covers required events (Section 11)."""

    def test_minimum_event_types_present(self) -> None:
        required = {
            EventType.WORKFLOW_CREATED,
            EventType.WORKFLOW_COMPLETED,
            EventType.WORKFLOW_FAILED,
            EventType.GOAL_COMPILED,
            EventType.ACTION_COMMITTED,
            EventType.ACTION_REJECTED,
            EventType.CHECKPOINT_CREATED,
            EventType.RECOVERY_STARTED,
            EventType.RECOVERY_COMPLETED,
        }
        assert required.issubset(set(EventType))


class TestExecutionStatus:
    """ExecutionStatus enum covers rejection categories."""

    def test_rejection_statuses_exist(self) -> None:
        rejection_statuses = {
            ExecutionStatus.REJECTED_BY_POLICY,
            ExecutionStatus.REJECTED_BY_SCHEMA,
            ExecutionStatus.REJECTED_BY_AUTHZ,
            ExecutionStatus.REJECTED_BY_PRECONDITION,
            ExecutionStatus.REJECTED_BY_BUDGET,
            ExecutionStatus.REJECTED_BY_IDEMPOTENCY,
            ExecutionStatus.SANDBOX_VIOLATION,
        }
        for status in rejection_statuses:
            assert "rejected" in status.value or "violation" in status.value
