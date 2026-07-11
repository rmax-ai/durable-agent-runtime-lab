"""Tests for JSON schema generation from Pydantic models."""

import json
import tempfile
from pathlib import Path

import pytest

from durable_agent_runtime.domain import (
    ActionProposal,
    Checkpoint,
    Event,
    ExecutionResult,
    GoalSpecification,
    Plan,
    Task,
    VerificationResult,
)
from durable_agent_runtime.domain.schema_gen import (
    MODEL_SCHEMA_MAP,
    generate_all_schemas,
    generate_schema,
    validate_against_schema,
)


class TestSchemaGeneration:
    """Schema generation from each canonical model."""

    @pytest.mark.parametrize(
        "name,model_class",
        [
            ("goal", GoalSpecification),
            ("plan", Plan),
            ("task", Task),
            ("action-proposal", ActionProposal),
            ("execution-result", ExecutionResult),
            ("verification-result", VerificationResult),
            ("event", Event),
            ("checkpoint", Checkpoint),
        ],
    )
    def test_generates_valid_json_schema(self, name: str, model_class: type) -> None:
        schema = generate_schema(model_class)
        assert isinstance(schema, dict)
        assert "properties" in schema
        # Verify it's valid JSON-serializable
        json.dumps(schema)

    def test_all_schemas_written_to_disk(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            results = generate_all_schemas(output_dir=Path(tmpdir))
            assert len(results) == len(MODEL_SCHEMA_MAP)

            for name in MODEL_SCHEMA_MAP:
                path = results[name]
                assert path.exists()
                content = path.read_text()
                schema = json.loads(content)
                assert "properties" in schema


class TestSchemaValidation:
    """validate_against_schema function."""

    def test_valid_instance_passes(self) -> None:
        goal = GoalSpecification(
            raw_goal="test",
            normalized_goal="test",
            repository_path="/tmp/x",
        )
        assert validate_against_schema("goal", goal.model_dump()) is True

    def test_invalid_instance_fails(self) -> None:
        assert validate_against_schema("goal", {"raw_goal": "incomplete"}) is False

    def test_unknown_schema_raises(self) -> None:
        with pytest.raises(ValueError, match="Unknown schema"):
            validate_against_schema("nonexistent", {})


class TestSchemaRoundTrip:
    """Verify that schemas generated from models can validate their own output."""

    def test_goal_self_validation(self) -> None:
        goal = GoalSpecification(
            raw_goal="Fix bug",
            normalized_goal="Fix the bug",
            repository_path="/tmp/test",
        )
        assert validate_against_schema("goal", goal.model_dump()) is True

    def test_event_self_validation(self) -> None:
        import uuid as _uuid

        from durable_agent_runtime.domain.enums import EventType

        event = Event(
            sequence=1,
            workflow_id=_uuid.uuid4(),
            event_type=EventType.WORKFLOW_CREATED,
            actor_id="test",
        )
        assert validate_against_schema("event", event.model_dump()) is True

    def test_action_proposal_self_validation(self) -> None:
        import uuid as _uuid

        proposal = ActionProposal(
            workflow_id=_uuid.uuid4(),
            task_id=_uuid.uuid4(),
            actor_id="test-model",
            tool_name="read_file",
            arguments={"path": "test.py"},
            intention="Read a file",
            idempotency_key="key-001",
        )
        assert validate_against_schema("action-proposal", proposal.model_dump()) is True
