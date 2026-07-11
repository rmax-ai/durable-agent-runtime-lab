"""Canonical action and action proposal domain models (Section 9.4)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .enums import ExecutionStatus, RiskLevel
from .plan import Assertion


class ActionProposal(BaseModel):
    """A model-proposed action before verification (Section 9.4)."""

    proposal_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    task_id: UUID
    actor_id: str = Field(description="Model or agent proposing the action")
    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    intention: str = Field(
        description="Human-readable description of what this action intends to do"
    )
    expected_effects: list[str] = Field(default_factory=list)
    expected_postconditions: list[Assertion] = Field(default_factory=list)
    idempotency_key: str = Field(description="Unique key for deduplication")
    risk_level: RiskLevel = Field(default=RiskLevel.LOW)
    requested_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """Result of proposal verification (Section 9.5)."""

    verification_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    passed: bool
    checks: list["CheckResult"] = Field(default_factory=list)
    rejection_code: str | None = None
    rejection_message: str | None = None
    evidence: list["EvidenceReference"] = Field(default_factory=list)
    verified_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    verified_by: str = "deterministic"  # or model reference


class CheckResult(BaseModel):
    """Result of a single verification check."""

    check_name: str
    passed: bool
    detail: str = ""
    check_type: str = "deterministic"  # or "model_based"


class EvidenceReference(BaseModel):
    """Reference to verification evidence."""

    reference_type: str  # "artifact", "log_line", "test_result", "diff"
    reference_id: str
    description: str = ""


class ResourceUsage(BaseModel):
    """Resource consumption for an execution."""

    cpu_seconds: float = 0.0
    memory_mb: float = 0.0
    disk_read_bytes: int = 0
    disk_write_bytes: int = 0
    network_bytes: int = 0


class SideEffect(BaseModel):
    """Recorded side effect of tool execution."""

    effect_type: (
        str  # "file_created", "file_modified", "file_deleted", "command_output", "network_call"
    )
    target: str
    description: str
    before_hash: str | None = None
    after_hash: str | None = None


class ExecutionResult(BaseModel):
    """Result of sandboxed tool execution (Section 9.6)."""

    execution_id: UUID = Field(default_factory=uuid4)
    proposal_id: UUID
    status: ExecutionStatus = Field(description="Execution outcome")
    exit_code: int | None = None
    stdout_ref: str | None = Field(default=None, description="Artifact reference to stdout")
    stderr_ref: str | None = Field(default=None, description="Artifact reference to stderr")
    started_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    finished_at: datetime | None = None
    resource_usage: ResourceUsage = Field(default_factory=ResourceUsage)
    workspace_diff_hash: str | None = Field(default=None, description="SHA-256 of workspace diff")
    side_effects: list[SideEffect] = Field(default_factory=list)
    error_message: str | None = None
