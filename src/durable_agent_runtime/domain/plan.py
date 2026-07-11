"""Canonical plan and task domain models (Section 9.2, 9.3)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .enums import PlanStatus, RiskLevel, TaskStatus


class ModelReference(BaseModel):
    """Reference to a model that produced output."""

    provider: str
    model: str
    version: str | None = None
    parameters: dict[str, Any] = Field(default_factory=dict)


class Assertion(BaseModel):
    """A precondition or postcondition assertion."""

    assertion_id: UUID = Field(default_factory=uuid4)
    description: str
    assertion_type: str  # "test_pass", "file_exists", "schema_valid", "diff_empty", etc.
    parameters: dict[str, Any] = Field(default_factory=dict)


class Task(BaseModel):
    """A single task within a plan DAG (Section 9.3)."""

    task_id: UUID = Field(default_factory=uuid4)
    title: str
    description: str
    dependencies: list[UUID] = Field(
        default_factory=list, description="Task IDs this task depends on"
    )
    status: TaskStatus = Field(default=TaskStatus.PENDING)
    risk_level: RiskLevel = Field(default=RiskLevel.MEDIUM)
    estimated_complexity: int = Field(default=1, ge=1)
    required_tools: list[str] = Field(default_factory=list)
    preconditions: list[Assertion] = Field(default_factory=list)
    postconditions: list[Assertion] = Field(default_factory=list)
    max_attempts: int = Field(default=3, ge=1)
    human_approval_required: bool = False
    assigned_to: str | None = Field(default=None, description="Actor/model assigned to this task")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    metadata: dict[str, Any] = Field(default_factory=dict)


class Plan(BaseModel):
    """Typed plan DAG (Section 9.2)."""

    plan_id: UUID = Field(default_factory=uuid4)
    goal_id: UUID
    version: int = Field(default=1, ge=1)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    tasks: list[Task] = Field(default_factory=list)
    status: PlanStatus = Field(default=PlanStatus.DRAFT)
    planner_model: ModelReference | None = None
    assumptions: list[str] = Field(default_factory=list)
    superseded_by: UUID | None = Field(default=None, description="Plan ID that supersedes this one")
    parent_plan_id: UUID | None = Field(default=None, description="Plan this was replanned from")
