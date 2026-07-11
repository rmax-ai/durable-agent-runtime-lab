"""Canonical event domain model (Section 9.7)."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from .enums import EventType


class Event(BaseModel):
    """Immutable event in the append-only ledger (Section 9.7).

    Events form a hash-chained, append-only log. Each event references its
    predecessor by hash, providing tamper-evident integrity.
    """

    sequence: int = Field(ge=0, description="Monotonic sequence number")
    event_id: UUID = Field(default_factory=uuid4)
    workflow_id: UUID
    task_id: UUID | None = None
    event_type: EventType
    actor_id: str = Field(description="Actor that produced this event")
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    causation_id: UUID | None = Field(
        default=None, description="Event that directly caused this one"
    )
    correlation_id: UUID = Field(
        default_factory=uuid4, description="Groups related events across causations"
    )
    payload: dict[str, Any] = Field(default_factory=dict)
    payload_hash: str = Field(default="", description="SHA-256 of serialized payload")
    previous_event_hash: str | None = Field(default=None, description="SHA-256 of previous event")
    event_hash: str = Field(default="", description="SHA-256 of this event (payload + metadata)")
    metadata: dict[str, Any] = Field(default_factory=dict)
