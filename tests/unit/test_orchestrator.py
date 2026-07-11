"""Tests for the deterministic orchestrator engine."""

import tempfile
import uuid
from pathlib import Path

import pytest

from durable_agent_runtime.domain import Plan, Task
from durable_agent_runtime.domain.enums import TaskStatus, WorkflowStatus
from durable_agent_runtime.orchestration.engine import OrchestratorEngine
from durable_agent_runtime.persistence.event_store import EventStore


@pytest.fixture
def engine() -> OrchestratorEngine:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield OrchestratorEngine(Path(tmpdir))


@pytest.fixture
def goal_id() -> uuid.UUID:
    return uuid.uuid4()


class TestWorkflowLifecycle:
    def test_create_workflow(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.CREATED

        events = engine.events.read_all(wf_id)
        assert len(events) == 1
        assert events[0].event_type.value == "workflow_created"

    def test_full_workflow_lifecycle(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")

        engine.transition_workflow(wf_id, WorkflowStatus.COMPILED)
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.COMPILED

        engine.transition_workflow(wf_id, WorkflowStatus.PLANNED)
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.PLANNED

        engine.transition_workflow(wf_id, WorkflowStatus.RUNNING)
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.RUNNING

        engine.transition_workflow(wf_id, WorkflowStatus.PAUSED)
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.PAUSED

        engine.transition_workflow(wf_id, WorkflowStatus.RUNNING)
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.RUNNING

        engine.transition_workflow(wf_id, WorkflowStatus.COMPLETED)
        assert engine.get_workflow_status(wf_id) == WorkflowStatus.COMPLETED

    def test_invalid_transition_raises(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        # Can't go CREATED → RUNNING
        with pytest.raises(ValueError, match="Invalid workflow transition"):
            engine.transition_workflow(wf_id, WorkflowStatus.RUNNING)


class TestTaskLifecycle:
    def test_register_and_transition_tasks(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        engine.transition_workflow(wf_id, WorkflowStatus.COMPILED)
        engine.transition_workflow(wf_id, WorkflowStatus.PLANNED)

        t1 = uuid.uuid4()
        t2 = uuid.uuid4()
        plan = Plan(
            goal_id=goal_id,
            tasks=[
                Task(task_id=t1, title="Task 1", description="First task", estimated_complexity=1),
                Task(task_id=t2, title="Task 2", description="Second task", estimated_complexity=2),
            ],
        )
        engine.register_tasks(wf_id, plan)

        # Both tasks start as PENDING
        tasks = engine.state.get_tasks_by_workflow(wf_id)
        assert len(tasks) == 2
        assert all(TaskStatus(t.status) == TaskStatus.PENDING for t in tasks)

        # Transition t1 through its lifecycle
        engine.transition_task(t1, wf_id, TaskStatus.READY)
        engine.transition_task(t1, wf_id, TaskStatus.CLAIMED)
        engine.transition_task(t1, wf_id, TaskStatus.PROPOSING)
        engine.transition_task(t1, wf_id, TaskStatus.VERIFYING)
        engine.transition_task(t1, wf_id, TaskStatus.EXECUTING)
        engine.transition_task(t1, wf_id, TaskStatus.POST_VERIFYING)
        engine.transition_task(t1, wf_id, TaskStatus.COMMITTED)

        # Verify t1 is COMMITTED
        t1_row = engine.state.get_task(t1)
        assert t1_row is not None
        assert t1_row.status == "committed"

        # t2 should still be PENDING
        t2_row = engine.state.get_task(t2)
        assert t2_row is not None
        assert t2_row.status == "pending"

    def test_invalid_task_transition_raises(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        t1 = uuid.uuid4()
        plan = Plan(goal_id=goal_id, tasks=[Task(task_id=t1, title="Task 1", description="Test", estimated_complexity=1)])
        engine.register_tasks(wf_id, plan)

        # Can't go PENDING → EXECUTING
        with pytest.raises(ValueError, match="Invalid task transition"):
            engine.transition_task(t1, wf_id, TaskStatus.EXECUTING)


class TestBudgetTracking:
    def test_record_model_call(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        engine.record_model_call(wf_id, input_tokens=100, output_tokens=50)

        row = engine.state.get_workflow(wf_id)
        assert row is not None
        assert row.tokens_used == 150
        assert row.model_calls == 1

    def test_record_tool_call(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        engine.record_tool_call(wf_id)
        engine.record_tool_call(wf_id)

        row = engine.state.get_workflow(wf_id)
        assert row is not None
        assert row.tool_calls == 2


class TestEventIntegrity:
    def test_workflow_events_are_hash_chained(self, engine: OrchestratorEngine, goal_id: uuid.UUID) -> None:
        wf_id = engine.create_workflow(goal_id, "/tmp/test-repo")
        engine.transition_workflow(wf_id, WorkflowStatus.COMPILED)
        engine.transition_workflow(wf_id, WorkflowStatus.PLANNED)

        valid, error = engine.events.verify_chain(wf_id)
        assert valid is True
        assert error is None
