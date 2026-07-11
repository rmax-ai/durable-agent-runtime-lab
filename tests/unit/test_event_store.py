"""Tests for the append-only JSONL event store with hash chaining."""

import tempfile
import uuid
from pathlib import Path

import pytest

from durable_agent_runtime.domain import Event
from durable_agent_runtime.domain.enums import EventType
from durable_agent_runtime.persistence.event_store import EventStore


@pytest.fixture
def store() -> EventStore:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield EventStore(Path(tmpdir))


@pytest.fixture
def workflow_id() -> uuid.UUID:
    return uuid.uuid4()


class TestEventStoreAppend:
    def test_append_single_event(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        event = Event(
            sequence=0,
            workflow_id=workflow_id,
            event_type=EventType.WORKFLOW_CREATED,
            actor_id="test",
        )
        result = store.append(event)
        assert result.sequence == 0
        assert result.payload_hash
        assert result.event_hash
        assert result.previous_event_hash is None  # first event

    def test_append_two_events_chain_hashes(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        e1 = store.append(Event(
            sequence=0, workflow_id=workflow_id,
            event_type=EventType.WORKFLOW_CREATED, actor_id="test",
        ))
        e2 = store.append(Event(
            sequence=1, workflow_id=workflow_id,
            event_type=EventType.GOAL_COMPILED, actor_id="test",
        ))
        assert e2.previous_event_hash == e1.event_hash
        assert e1.event_hash != e2.event_hash

    def test_read_all_returns_events_in_order(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        for i in range(5):
            store.append(Event(
                sequence=i, workflow_id=workflow_id,
                event_type=EventType.WORKFLOW_CREATED, actor_id="test",
                payload={"index": i},
            ))
        events = store.read_all(workflow_id)
        assert len(events) == 5
        for i, e in enumerate(events):
            assert e.sequence == i

    def test_verify_chain_valid(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        for i in range(10):
            store.append(Event(
                sequence=i, workflow_id=workflow_id,
                event_type=EventType.TASK_READY if i > 0 else EventType.WORKFLOW_CREATED,
                actor_id="test",
                payload={"step": i},
            ))
        valid, error = store.verify_chain(workflow_id)
        assert valid is True
        assert error is None

    def test_verify_chain_empty(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        valid, error = store.verify_chain(workflow_id)
        assert valid is True
        assert error is None

    def test_latest_sequence(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        assert store.get_latest_sequence(workflow_id) == -1
        store.append(Event(sequence=0, workflow_id=workflow_id, event_type=EventType.WORKFLOW_CREATED, actor_id="test"))
        assert store.get_latest_sequence(workflow_id) == 0
        store.append(Event(sequence=1, workflow_id=workflow_id, event_type=EventType.GOAL_COMPILED, actor_id="test"))
        assert store.get_latest_sequence(workflow_id) == 1

    def test_get_events_by_type(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        store.append(Event(sequence=0, workflow_id=workflow_id, event_type=EventType.WORKFLOW_CREATED, actor_id="test"))
        store.append(Event(sequence=1, workflow_id=workflow_id, event_type=EventType.ACTION_COMMITTED, actor_id="test"))
        store.append(Event(sequence=2, workflow_id=workflow_id, event_type=EventType.ACTION_COMMITTED, actor_id="test"))
        store.append(Event(sequence=3, workflow_id=workflow_id, event_type=EventType.ACTION_REJECTED, actor_id="test"))

        committed = store.get_events_by_type(workflow_id, EventType.ACTION_COMMITTED)
        assert len(committed) == 2

    def test_isolation_between_workflows(self, store: EventStore) -> None:
        wf1 = uuid.uuid4()
        wf2 = uuid.uuid4()

        store.append(Event(sequence=0, workflow_id=wf1, event_type=EventType.WORKFLOW_CREATED, actor_id="test"))
        store.append(Event(sequence=0, workflow_id=wf2, event_type=EventType.WORKFLOW_CREATED, actor_id="test"))

        assert len(store.read_all(wf1)) == 1
        assert len(store.read_all(wf2)) == 1


class TestEventStoreTamperDetection:
    def test_detect_payload_tampering(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        store.append(Event(sequence=0, workflow_id=workflow_id, event_type=EventType.WORKFLOW_CREATED, actor_id="test", payload={"key": "original"}))

        # Tamper with the file directly
        path = store._file_path(workflow_id)
        content = path.read_text()
        tampered = content.replace('"original"', '"tampered"')
        path.write_text(tampered)

        valid, error = store.verify_chain(workflow_id)
        assert valid is False
        assert "payload hash mismatch" in (error or "")

    def test_detect_missing_event(self, store: EventStore, workflow_id: uuid.UUID) -> None:
        for i in range(3):
            store.append(Event(sequence=i, workflow_id=workflow_id, event_type=EventType.WORKFLOW_CREATED, actor_id="test"))

        path = store._file_path(workflow_id)
        lines = path.read_text().strip().split("\n")
        # Remove the middle event
        path.write_text(lines[0] + "\n" + lines[2] + "\n")

        valid, error = store.verify_chain(workflow_id)
        assert valid is False
        assert "chain broken" in (error or "")
