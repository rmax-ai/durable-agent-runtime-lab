"""Canonical enum definitions for the Durable Agent Runtime.

All workflow and task states, event types, risk levels, approval policies,
and other enumerated types used across the domain model.
"""

from enum import StrEnum


class RiskLevel(StrEnum):
    """Risk classification for goals, tasks, tool calls, and actions."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ApprovalPolicy(StrEnum):
    """Policy governing when human approval is required."""

    NONE = "none"
    LOW_RISK_ONLY = "low_risk_only"
    MEDIUM_AND_ABOVE = "medium_and_above"
    HIGH_AND_ABOVE = "high_and_above"
    ALL_MUTATING = "all_mutating"


class WorkflowStatus(StrEnum):
    """Workflow-level state machine states (Section 10)."""

    CREATED = "created"
    COMPILED = "compiled"
    PLANNED = "planned"
    RUNNING = "running"
    PAUSED = "paused"
    RECOVERING = "recovering"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(StrEnum):
    """Task-level state machine states (Section 10)."""

    PENDING = "pending"
    READY = "ready"
    CLAIMED = "claimed"
    PROPOSING = "proposing"
    VERIFYING = "verifying"
    EXECUTING = "executing"
    POST_VERIFYING = "post_verifying"
    COMMITTED = "committed"
    REJECTED = "rejected"
    RETRY_WAIT = "retry_wait"
    BLOCKED = "blocked"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ExecutionStatus(StrEnum):
    """Fine-grained execution result status."""

    SUCCEEDED = "succeeded"
    FAILED = "failed"
    TIMED_OUT = "timed_out"
    REJECTED_BY_POLICY = "rejected_by_policy"
    REJECTED_BY_SCHEMA = "rejected_by_schema"
    REJECTED_BY_AUTHZ = "rejected_by_authorization"
    REJECTED_BY_PRECONDITION = "rejected_by_precondition"
    REJECTED_BY_BUDGET = "rejected_by_budget"
    REJECTED_BY_IDEMPOTENCY = "rejected_by_idempotency"
    SANDBOX_VIOLATION = "sandbox_violation"


class EventType(StrEnum):
    """All supported event types (Section 11)."""

    WORKFLOW_CREATED = "workflow_created"
    GOAL_COMPILED = "goal_compiled"
    GOAL_REJECTED = "goal_rejected"
    PLAN_PROPOSED = "plan_proposed"
    PLAN_VALIDATED = "plan_validated"
    PLAN_REJECTED = "plan_rejected"
    PLAN_VERSION_CREATED = "plan_version_created"
    TASK_READY = "task_ready"
    TASK_CLAIMED = "task_claimed"
    ACTION_PROPOSED = "action_proposed"
    ACTION_VERIFICATION_PASSED = "action_verification_passed"
    ACTION_VERIFICATION_FAILED = "action_verification_failed"
    ACTION_EXECUTION_STARTED = "action_execution_started"
    ACTION_EXECUTION_SUCCEEDED = "action_execution_succeeded"
    ACTION_EXECUTION_FAILED = "action_execution_failed"
    POSTCONDITION_PASSED = "postcondition_passed"
    POSTCONDITION_FAILED = "postcondition_failed"
    ACTION_COMMITTED = "action_committed"
    ACTION_REJECTED = "action_rejected"
    CHECKPOINT_CREATED = "checkpoint_created"
    ROLLBACK_STARTED = "rollback_started"
    ROLLBACK_COMPLETED = "rollback_completed"
    RECOVERY_STARTED = "recovery_started"
    RECOVERY_COMPLETED = "recovery_completed"
    HUMAN_APPROVAL_REQUESTED = "human_approval_requested"
    HUMAN_APPROVAL_RECEIVED = "human_approval_received"
    BUDGET_THRESHOLD_REACHED = "budget_threshold_reached"
    WORKFLOW_COMPLETED = "workflow_completed"
    WORKFLOW_FAILED = "workflow_failed"


class PlanStatus(StrEnum):
    """Plan-level status."""

    DRAFT = "draft"
    PROPOSED = "proposed"
    VALIDATED = "validated"
    REJECTED = "rejected"
    ACTIVE = "active"
    SUPERSEDED = "superseded"


class FaultType(StrEnum):
    """Supported fault injection types (Section 22)."""

    PROCESS_KILL = "process_kill"
    MODEL_TIMEOUT = "model_timeout"
    MALFORMED_MODEL_RESPONSE = "malformed_model_response"
    TOOL_TIMEOUT = "tool_timeout"
    TOOL_NONZERO_EXIT = "tool_nonzero_exit"
    TRANSIENT_FILESYSTEM_ERROR = "transient_filesystem_error"
    CORRUPTED_ARTIFACT = "corrupted_artifact"
    DUPLICATE_MESSAGE = "duplicate_message"
    DELAYED_EVENT_WRITE = "delayed_event_write"
    FAILED_CHECKPOINT = "failed_checkpoint"
    FAILED_COMMIT = "failed_commit"
    REPEATED_IDENTICAL_PROPOSAL = "repeated_identical_proposal"
    OUT_OF_BUDGET = "out_of_budget"


class RetryableErrorKind(StrEnum):
    """Classification for whether an error is retryable (Section 16)."""

    RETRYABLE = "retryable"
    NON_RETRYABLE = "non_retryable"


class SandboxMode(StrEnum):
    """Sandbox executor implementation mode."""

    PROCESS = "process"
    DOCKER = "docker"
