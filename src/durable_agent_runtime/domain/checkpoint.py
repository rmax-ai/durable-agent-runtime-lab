"""Canonical checkpoint domain model (Section 6.9)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .enums import WorkflowStatus


class ModelConfiguration(BaseModel):
    """Provider and model configuration at checkpoint time."""

    provider: str
    model: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class ToolConfiguration(BaseModel):
    """Tool configuration at checkpoint time."""

    tool_name: str
    version: str
    sandbox_mode: str
    parameters: dict[str, Any] = Field(default_factory=dict)


class Checkpoint(BaseModel):
    """Workflow checkpoint capturing full state for recovery (Section 6.9)."""

    checkpoint_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    sequence: int = Field(ge=0, description="Checkpoint sequence number")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))

    # Repository state
    git_commit: str = Field(description="Git commit SHA at checkpoint time")
    git_branch: str | None = None

    # Workflow state
    workflow_status: WorkflowStatus
    active_plan_id: UUID | None = None
    active_plan_version: int | None = None

    # Task state snapshot
    task_states: dict[str, str] = Field(
        default_factory=dict,
        description="task_id -> TaskStatus mapping at checkpoint time",
    )

    # Event ledger position
    last_event_sequence: int = 0
    last_event_hash: str | None = None

    # Budget state
    tokens_used: int = 0
    model_calls: int = 0
    tool_calls: int = 0
    estimated_cost: float = 0.0
    budget_remaining: float | None = None

    # Artifact references
    artifact_refs: list[str] = Field(default_factory=list)
    model_response_refs: list[str] = Field(default_factory=list)

    # Configuration
    model_configuration: ModelConfiguration | None = None
    tool_configs: list[ToolConfiguration] = Field(default_factory=list)

    # Integrity
    payload_hash: str = ""
    checksum: str = ""

    metadata: dict[str, Any] = Field(default_factory=dict)
