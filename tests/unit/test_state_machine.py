"""Tests for workflow and task state machines (Section 10).

Verifies every state transition in the spec, rejects invalid transitions,
and ensures terminal states cannot transition.
"""

import pytest

from durable_agent_runtime.domain.enums import TaskStatus, WorkflowStatus
from durable_agent_runtime.domain.state_machine import (
    TASK_TRANSITIONS,
    WORKFLOW_TRANSITIONS,
    InvalidTransitionError,
    can_transition,
    validate_transition,
)

# ── Workflow state machine tests ────────────────────────────────────────────


class TestWorkflowStateMachine:
    """WorkflowStatus state transitions as specified in Section 10."""

    def test_created_to_compiled(self) -> None:
        assert can_transition(WorkflowStatus.CREATED, WorkflowStatus.COMPILED)

    def test_created_to_cancelled(self) -> None:
        assert can_transition(WorkflowStatus.CREATED, WorkflowStatus.CANCELLED)

    def test_compiled_to_planned(self) -> None:
        assert can_transition(WorkflowStatus.COMPILED, WorkflowStatus.PLANNED)

    def test_planned_to_running(self) -> None:
        assert can_transition(WorkflowStatus.PLANNED, WorkflowStatus.RUNNING)

    def test_running_to_paused(self) -> None:
        assert can_transition(WorkflowStatus.RUNNING, WorkflowStatus.PAUSED)

    def test_running_to_completed(self) -> None:
        assert can_transition(WorkflowStatus.RUNNING, WorkflowStatus.COMPLETED)

    def test_paused_to_running(self) -> None:
        assert can_transition(WorkflowStatus.PAUSED, WorkflowStatus.RUNNING)

    def test_paused_to_recovering(self) -> None:
        assert can_transition(WorkflowStatus.PAUSED, WorkflowStatus.RECOVERING)

    def test_recovering_to_running(self) -> None:
        assert can_transition(WorkflowStatus.RECOVERING, WorkflowStatus.RUNNING)

    # ── Terminal states ─────────────────────────────────────────────────

    @pytest.mark.parametrize(
        "terminal",
        [
            WorkflowStatus.COMPLETED,
            WorkflowStatus.FAILED,
            WorkflowStatus.CANCELLED,
        ],
    )
    def test_terminal_state_no_transitions(self, terminal: WorkflowStatus) -> None:
        """Terminal states cannot transition to anything."""
        for target in WorkflowStatus:
            assert not can_transition(terminal, target), (
                f"Terminal state {terminal.value} should not transition to {target.value}"
            )

    def test_created_is_not_terminal(self) -> None:
        assert can_transition(WorkflowStatus.CREATED, WorkflowStatus.COMPILED)

    # ── Invalid transitions ─────────────────────────────────────────────

    def test_created_to_running_invalid(self) -> None:
        assert not can_transition(WorkflowStatus.CREATED, WorkflowStatus.RUNNING)

    def test_compiled_to_completed_invalid(self) -> None:
        assert not can_transition(WorkflowStatus.COMPILED, WorkflowStatus.COMPLETED)

    def test_validate_transition_raises_on_invalid(self) -> None:
        with pytest.raises(InvalidTransitionError) as exc:
            validate_transition(WorkflowStatus.CREATED, WorkflowStatus.RUNNING, "workflow")
        assert "created" in str(exc.value)
        assert "running" in str(exc.value)


# ── Task state machine tests ────────────────────────────────────────────────


