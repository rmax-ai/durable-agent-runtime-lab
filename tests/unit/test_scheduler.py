"""Tests for the multi-task DAG scheduler."""

import tempfile
import uuid
from pathlib import Path
from uuid import UUID

import pytest

from durable_agent_runtime.domain import Plan, Task
from durable_agent_runtime.domain.enums import TaskStatus
from durable_agent_runtime.orchestration.engine import OrchestratorEngine
from durable_agent_runtime.orchestration.scheduler import TaskScheduler

# ── Fixtures ────────────────────────────────────────────────────────────────


@pytest.fixture
def engine() -> OrchestratorEngine:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield OrchestratorEngine(Path(tmpdir))


@pytest.fixture
def scheduler(engine: OrchestratorEngine) -> TaskScheduler:
    return TaskScheduler(engine.state, engine)


@pytest.fixture
def goal_id() -> UUID:
    return uuid.uuid4()


def _make_plan(goal_id: UUID, tasks: list[Task]) -> Plan:
    return Plan(goal_id=goal_id, tasks=tasks)


def _register_and_setup(engine: OrchestratorEngine, wf_id: UUID, plan: Plan) -> None:
    """Register tasks into a fresh workflow with COMPILED→PLANNED→RUNNING."""
    engine.register_tasks(wf_id, plan)


# ── Chain dependency test (A → B → C) ────────────────────────────────────────


