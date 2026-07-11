"""Workflow and task state machine definitions (Section 10)."""

from .enums import TaskStatus, WorkflowStatus

# ── Workflow state transitions ──────────────────────────────────────────────
# Canonical: Section 10 workflow lifecycle state machine

WORKFLOW_TRANSITIONS: dict[WorkflowStatus, set[WorkflowStatus]] = {
    WorkflowStatus.CREATED: {
        WorkflowStatus.COMPILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.COMPILED: {
        WorkflowStatus.PLANNED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.PLANNED: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.RUNNING: {
        WorkflowStatus.PAUSED,
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.PAUSED: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.RECOVERING,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.RECOVERING: {
        WorkflowStatus.RUNNING,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    },
    WorkflowStatus.COMPLETED: set(),  # Terminal
    WorkflowStatus.FAILED: set(),  # Terminal
    WorkflowStatus.CANCELLED: set(),  # Terminal
}

# ── Task state transitions ──────────────────────────────────────────────────
# Canonical: Section 10 task lifecycle state machine

TASK_TRANSITIONS: dict[TaskStatus, set[TaskStatus]] = {
    TaskStatus.PENDING: {
        TaskStatus.READY,
        TaskStatus.CANCELLED,
    },
    TaskStatus.READY: {
        TaskStatus.CLAIMED,
        TaskStatus.BLOCKED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.CLAIMED: {
        TaskStatus.PROPOSING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.PROPOSING: {
        TaskStatus.VERIFYING,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.VERIFYING: {
        TaskStatus.EXECUTING,
        TaskStatus.REJECTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.EXECUTING: {
        TaskStatus.POST_VERIFYING,
        TaskStatus.REJECTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.POST_VERIFYING: {
        TaskStatus.COMMITTED,
        TaskStatus.RETRY_WAIT,
        TaskStatus.REJECTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.COMMITTED: set(),  # Terminal
    TaskStatus.REJECTED: {
        TaskStatus.RETRY_WAIT,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.RETRY_WAIT: {
        TaskStatus.READY,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    },
    TaskStatus.BLOCKED: {
        TaskStatus.READY,
        TaskStatus.CANCELLED,
    },
    TaskStatus.FAILED: set(),  # Terminal
    TaskStatus.CANCELLED: set(),  # Terminal
}


class InvalidTransitionError(ValueError):
    """Raised when an invalid state transition is attempted."""

    def __init__(
        self,
        current: WorkflowStatus | TaskStatus,
        target: WorkflowStatus | TaskStatus,
        entity_type: str,
    ) -> None:
        self.current = current
        self.target = target
        self.entity_type = entity_type
        super().__init__(f"Invalid {entity_type} transition: {current.value} → {target.value}")


def can_transition(
    current: WorkflowStatus | TaskStatus,
    target: WorkflowStatus | TaskStatus,
) -> bool:
    """Check if a state transition is valid."""
    if isinstance(current, WorkflowStatus) and isinstance(target, WorkflowStatus):
        return target in WORKFLOW_TRANSITIONS.get(current, set())
    if isinstance(current, TaskStatus) and isinstance(target, TaskStatus):
        return target in TASK_TRANSITIONS.get(current, set())
    return False


def validate_transition(
    current: WorkflowStatus | TaskStatus,
    target: WorkflowStatus | TaskStatus,
    entity_type: str,
) -> None:
    """Validate a state transition, raising on invalid."""
    if not can_transition(current, target):
        raise InvalidTransitionError(current, target, entity_type)
