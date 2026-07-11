"""Canonical goal specification domain model (Section 9.1)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .enums import ApprovalPolicy, RiskLevel


class Budget(BaseModel):
    """Cost budget constraints for a workflow or task."""

    max_currency: float | None = Field(
        default=None, description="Maximum estimated cost in currency units"
    )
    max_tokens: int | None = Field(
        default=None, description="Maximum total tokens (input + output)"
    )
    max_model_calls: int | None = Field(default=None, description="Maximum model API calls")
    max_tool_calls: int | None = Field(default=None, description="Maximum tool executions")
    max_elapsed_seconds: int | None = Field(default=None, description="Maximum wall-clock time")
    max_retries: int | None = Field(
        default=None, description="Maximum total retries across all tasks"
    )


class Constraint(BaseModel):
    """A constraint on the goal or execution."""

    constraint_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    constraint_type: str  # e.g. "file_scope", "tool_scope", "time_limit", "network_policy"
    parameters: dict[str, Any] = Field(default_factory=dict)


class SuccessCriterion(BaseModel):
    """A verifiable success criterion."""

    criterion_id: UUID = Field(default_factory=uuid4)
    name: str
    description: str
    verification_method: str  # "test_pass", "file_exists", "diff_match", "model_eval", etc.
    expected: Any | None = Field(default=None, description="Expected value or pattern")
    weight: float = Field(default=1.0, ge=0.0)


class GoalSpecification(BaseModel):
    """Complete typed goal specification (Section 9.1)."""

    goal_id: UUID = Field(default_factory=uuid4)
    raw_goal: str = Field(description="Original natural-language goal")
    normalized_goal: str = Field(description="Normalized and structured goal text")
    repository_path: str = Field(description="Path to the target repository")
    constraints: list[Constraint] = Field(default_factory=list)
    success_criteria: list[SuccessCriterion] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)
    available_tools: list[str] = Field(default_factory=list)
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)
    max_budget: Budget = Field(default_factory=Budget)
    human_approval_policy: ApprovalPolicy = Field(default=ApprovalPolicy.MEDIUM_AND_ABOVE)
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    compiled_by: str | None = Field(
        default=None, description="Model or agent that compiled the goal"
    )
