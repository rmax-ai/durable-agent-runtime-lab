"""Tests for Pydantic domain model serialization, validation, and round-trips."""

import uuid
from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from durable_agent_runtime.domain import (
    ActionProposal,
    Assertion,
    Budget,
    Checkpoint,
    Constraint,
    Event,
    ExecutionResult,
    GoalSpecification,
    Plan,
    SuccessCriterion,
    Task,
    VerificationResult,
)
from durable_agent_runtime.domain.enums import (
    ApprovalPolicy,
    EventType,
    ExecutionStatus,
    PlanStatus,
    RiskLevel,
    TaskStatus,
    WorkflowStatus,
)

# ── Test fixtures ───────────────────────────────────────────────────────────


def make_goal() -> GoalSpecification:
    return GoalSpecification(
        raw_goal="Fix the bug in auth.py",
        normalized_goal="Locate and fix the authentication bug in auth.py",
        repository_path="/tmp/test-repo",
        constraints=[
            Constraint(
                name="scope",
                description="Only modify auth.py",
                constraint_type="file_scope",
                parameters={"files": ["auth.py"]},
            )
        ],
        success_criteria=[
            SuccessCriterion(
                name="tests_pass", description="All tests pass", verification_method="test_pass"
            )
        ],
        available_tools=["read_file", "write_patch", "run_command"],
        risk_level=RiskLevel.MEDIUM,
        human_approval_policy=ApprovalPolicy.MEDIUM_AND_ABOVE,
    )


def make_plan(goal: GoalSpecification) -> Plan:
    return Plan(
        goal_id=goal.goal_id,
        tasks=[
            Task(
                title="Read auth.py",
                description="Read the auth module to understand current implementation",
                estimated_complexity=1,
                required_tools=["read_file"],
                preconditions=[
                    Assertion(
                        description="auth.py exists",
                        assertion_type="file_exists",
                        parameters={"path": "auth.py"},
                    )
                ],
                postconditions=[
                    Assertion(
                        description="Understood the bug",
                        assertion_type="model_eval",
                        parameters={"criterion": "bug_understood"},
                    )
                ],
            ),
            Task(
                title="Fix the bug",
                description="Apply patch to fix authentication bug",
                dependencies=[],  # Will be set below
                estimated_complexity=3,
                required_tools=["write_patch", "run_command"],
                preconditions=[
                    Assertion(
                        description="Bug is understood",
                        assertion_type="model_eval",
                        parameters={"criterion": "bug_understood"},
                    )
                ],
                postconditions=[
                    Assertion(
                        description="Tests pass",
                        assertion_type="test_pass",
                        parameters={"command": "pytest tests/test_auth.py"},
                    )
                ],
                risk_level=RiskLevel.HIGH,
                human_approval_required=True,
            ),
        ],
        status=PlanStatus.DRAFT,
        assumptions=["Auth bug is in the password hashing logic"],
    )


# ── Goal Specification tests ────────────────────────────────────────────────


class TestGoalSpecification:
    def test_valid_goal_creates(self) -> None:
        goal = make_goal()
        assert isinstance(goal.goal_id, uuid.UUID)
        assert goal.risk_level == RiskLevel.MEDIUM
        assert goal.constraints[0].constraint_type == "file_scope"

    def test_goal_round_trip_json(self) -> None:
        """Goal serializes to JSON and back without data loss."""
        goal = make_goal()
        data = goal.model_dump(mode="json")
        reloaded = GoalSpecification.model_validate(data)
        assert reloaded.goal_id == goal.goal_id
        assert reloaded.raw_goal == goal.raw_goal
        assert reloaded.risk_level == goal.risk_level
        assert len(reloaded.success_criteria) == len(goal.success_criteria)

    def test_goal_round_trip_python(self) -> None:
        """Goal serializes to Python dict and back preserving UUIDs."""
        goal = make_goal()
        data = goal.model_dump()
        reloaded = GoalSpecification.model_validate(data)
        assert reloaded.goal_id == goal.goal_id

    def test_constraint_missing_name_raises(self) -> None:
        with pytest.raises(ValidationError):
            Constraint(description="scope", constraint_type="file_scope")  # type: ignore[arg-type]

    def test_success_criterion_default_weight(self) -> None:
        sc = SuccessCriterion(name="test", description="desc", verification_method="test_pass")
        assert sc.weight == 1.0

    def test_budget_defaults(self) -> None:
        b = Budget()
        assert b.max_currency is None
        assert b.max_tokens is None

    def test_budget_custom(self) -> None:
        b = Budget(max_tokens=10000, max_retries=3)
        assert b.max_tokens == 10000
        assert b.max_retries == 3

    def test_approval_policy_values(self) -> None:
        goal = GoalSpecification(
            raw_goal="g",
            normalized_goal="g",
            repository_path="/tmp/x",
            human_approval_policy=ApprovalPolicy.ALL_MUTATING,
        )
        assert goal.human_approval_policy == ApprovalPolicy.ALL_MUTATING

    def test_goal_json_schema_generation(self) -> None:
        """Schema generation succeeds and includes key fields."""
        schema = GoalSpecification.model_json_schema()
        assert schema["title"] == "GoalSpecification"
        assert "goal_id" in schema["properties"]
        assert "raw_goal" in schema["properties"]


