"""Tests for SQLite state store projections."""

import tempfile
import uuid
from pathlib import Path

import pytest

from durable_agent_runtime.domain.enums import TaskStatus, WorkflowStatus
from durable_agent_runtime.persistence.state_store import StateStore


@pytest.fixture
def store() -> StateStore:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield StateStore(Path(tmpdir))


@pytest.fixture
def workflow_id() -> uuid.UUID:
    return uuid.uuid4()


class TestWorkflowState:
    def test_upsert_creates(self, store: StateStore, workflow_id: uuid.UUID) -> None:
        store.upsert_workflow(workflow_id, WorkflowStatus.CREATED)
        row = store.get_workflow(workflow_id)
        assert row is not None
        assert row.status == "created"

    def test_upsert_updates(self, store: StateStore, workflow_id: uuid.UUID) -> None:
        store.upsert_workflow(workflow_id, WorkflowStatus.CREATED)
        store.upsert_workflow(workflow_id, WorkflowStatus.RUNNING, tokens_used=500)
        row = store.get_workflow(workflow_id)
        assert row is not None
        assert row.status == "running"
        assert row.tokens_used == 500

    def test_get_nonexistent(self, store: StateStore) -> None:
        assert store.get_workflow(uuid.uuid4()) is None


class TestTaskState:
    def test_upsert_task(self, store: StateStore, workflow_id: uuid.UUID) -> None:
        task_id = uuid.uuid4()
        store.upsert_task(task_id, workflow_id, TaskStatus.PENDING)
        row = store.get_task(task_id)
        assert row is not None
        assert row.status == "pending"

    def test_task_lifecycle(self, store: StateStore, workflow_id: uuid.UUID) -> None:
        task_id = uuid.uuid4()
        store.upsert_task(task_id, workflow_id, TaskStatus.PENDING)
        store.upsert_task(task_id, workflow_id, TaskStatus.READY)
        store.upsert_task(task_id, workflow_id, TaskStatus.COMMITTED)
        row = store.get_task(task_id)
        assert row is not None
        assert row.status == "committed"

    def test_get_tasks_by_workflow(self, store: StateStore, workflow_id: uuid.UUID) -> None:
        t1 = uuid.uuid4()
        t2 = uuid.uuid4()
        t3 = uuid.uuid4()
        store.upsert_task(t1, workflow_id, TaskStatus.COMMITTED)
        store.upsert_task(t2, workflow_id, TaskStatus.READY)
        store.upsert_task(t3, workflow_id, TaskStatus.PENDING)

        tasks = store.get_tasks_by_workflow(workflow_id)
        assert len(tasks) == 3
        statuses = {t.status for t in tasks}
        assert statuses == {"committed", "ready", "pending"}

    def test_task_isolation(self, store: StateStore) -> None:
        wf1 = uuid.uuid4()
        wf2 = uuid.uuid4()
        t1 = uuid.uuid4()
        store.upsert_task(t1, wf1, TaskStatus.READY)
        assert len(store.get_tasks_by_workflow(wf1)) == 1
        assert len(store.get_tasks_by_workflow(wf2)) == 0


class TestIdempotency:
    def test_record_and_check(self, store: StateStore, workflow_id: uuid.UUID) -> None:
        store.record_idempotency("key-1", workflow_id, execution_status="committed")
        assert store.is_duplicate("key-1") is True

    def test_not_duplicate_if_not_committed(
        self, store: StateStore, workflow_id: uuid.UUID
    ) -> None:
        store.record_idempotency("key-2", workflow_id, execution_status="executing")
        assert store.is_duplicate("key-2") is False

    def test_nonexistent_key(self, store: StateStore) -> None:
        assert store.is_duplicate("nonexistent") is False
