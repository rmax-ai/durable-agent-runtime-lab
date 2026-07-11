"""Domain module — canonical data models.

Re-exports all domain models for convenient imports:
    from durable_agent_runtime.domain import (
        GoalSpecification,
        Plan,
        Task,
        ActionProposal,
        VerificationResult,
        ExecutionResult,
        Event,
        Checkpoint,
        ...
    )
"""

from .action import (
    ActionProposal,
    CheckResult,
    EvidenceReference,
    ExecutionResult,
    ResourceUsage,
    SideEffect,
    VerificationResult,
)
from .checkpoint import Checkpoint, ModelConfiguration, ToolConfiguration
from .enums import (
    ApprovalPolicy,
    EventType,
    ExecutionStatus,
    FaultType,
    PlanStatus,
    RetryableErrorKind,
    RiskLevel,
    SandboxMode,
    TaskStatus,
    WorkflowStatus,
)
from .event import Event
from .goal import Budget, Constraint, GoalSpecification, SuccessCriterion
from .plan import Assertion, ModelReference, Plan, Task
from .state_machine import (
    TASK_TRANSITIONS,
    WORKFLOW_TRANSITIONS,
    InvalidTransitionError,
    can_transition,
    validate_transition,
)

__all__ = [
    "TASK_TRANSITIONS",
    # State Machine
    "WORKFLOW_TRANSITIONS",
    # Action & Verification
    "ActionProposal",
    # Enums
    "ApprovalPolicy",
    # Plan & Task
    "Assertion",
    # Goal
    "Budget",
    "CheckResult",
    # Checkpoint
    "Checkpoint",
    "Constraint",
    # Event
    "Event",
    "EventType",
    "EvidenceReference",
    "ExecutionResult",
    "ExecutionStatus",
    "FaultType",
    "GoalSpecification",
    "InvalidTransitionError",
    "ModelConfiguration",
    "ModelReference",
    "Plan",
    "PlanStatus",
    "ResourceUsage",
    "RetryableErrorKind",
    "RiskLevel",
    "SandboxMode",
    "SideEffect",
    "SuccessCriterion",
    "Task",
    "TaskStatus",
    "ToolConfiguration",
    "VerificationResult",
    "WorkflowStatus",
    "can_transition",
    "validate_transition",
]