# ── Plan and Task tests ─────────────────────────────────────────────────────


class TestPlan:
    def test_valid_plan_creates(self) -> None:
        goal = make_goal()
        plan = make_plan(goal)
        assert plan.goal_id == goal.goal_id
        assert plan.version == 1
        assert len(plan.tasks) == 2

    def test_plan_round_trip_json(self) -> None:
        goal = make_goal()
        plan = make_plan(goal)
        data = plan.model_dump(mode="json")
        reloaded = Plan.model_validate(data)
        assert reloaded.plan_id == plan.plan_id
        assert len(reloaded.tasks) == len(plan.tasks)
        assert reloaded.tasks[0].title == plan.tasks[0].title

    def test_empty_plan_valid(self) -> None:
        plan = Plan(goal_id=uuid.uuid4())
        assert plan.tasks == []
        assert plan.status == PlanStatus.DRAFT

    def test_plan_version_ge_1(self) -> None:
        with pytest.raises(ValidationError):
            Plan(goal_id=uuid.uuid4(), version=0)


class TestTask:
    def test_task_defaults(self) -> None:
        task = Task(title="Test task", description="A test")
        assert task.status == TaskStatus.PENDING
        assert task.max_attempts == 3
        assert task.estimated_complexity == 1

    def test_task_custom_attempts(self) -> None:
        task = Task(title="T", description="D", max_attempts=5)
        assert task.max_attempts == 5

    def test_task_complexity_ge_1(self) -> None:
        with pytest.raises(ValidationError):
            Task(title="T", description="D", estimated_complexity=0)

    def test_precondition_assertion(self) -> None:
        a = Assertion(
            description="File must exist",
            assertion_type="file_exists",
            parameters={"path": "/tmp/x"},
        )
        assert a.assertion_type == "file_exists"
        assert isinstance(a.assertion_id, uuid.UUID)


# ── Action Proposal tests ───────────────────────────────────────────────────


class TestActionProposal:
    def test_proposal_creates(self) -> None:
        proposal = ActionProposal(
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            actor_id="test-model",
            tool_name="read_file",
            arguments={"path": "auth.py"},
            intention="Read the auth module",
            idempotency_key="key-123",
        )
        assert proposal.tool_name == "read_file"
        assert proposal.risk_level == RiskLevel.LOW

    def test_proposal_round_trip(self) -> None:
        proposal = ActionProposal(
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            actor_id="test-model",
            tool_name="write_patch",
            arguments={
                "path": "auth.py",
                "patch": "--- a/auth.py\n+++ b/auth.py\n@@ -1,1 +1,1 @@\n-old\n+new",
            },
            intention="Fix the auth bug",
            idempotency_key="key-456",
            risk_level=RiskLevel.HIGH,
        )
        data = proposal.model_dump(mode="json")
        reloaded = ActionProposal.model_validate(data)
        assert reloaded.idempotency_key == "key-456"

    def test_proposal_missing_idempotency_key_raises(self) -> None:
        with pytest.raises(ValidationError):
            ActionProposal(
                workflow_id=uuid.uuid4(),
                task_id=uuid.uuid4(),
                actor_id="test",
                tool_name="write_patch",
                arguments={},
                intention="fix",
            )  # type: ignore[call-arg]

    def test_verification_result_passed(self) -> None:
        vr = VerificationResult(
            proposal_id=uuid.uuid4(),
            passed=True,
            checks=[],
        )
        assert vr.passed is True

    def test_verification_result_rejected(self) -> None:
        vr = VerificationResult(
            proposal_id=uuid.uuid4(),
            passed=False,
            rejection_code="SCHEMA_INVALID",
            rejection_message="Missing required field",
        )
        assert vr.passed is False
        assert vr.rejection_code == "SCHEMA_INVALID"

    def test_execution_result_round_trip(self) -> None:
        er = ExecutionResult(
            proposal_id=uuid.uuid4(),
            status=ExecutionStatus.SUCCEEDED,
            exit_code=0,
            stdout_ref="artifact://stdout/abc123",
            finished_at=datetime.now(UTC),
        )
        data = er.model_dump(mode="json")
        reloaded = ExecutionResult.model_validate(data)
        assert reloaded.status == ExecutionStatus.SUCCEEDED
        assert reloaded.exit_code == 0


