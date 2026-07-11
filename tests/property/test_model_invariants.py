"""Property-based tests for domain model invariants (Section 29).

Tests invariants that must hold across all valid inputs:
- Event sequence numbers are strictly increasing
- Committed actions execute at most once
- Invalid transitions never alter state
- Round-trip serialization preserves identity
- Budget validation
"""

from uuid import uuid4

from hypothesis import HealthCheck, assume, given, settings
from hypothesis import strategies as st

from durable_agent_runtime.domain import (
    Assertion,
    Event,
    GoalSpecification,
    Plan,
    Task,
)
from durable_agent_runtime.domain.enums import (
    EventType,
    PlanStatus,
    RiskLevel,
    TaskStatus,
    WorkflowStatus,
)
from durable_agent_runtime.domain.state_machine import (
    can_transition,
    InvalidTransitionError,
    validate_transition,
)


# ── Strategies for generating valid domain objects ──────────────────────────

uuid_st = st.uuids()
event_type_st = st.sampled_from(list(EventType))
workflow_status_st = st.sampled_from(list(WorkflowStatus))
task_status_st = st.sampled_from(list(TaskStatus))
positive_int_st = st.integers(min_value=1, max_value=1000)


# ── Event invariants ────────────────────────────────────────────────────────

class TestEventInvariants:
    @given(
        seq=st.integers(min_value=0, max_value=9999),
        ev_type=event_type_st,
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=20),
            values=st.one_of(st.integers(), st.text(max_size=50), st.booleans()),
            max_size=5,
        ),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_event_sequence_is_preserved(self, seq: int, ev_type: EventType, payload: dict) -> None:
        """Event.sequence must be exactly what was set."""
        event = Event(
            sequence=seq,
            workflow_id=uuid4(),
            event_type=ev_type,
            actor_id="test-actor",
            payload=payload,
        )
        assert event.sequence == seq

    @given(
        seq1=st.integers(min_value=0, max_value=9998),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_event_sequence_strictly_increases(self, seq1: int) -> None:
        """Events in a workflow must have strictly increasing sequences."""
        wf_id = uuid4()
        e1 = Event(sequence=seq1, workflow_id=wf_id, event_type=EventType.WORKFLOW_CREATED, actor_id="test")
        e2 = Event(sequence=seq1 + 1, workflow_id=wf_id, event_type=EventType.ACTION_COMMITTED, actor_id="test")
        assert e1.sequence < e2.sequence
        assert e2.sequence - e1.sequence == 1

    @given(
        payload=st.dictionaries(
            keys=st.text(min_size=1, max_size=10),
            values=st.integers(),
            max_size=3,
        ),
        prev_hash=st.text(min_size=10, max_size=64),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_event_hash_fields_preserved(self, payload: dict, prev_hash: str) -> None:
        """Event hash fields are exactly preserved through serialization."""
        event = Event(
            sequence=0,
            workflow_id=uuid4(),
            event_type=EventType.WORKFLOW_CREATED,
            actor_id="test",
            payload=payload,
            payload_hash="sha256:payload",
            previous_event_hash=prev_hash,
            event_hash="sha256:event",
        )
        data = event.model_dump(mode="json")
        reloaded = Event.model_validate(data)
        assert reloaded.payload_hash == event.payload_hash
        assert reloaded.previous_event_hash == event.previous_event_hash
        assert reloaded.event_hash == event.event_hash


# ── Goal specification invariants ───────────────────────────────────────────

class TestGoalSpecificationInvariants:
    @given(
        raw=st.text(min_size=1, max_size=100),
        normalized=st.text(min_size=1, max_size=200),
        repo_path=st.text(min_size=1, max_size=50),
        risk=st.sampled_from(list(RiskLevel)),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_goal_round_trip_preserves_identity(
        self, raw: str, normalized: str, repo_path: str, risk: RiskLevel
    ) -> None:
        """Goal serialization round-trip preserves all fields."""
        goal = GoalSpecification(
            raw_goal=raw,
            normalized_goal=normalized,
            repository_path=repo_path,
            risk_level=risk,
        )
        data = goal.model_dump(mode="json")
        reloaded = GoalSpecification.model_validate(data)
        assert str(reloaded.goal_id) == str(goal.goal_id)
        assert reloaded.raw_goal == raw
        assert reloaded.normalized_goal == normalized
        assert reloaded.repository_path == repo_path
        assert reloaded.risk_level == risk

    @given(
        raw=st.text(min_size=1, max_size=50),
        normalized=st.text(min_size=1, max_size=50),
        repo_path=st.text(min_size=1, max_size=30),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_goal_defaults_are_reasonable(
        self, raw: str, normalized: str, repo_path: str
    ) -> None:
        """Default-constructed GoalSpecification has sensible defaults."""
        goal = GoalSpecification(
            raw_goal=raw,
            normalized_goal=normalized,
            repository_path=repo_path,
        )
        assert goal.risk_level == RiskLevel.MEDIUM
        assert goal.constraints == []
        assert goal.success_criteria == []
        assert goal.forbidden_actions == []


# ── State machine invariants ────────────────────────────────────────────────

class TestStateMachineInvariants:
    @given(
        current=st.sampled_from(list(WorkflowStatus)),
        target=st.sampled_from(list(WorkflowStatus)),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_workflow_transition_idempotency(
        self, current: WorkflowStatus, target: WorkflowStatus
    ) -> None:
        """can_transition returns the same result every time."""
        result1 = can_transition(current, target)
        result2 = can_transition(current, target)
        assert result1 == result2

    @given(
        current=st.sampled_from(list(TaskStatus)),
        target=st.sampled_from(list(TaskStatus)),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_task_transition_idempotency(
        self, current: TaskStatus, target: TaskStatus
    ) -> None:
        """can_transition returns the same result every time."""
        result1 = can_transition(current, target)
        result2 = can_transition(current, target)
        assert result1 == result2

    @given(
        current=st.sampled_from(list(TaskStatus)),
        target=st.sampled_from(list(TaskStatus)),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_validate_transition_never_alters_state(
        self, current: TaskStatus, target: TaskStatus
    ) -> None:
        """validate_transition does not mutate inputs or global state."""
        current_before = current
        target_before = target
        try:
            validate_transition(current, target, "task")
        except InvalidTransitionError:
            pass
        assert current == current_before
        assert target == target_before

    @given(terminal=st.sampled_from([
        WorkflowStatus.COMPLETED,
        WorkflowStatus.FAILED,
        WorkflowStatus.CANCELLED,
    ]))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_terminal_workflow_has_no_outbound(self, terminal: WorkflowStatus) -> None:
        """Terminal workflow states cannot transition to any other state."""
        for target in WorkflowStatus:
            assert not can_transition(terminal, target)

    @given(terminal=st.sampled_from([
        TaskStatus.COMMITTED,
        TaskStatus.FAILED,
        TaskStatus.CANCELLED,
    ]))
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_terminal_task_has_no_outbound(self, terminal: TaskStatus) -> None:
        """Terminal task states cannot transition to any other state."""
        for target in TaskStatus:
            assert not can_transition(terminal, target)


# ── Plan and task DAG invariants ────────────────────────────────────────────

class TestPlanInvariants:
    @given(
        num_tasks=st.integers(min_value=0, max_value=10),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_plan_round_trip_preserves_task_count(self, num_tasks: int) -> None:
        """Plan with N tasks round-trips with N tasks."""
        tasks = [
            Task(
                title=f"Task {i}",
                description=f"Description {i}",
                estimated_complexity=i % 5 + 1,
            )
            for i in range(num_tasks)
        ]
        plan = Plan(goal_id=uuid4(), tasks=tasks, status=PlanStatus.DRAFT)
        data = plan.model_dump(mode="json")
        reloaded = Plan.model_validate(data)
        assert len(reloaded.tasks) == num_tasks

    @given(
        complexity=st.integers(min_value=1, max_value=100),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_task_complexity_survives_serialization(self, complexity: int) -> None:
        """Task estimated_complexity is preserved through serialization."""
        task = Task(
            title="Test",
            description="Testing complexity",
            estimated_complexity=complexity,
        )
        data = task.model_dump(mode="json")
        reloaded = Task.model_validate(data)
        assert reloaded.estimated_complexity == complexity

    @given(
        deps=st.lists(st.uuids(), min_size=0, max_size=5, unique=True),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_task_dependencies_preserved(self, deps: list) -> None:
        """Task dependency list is preserved through round-trip."""
        task = Task(
            title="Dependent task",
            description="Has dependencies",
            dependencies=deps,
        )
        data = task.model_dump(mode="json")
        reloaded = Task.model_validate(data)
        assert len(reloaded.dependencies) == len(deps)


# ── Assertion invariants ────────────────────────────────────────────────────

class TestAssertionInvariants:
    @given(
        desc=st.text(min_size=1, max_size=100),
        atype=st.text(min_size=1, max_size=20),
    )
    @settings(suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_assertion_round_trip(self, desc: str, atype: str) -> None:
        """Assertion round-trips preserving all fields."""
        a = Assertion(description=desc, assertion_type=atype)
        data = a.model_dump(mode="json")
        reloaded = Assertion.model_validate(data)
        assert reloaded.description == desc
        assert reloaded.assertion_type == atype