class TestChainDependency:
    """Sequential execution: A→B→C. Each task depends on the previous."""

    def test_chain_initial_ready(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """Only A (no deps) should be promotable initially."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="First", dependencies=[]),
                Task(task_id=b, title="B", description="Second", dependencies=[a]),
                Task(task_id=c, title="C", description="Third", dependencies=[b]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        promoted = scheduler.promote_pending(wf_id, plan)
        assert promoted == 1  # only A

        ready = scheduler.get_ready(wf_id, plan)
        assert a in ready
        assert b not in ready
        assert c not in ready

    def test_chain_after_a_committed(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """After A is COMMITTED, B becomes ready."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="First", dependencies=[]),
                Task(task_id=b, title="B", description="Second", dependencies=[a]),
                Task(task_id=c, title="C", description="Third", dependencies=[b]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Promote A
        scheduler.promote_pending(wf_id, plan)
        # Manually commit A (simulating full lifecycle)
        engine.state.upsert_task(a, wf_id, TaskStatus.COMMITTED)

        promoted = scheduler.promote_pending(wf_id, plan)
        assert promoted == 1  # B

        ready = scheduler.get_ready(wf_id, plan)
        assert b in ready
        assert c not in ready  # B not committed yet

    def test_chain_full_sequence(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """Simulate the full sequential execution of A→B→C."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="First", dependencies=[]),
                Task(task_id=b, title="B", description="Second", dependencies=[a]),
                Task(task_id=c, title="C", description="Third", dependencies=[b]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Step 1: A becomes ready
        assert scheduler.promote_pending(wf_id, plan) == 1
        ready = scheduler.get_ready(wf_id, plan)
        assert ready == [a]

        # Commit A
        engine.state.upsert_task(a, wf_id, TaskStatus.COMMITTED)

        # Step 2: B becomes ready
        assert scheduler.promote_pending(wf_id, plan) == 1
        ready = scheduler.get_ready(wf_id, plan)
        assert b in ready
        assert a not in ready  # A is committed, not ready

        # Commit B
        engine.state.upsert_task(b, wf_id, TaskStatus.COMMITTED)

        # Step 3: C becomes ready
        assert scheduler.promote_pending(wf_id, plan) == 1
        ready = scheduler.get_ready(wf_id, plan)
        assert c in ready

        # Commit C
        engine.state.upsert_task(c, wf_id, TaskStatus.COMMITTED)

        # Step 4: No more PENDING tasks
        assert scheduler.promote_pending(wf_id, plan) == 0
        all_tasks = engine.state.get_tasks_by_workflow(wf_id)
        statuses = {UUID(row.task_id): TaskStatus(row.status) for row in all_tasks}
        assert all(s == TaskStatus.COMMITTED for s in statuses.values())


# ── Diamond dependency test (A → B,C → D) ───────────────────────────────────


class TestDiamondDependency:
    """Diamond topology: A→B, A→C, B→D, C→D."""

    def test_diamond_initial(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """Only A (no deps) should be promotable initially."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="Root", dependencies=[]),
                Task(task_id=b, title="B", description="Child1", dependencies=[a]),
                Task(task_id=c, title="C", description="Child2", dependencies=[a]),
                Task(task_id=d, title="D", description="Leaf", dependencies=[b, c]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        assert scheduler.promote_pending(wf_id, plan) == 1
        ready = scheduler.get_ready(wf_id, plan)
        assert a in ready
        assert b not in ready
        assert c not in ready
        assert d not in ready

    def test_diamond_after_a(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """After A is COMMITTED, B and C become ready."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="Root", dependencies=[]),
                Task(task_id=b, title="B", description="Child1", dependencies=[a]),
                Task(task_id=c, title="C", description="Child2", dependencies=[a]),
                Task(task_id=d, title="D", description="Leaf", dependencies=[b, c]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Promote and commit A
        scheduler.promote_pending(wf_id, plan)
        engine.state.upsert_task(a, wf_id, TaskStatus.COMMITTED)

        assert scheduler.promote_pending(wf_id, plan) == 2  # B and C
        ready = scheduler.get_ready(wf_id, plan)
        assert b in ready
        assert c in ready
        assert d not in ready

    def test_diamond_after_b_and_c(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """After B and C are both COMMITTED, D becomes ready."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="Root", dependencies=[]),
                Task(task_id=b, title="B", description="Child1", dependencies=[a]),
                Task(task_id=c, title="C", description="Child2", dependencies=[a]),
                Task(task_id=d, title="D", description="Leaf", dependencies=[b, c]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Promote and commit A, B, C
        scheduler.promote_pending(wf_id, plan)
        engine.state.upsert_task(a, wf_id, TaskStatus.COMMITTED)
        scheduler.promote_pending(wf_id, plan)
        engine.state.upsert_task(b, wf_id, TaskStatus.COMMITTED)
        engine.state.upsert_task(c, wf_id, TaskStatus.COMMITTED)

        assert scheduler.promote_pending(wf_id, plan) == 1  # D
        ready = scheduler.get_ready(wf_id, plan)
        assert d in ready

    def test_diamond_d_requires_both(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """D should NOT be ready if only one of B or C is committed."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="Root", dependencies=[]),
                Task(task_id=b, title="B", description="Child1", dependencies=[a]),
                Task(task_id=c, title="C", description="Child2", dependencies=[a]),
                Task(task_id=d, title="D", description="Leaf", dependencies=[b, c]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Promote and commit A, then just B
        scheduler.promote_pending(wf_id, plan)
        engine.state.upsert_task(a, wf_id, TaskStatus.COMMITTED)
        scheduler.promote_pending(wf_id, plan)
        engine.state.upsert_task(b, wf_id, TaskStatus.COMMITTED)
        # C still PENDING

        assert scheduler.promote_pending(wf_id, plan) == 0  # D not ready
        ready = scheduler.get_ready(wf_id, plan)
        assert d not in ready


# ── Circular dependency detection ────────────────────────────────────────────


class TestCircularDependencyDetection:
    """Detect circular dependencies in the plan DAG."""

    def test_no_cycles(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[]),
                Task(task_id=b, title="B", description="", dependencies=[a]),
                Task(task_id=c, title="C", description="", dependencies=[b]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert cycles == []

    def test_simple_cycle(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        a, b = uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[b]),
                Task(task_id=b, title="B", description="", dependencies=[a]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert len(cycles) == 1
        assert a in cycles[0]
        assert b in cycles[0]

    def test_self_loop(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        a = uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[a]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert len(cycles) == 1
        assert a in cycles[0]

    def test_three_node_cycle(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[c]),
                Task(task_id=b, title="B", description="", dependencies=[a]),
                Task(task_id=c, title="C", description="", dependencies=[b]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert len(cycles) >= 1
        all_ids = {a, b, c}
        cycle_ids = set()
        for cycle in cycles:
            cycle_ids.update(cycle)
        assert all_ids.issubset(cycle_ids)

    def test_disconnected_no_cycle(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[]),
                Task(task_id=b, title="B", description="", dependencies=[]),
                Task(task_id=c, title="C", description="", dependencies=[]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert cycles == []

    def test_diamond_no_cycle(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[]),
                Task(task_id=b, title="B", description="", dependencies=[a]),
                Task(task_id=c, title="C", description="", dependencies=[a]),
                Task(task_id=d, title="D", description="", dependencies=[b, c]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert cycles == []

    def test_dangling_dep_ignored(self, scheduler: TaskScheduler, goal_id: UUID) -> None:
        """Dependency pointing to a task not in the plan should be ignored."""
        a = uuid.uuid4()
        missing = uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[missing]),
            ],
        )
        cycles = scheduler.detect_circular_deps(plan)
        assert cycles == []


# ── Failed dependency handling ────────────────────────────────────────────────


class TestFailedDependency:
    """Tasks with FAILED dependencies should be BLOCKED, not READY."""

    def test_failed_dep_blocks_sibling(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """B depends on A. If A fails, B should be BLOCKED."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b = uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="Root", dependencies=[]),
                Task(task_id=b, title="B", description="Dep on A", dependencies=[a]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Promote A
        scheduler.promote_pending(wf_id, plan)
        # A fails (simulate full lifecycle ending in FAILED)
        engine.state.upsert_task(a, wf_id, TaskStatus.FAILED)

        # B should be BLOCKED now (failed dep)
        promoted = scheduler.promote_pending(wf_id, plan)
        assert promoted == 0  # B not promoted to READY

        b_row = engine.state.get_task(b)
        assert b_row is not None
        assert TaskStatus(b_row.status) == TaskStatus.BLOCKED

    def test_failed_dep_after_commit(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """A→B, C. B depends on A, C is independent. A fails → B blocked, C still goes."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="Root", dependencies=[]),
                Task(task_id=b, title="B", description="Dep on A", dependencies=[a]),
                Task(task_id=c, title="C", description="Independent", dependencies=[]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        # Promote: A and C have no deps
        promoted = scheduler.promote_pending(wf_id, plan)
        assert promoted == 2  # A and C

        # A fails, commit C
        engine.state.upsert_task(a, wf_id, TaskStatus.FAILED)
        engine.state.upsert_task(c, wf_id, TaskStatus.COMMITTED)

        # B should be BLOCKED (A failed)
        promoted = scheduler.promote_pending(wf_id, plan)
        assert promoted == 0

        b_row = engine.state.get_task(b)
        assert b_row is not None
        assert TaskStatus(b_row.status) == TaskStatus.BLOCKED


# ── Edge cases ────────────────────────────────────────────────────────────────


class TestEdgeCases:
    """Edge cases for the scheduler."""

    def test_no_tasks(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """Empty plan should work gracefully."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        plan = _make_plan(goal_id, [])
        _register_and_setup(engine, wf_id, plan)

        assert scheduler.promote_pending(wf_id, plan) == 0
        assert scheduler.get_ready(wf_id, plan) == []

    def test_all_independent(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """All tasks with no deps should be promotable immediately."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [
                Task(task_id=a, title="A", description="", dependencies=[]),
                Task(task_id=b, title="B", description="", dependencies=[]),
                Task(task_id=c, title="C", description="", dependencies=[]),
            ],
        )
        _register_and_setup(engine, wf_id, plan)

        assert scheduler.promote_pending(wf_id, plan) == 3
        ready = scheduler.get_ready(wf_id, plan)
        assert len(ready) == 3


class TestRetryWaitRequeue:
    def test_retry_wait_tasks_are_requeued(
        self, engine: OrchestratorEngine, scheduler: TaskScheduler, goal_id: UUID
    ) -> None:
        """Tasks in RETRY_WAIT should be promoted back to READY."""
        wf_id = engine.create_workflow(goal_id, "/tmp/test")
        task_id = uuid.uuid4()
        plan = _make_plan(
            goal_id,
            [Task(task_id=task_id, title="Retry", description="Retry task", dependencies=[])],
        )
        _register_and_setup(engine, wf_id, plan)
        engine.state.upsert_task(task_id, wf_id, TaskStatus.RETRY_WAIT)

        requeued = scheduler.requeue_retry_wait(wf_id)

        assert requeued == 1
        ready = scheduler.get_ready(wf_id, plan)
        assert ready == [task_id]