class TestTaskStateMachine:
    """TaskStatus state transitions as specified in Section 10."""

    def test_pending_to_ready(self) -> None:
        assert can_transition(TaskStatus.PENDING, TaskStatus.READY)

    def test_ready_to_claimed(self) -> None:
        assert can_transition(TaskStatus.READY, TaskStatus.CLAIMED)

    def test_ready_to_blocked(self) -> None:
        assert can_transition(TaskStatus.READY, TaskStatus.BLOCKED)

    def test_claimed_to_proposing(self) -> None:
        assert can_transition(TaskStatus.CLAIMED, TaskStatus.PROPOSING)

    def test_proposing_to_verifying(self) -> None:
        assert can_transition(TaskStatus.PROPOSING, TaskStatus.VERIFYING)

    def test_verifying_to_executing(self) -> None:
        assert can_transition(TaskStatus.VERIFYING, TaskStatus.EXECUTING)

    def test_verifying_to_rejected(self) -> None:
        assert can_transition(TaskStatus.VERIFYING, TaskStatus.REJECTED)

    def test_executing_to_post_verifying(self) -> None:
        assert can_transition(TaskStatus.EXECUTING, TaskStatus.POST_VERIFYING)

    def test_post_verifying_to_committed(self) -> None:
        assert can_transition(TaskStatus.POST_VERIFYING, TaskStatus.COMMITTED)

    def test_post_verifying_to_retry_wait(self) -> None:
        assert can_transition(TaskStatus.POST_VERIFYING, TaskStatus.RETRY_WAIT)

    def test_rejected_to_retry_wait(self) -> None:
        assert can_transition(TaskStatus.REJECTED, TaskStatus.RETRY_WAIT)

    def test_retry_wait_to_ready(self) -> None:
        assert can_transition(TaskStatus.RETRY_WAIT, TaskStatus.READY)

    def test_blocked_to_ready(self) -> None:
        assert can_transition(TaskStatus.BLOCKED, TaskStatus.READY)

    # ── Terminal task states ────────────────────────────────────────────

    @pytest.mark.parametrize(
        "terminal",
        [
            TaskStatus.COMMITTED,
            TaskStatus.FAILED,
            TaskStatus.CANCELLED,
        ],
    )
    def test_terminal_task_no_transitions(self, terminal: TaskStatus) -> None:
        for target in TaskStatus:
            assert not can_transition(terminal, target), (
                f"Terminal task state {terminal.value} should not transition to {target.value}"
            )

    # ── Task invalid transitions ────────────────────────────────────────

    def test_pending_to_executing_invalid(self) -> None:
        assert not can_transition(TaskStatus.PENDING, TaskStatus.EXECUTING)

    def test_committed_to_anything_invalid(self) -> None:
        assert not can_transition(TaskStatus.COMMITTED, TaskStatus.READY)
        assert not can_transition(TaskStatus.COMMITTED, TaskStatus.EXECUTING)

    def test_validate_task_transition_raises(self) -> None:
        with pytest.raises(InvalidTransitionError) as exc:
            validate_transition(TaskStatus.COMMITTED, TaskStatus.READY, "task")
        assert "committed" in str(exc.value)
        assert "ready" in str(exc.value)


# ── Transition table completeness ───────────────────────────────────────────


class TestTransitionTableCompleteness:
    """Verify transition tables cover all enum values."""

    def test_every_workflow_status_in_table(self) -> None:
        for status in WorkflowStatus:
            assert status in WORKFLOW_TRANSITIONS, (
                f"WorkflowStatus {status.value} missing from transition table"
            )

    def test_every_task_status_in_table(self) -> None:
        for status in TaskStatus:
            assert status in TASK_TRANSITIONS, (
                f"TaskStatus {status.value} missing from transition table"
            )

    def test_all_transitions_are_valid_enums(self) -> None:
        """Every target in every transition set is a valid enum member."""
        for _source, targets in WORKFLOW_TRANSITIONS.items():
            for target in targets:
                assert isinstance(target, WorkflowStatus)
        for _source, targets in TASK_TRANSITIONS.items():
            for target in targets:
                assert isinstance(target, TaskStatus)


# ── InvalidTransitionError tests ────────────────────────────────────────────


class TestInvalidTransitionError:
    def test_error_repr(self) -> None:
        err = InvalidTransitionError(
            TaskStatus.COMMITTED,
            TaskStatus.READY,
            "task",
        )
        assert err.entity_type == "task"
        assert err.current == TaskStatus.COMMITTED
        assert err.target == TaskStatus.READY
