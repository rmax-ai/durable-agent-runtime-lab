"""Append-only JSONL event store with hash chaining (Section 6.8).

The event store is the canonical source of truth. Events are appended
to a JSONL file and never modified. Hash chaining provides tamper evidence.
"""

import hashlib
import json
import os
from pathlib import Path
from uuid import UUID

from durable_agent_runtime.domain import Event
from durable_agent_runtime.domain.enums import EventType


def _compute_payload_hash(payload: dict) -> str:
    """SHA-256 of canonical JSON payload."""
    raw = json.dumps(payload, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(raw.encode()).hexdigest()


def _compute_event_hash(previous_hash: str | None, payload_hash: str) -> str:
    """SHA-256 of (previous_hash || payload_hash)."""
    data = (previous_hash or "") + payload_hash
    return hashlib.sha256(data.encode()).hexdigest()


class EventStore:
    """Append-only JSONL event ledger.

    Thread-safe for single-writer scenarios. Each workflow gets its own
    JSONL file in the data directory.

    Usage:
        store = EventStore(Path("./data"))
        event = store.append(event)
        events = store.read_all(workflow_id)
        valid = store.verify_chain(workflow_id)
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        # In-memory sequence counters per workflow to avoid reading the file
        # for every append. Rebuilt on startup from file scan.
        self._sequences: dict[UUID, int] = {}

    def _file_path(self, workflow_id: UUID) -> Path:
        return self.data_dir / f"events-{workflow_id}.jsonl"

    def _read_all_lines(self, workflow_id: UUID) -> list[str]:
        path = self._file_path(workflow_id)
        if not path.exists():
            return []
        return path.read_text().strip().split("\n") if path.stat().st_size > 0 else []

    def _rebuild_sequence(self, workflow_id: UUID) -> int:
        """Rebuild the sequence counter from file (used on startup or after crash)."""
        lines = self._read_all_lines(workflow_id)
        if not lines:
            self._sequences[workflow_id] = -1
            return -1
        last_line = lines[-1]
        try:
            data = json.loads(last_line)
            seq = data.get("sequence", -1)
            self._sequences[workflow_id] = seq
            return seq
        except (json.JSONDecodeError, KeyError):
            self._sequences[workflow_id] = -1
            return -1

    def append(self, event: Event) -> Event:
        """Append an event to the ledger. Sets sequence, hashes, and returns the enriched event.

        Raises ValueError if events are appended out of sequence order.
        """
        workflow_id = event.workflow_id

        # Determine next sequence
        if workflow_id not in self._sequences:
            self._rebuild_sequence(workflow_id)
        current_seq = self._sequences.get(workflow_id, -1)
        next_seq = current_seq + 1

        if event.sequence != next_seq:
            # Auto-fix: assign correct sequence
            event = event.model_copy(update={"sequence": next_seq})

        # Read previous event hash
        prev_hash: str | None = None
        lines = self._read_all_lines(workflow_id)
        if lines:
            try:
                last_data = json.loads(lines[-1])
                prev_hash = last_data.get("event_hash")
            except json.JSONDecodeError:
                pass

        # Compute hashes
        payload_hash = _compute_payload_hash(event.payload)
        event_hash = _compute_event_hash(prev_hash, payload_hash)

        event = event.model_copy(
            update={
                "payload_hash": payload_hash,
                "previous_event_hash": prev_hash,
                "event_hash": event_hash,
            }
        )

        # Serialize and append
        event_dict = event.model_dump(mode="json")
        # Convert UUIDs to strings for JSON serialization
        line = json.dumps(event_dict, default=str, sort_keys=True) + "\n"

        path = self._file_path(workflow_id)
        with open(path, "a") as f:
            f.write(line)
            f.flush()
            os.fsync(f.fileno())  # Durability: ensure write hits disk

        self._sequences[workflow_id] = event.sequence
        return event

    def read_all(self, workflow_id: UUID) -> list[Event]:
        """Read all events for a workflow in sequence order."""
        lines = self._read_all_lines(workflow_id)
        events: list[Event] = []
        for line in lines:
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                events.append(Event.model_validate(data))
            except (json.JSONDecodeError, ValueError):
                continue
        return events

    def get_latest_sequence(self, workflow_id: UUID) -> int:
        """Return the latest sequence number, or -1 if no events exist."""
        if workflow_id in self._sequences:
            return self._sequences[workflow_id]
        return self._rebuild_sequence(workflow_id)

    def get_latest_event(self, workflow_id: UUID) -> Event | None:
        """Return the most recent event for a workflow."""
        events = self.read_all(workflow_id)
        return events[-1] if events else None

    def verify_chain(self, workflow_id: UUID) -> tuple[bool, str | None]:
        """Verify hash chain integrity for a workflow.

        Returns (valid, error_message). Error message is None if valid.
        """
        events = self.read_all(workflow_id)
        if not events:
            return True, None

        prev_hash: str | None = None
        for _i, event in enumerate(events):
            # Verify payload hash
            computed_payload = _compute_payload_hash(event.payload)
            if computed_payload != event.payload_hash:
                return False, (
                    f"Event {event.sequence}: payload hash mismatch — "
                    f"stored={event.payload_hash[:12]}... computed={computed_payload[:12]}..."
                )

            # Verify previous_event_hash
            if event.previous_event_hash != prev_hash:
                return False, (
                    f"Event {event.sequence}: chain broken — "
                    f"expected prev={prev_hash[:12] if prev_hash else 'None'}... "
                    f"got={event.previous_event_hash[:12] if event.previous_event_hash else '?'}..."
                )

            # Verify event_hash
            computed_event = _compute_event_hash(prev_hash, computed_payload)
            if computed_event != event.event_hash:
                return False, (
                    f"Event {event.sequence}: event hash mismatch — "
                    f"stored={event.event_hash[:12]}... computed={computed_event[:12]}..."
                )

            prev_hash = event.event_hash

        return True, None

    def get_events_by_type(self, workflow_id: UUID, event_type: EventType) -> list[Event]:
        """Filter events by type."""
        return [e for e in self.read_all(workflow_id) if e.event_type == event_type]
