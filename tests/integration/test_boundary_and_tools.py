"""Tests for the tool boundary and proposal verification."""

import tempfile
import uuid
from pathlib import Path

import pytest

from durable_agent_runtime.boundary.service import BoundaryService
from durable_agent_runtime.domain import ActionProposal
from durable_agent_runtime.execution.process_executor import ProcessExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext, ToolRegistry
from durable_agent_runtime.persistence.state_store import StateStore


class TestBoundaryService:
    @pytest.fixture
    def service(self) -> BoundaryService:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = StateStore(Path(tmpdir))
            yield BoundaryService(store)

    def test_valid_proposal_passes(self, service: BoundaryService) -> None:
        proposal = ActionProposal(
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            actor_id="test",
            tool_name="read_file",
            arguments={"path": "auth.py"},
            intention="Read file",
            idempotency_key="valid-key-1",
        )
        result = service.verify(proposal)
        assert result.passed is True

    def test_duplicate_idempotency_key_rejected(self, service: BoundaryService) -> None:
        proposal = ActionProposal(
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            actor_id="test",
            tool_name="write_patch",
            arguments={"path": "x.py"},
            intention="Write",
            idempotency_key="dup-key",
        )
        # Record as already committed
        service.state.record_idempotency("dup-key", uuid.uuid4(), execution_status="committed")

        result = service.verify(proposal)
        assert result.passed is False
        assert "Duplicate" in (result.rejection_message or "")

    def test_path_traversal_rejected(self, service: BoundaryService) -> None:
        proposal = ActionProposal(
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            actor_id="test",
            tool_name="read_file",
            arguments={"path": "../../../etc/passwd"},
            intention="Read passwd",
            idempotency_key="path-traverse-1",
        )
        result = service.verify(proposal)
        assert result.passed is False
        assert "Unsafe path" in (result.rejection_message or "")

    def test_budget_exhausted_rejected(self, service: BoundaryService) -> None:
        proposal = ActionProposal(
            workflow_id=uuid.uuid4(),
            task_id=uuid.uuid4(),
            actor_id="test",
            tool_name="run_command",
            arguments={"command": "echo hi"},
            intention="Run command",
            idempotency_key="budget-key",
        )
        result = service.verify(proposal, budget_remaining=0)
        assert result.passed is False
        assert "Budget" in (result.rejection_message or "")


class TestProcessExecutor:
    def test_successful_command(self) -> None:
        executor = ProcessExecutor()
        context = ToolContext(workspace_root="/tmp")
        result = executor.execute(["echo", "hello"], context)
        assert result.success is True
        assert "hello" in result.output
        assert result.exit_code == 0

    def test_failing_command(self) -> None:
        executor = ProcessExecutor()
        context = ToolContext(workspace_root="/tmp")
        result = executor.execute(["ls", "/nonexistent/path/xyz"], context)
        assert result.success is False
        assert result.exit_code != 0

    def test_timeout(self) -> None:
        executor = ProcessExecutor()
        context = ToolContext(workspace_root="/tmp", timeout_seconds=1)
        result = executor.execute(["sleep", "5"], context)
        assert result.success is False
        assert "timed out" in result.error.lower()


class TestToolRegistry:
    def test_register_and_list(self) -> None:
        registry = ToolRegistry()
        assert registry.list_names() == []

    def test_get_nonexistent(self) -> None:
        registry = ToolRegistry()
        assert registry.get("nonexistent") is None