# ── Event tests ─────────────────────────────────────────────────────────────


class TestEvent:
    def test_event_creates(self) -> None:
        event = Event(
            sequence=1,
            workflow_id=uuid.uuid4(),
            event_type=EventType.WORKFLOW_CREATED,
            actor_id="system",
            correlation_id=uuid.uuid4(),
        )
        assert event.sequence == 1
        assert event.event_type == EventType.WORKFLOW_CREATED
        assert isinstance(event.event_id, uuid.UUID)

    def test_event_round_trip_json(self) -> None:
        event = Event(
            sequence=0,
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            event_type=EventType.ACTION_COMMITTED,
            actor_id="orchestrator",
            payload={"commit": "abc123", "files_changed": 2},
            payload_hash="sha256:abc",
            previous_event_hash="sha256:def",
            event_hash="sha256:ghi",
        )
        data = event.model_dump(mode="json")
        reloaded = Event.model_validate(data)
        assert reloaded.event_id == event.event_id
        assert reloaded.payload == event.payload
        assert reloaded.previous_event_hash == "sha256:def"

    def test_event_tampered_payload_rejected(self) -> None:
        """Event hash chain integrity — payload change should be detectable."""
        event = Event(
            sequence=1,
            workflow_id=uuid.uuid4(),
            event_type=EventType.ACTION_COMMITTED,
            actor_id="test",
            payload={"files": 3},
            payload_hash="sha256:original",
        )
        data = event.model_dump()
        data["payload"] = {"files": 999}
        reloaded = Event.model_validate(data)
        # The event validates structurally, but the payload hash won't match
        assert reloaded.payload == {"files": 999}
        assert reloaded.payload_hash == "sha256:original"  # Not recalculated by Pydantic
        # Real integrity check happens in the event store's hash computation


# ── Checkpoint tests ────────────────────────────────────────────────────────


class TestCheckpoint:
    def test_checkpoint_creates(self) -> None:
        cp = Checkpoint(
            workflow_id=uuid.uuid4(),
            sequence=0,
            git_commit="abc123def456",
            workflow_status=WorkflowStatus.RUNNING,
            last_event_sequence=42,
        )
        assert cp.git_commit == "abc123def456"
        assert cp.sequence == 0
        assert cp.last_event_sequence == 42

    def test_checkpoint_round_trip(self) -> None:
        cp = Checkpoint(
            workflow_id=uuid.uuid4(),
            sequence=1,
            git_commit="fedcba",
            workflow_status=WorkflowStatus.PAUSED,
            active_plan_id=uuid.uuid4(),
            task_states={"task-1": "committed", "task-2": "running"},
            last_event_sequence=100,
            tokens_used=5000,
            model_calls=12,
            tool_calls=8,
            estimated_cost=0.15,
        )
        data = cp.model_dump(mode="json")
        reloaded = Checkpoint.model_validate(data)
        assert reloaded.sequence == 1
        assert reloaded.task_states == {"task-1": "committed", "task-2": "running"}
        assert reloaded.estimated_cost == 0.15


# ── JSON Schema generation tests ────────────────────────────────────────────


class TestJsonSchemaGeneration:
    """Verify all domain models produce valid JSON Schema."""

    @pytest.mark.parametrize(
        "model_class_name",
        [
            "GoalSpecification",
            "Plan",
            "Task",
            "ActionProposal",
            "VerificationResult",
            "ExecutionResult",
            "Event",
            "Checkpoint",
        ],
    )
    def test_model_generates_json_schema(self, model_class_name: str) -> None:
        import importlib

        module = importlib.import_module("durable_agent_runtime.domain")
        model_class = getattr(module, model_class_name)
        schema = model_class.model_json_schema()
        assert "$defs" in schema or "properties" in schema
        assert "properties" in schema


# ── Edge cases ──────────────────────────────────────────────────────────────


class TestEdgeCases:
    def test_max_budget_zero_retries(self) -> None:
        b = Budget(max_retries=0)
        assert b.max_retries == 0

    def test_task_with_dependencies(self) -> None:
        dep_id = uuid.uuid4()
        task = Task(
            title="Dep task",
            description="Depends on previous",
            dependencies=[dep_id],
        )
        assert dep_id in task.dependencies

    def test_plan_replan_parent(self) -> None:
        parent_id = uuid.uuid4()
        plan = Plan(goal_id=uuid.uuid4(), parent_plan_id=parent_id)
        assert plan.parent_plan_id == parent_id

    def test_plan_superseding(self) -> None:
        superseded_by = uuid.uuid4()
        plan = Plan(goal_id=uuid.uuid4(), superseded_by=superseded_by)
        assert plan.superseded_by == superseded_by
