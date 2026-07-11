"""Integration test: human approval flow (Phase 4).

Tests the request-approval → approve/reject cycle on the OrchestratorEngine:

- request_approval: RUNNING → PAUSED, emits HUMAN_APPROVAL_REQUESTED
- approve:          PAUSED → RUNNING, emits HUMAN_APPROVAL_RECEIVED (approved=True)
- reject:           PAUSED → RUNNING, emits HUMAN_APPROVAL_RECEIVED (approved=False)
- approve on non-PAUSED workflow → ValueError
"""

import tempfile
import uuid
from pathlib import Path

import pytest

from durable_agent_runtime.domain.enums import EventType, WorkflowStatus
from durable_agent_runtime.orchestration.engine import OrchestratorEngine


class TestHumanApprovalFlow:
    """Test the human approval request/approve/reject cycle."""

    @pytest.fixture
    def engine(self) -> OrchestratorEngine:
        tmpdir = tempfile.mkdtemp()
        return OrchestratorEngine(Path(tmpdir) / "data")

    @pytest.fixture
    def running_workflow(self, engine: OrchestratorEngine) -> uuid.UUID:
        """Create a workflow and transition it through to RUNNING."""
        wf_id = engine.create_workflow(
            goal_id=uuid.uuid4(),
            repository_path="/tmp/test-repo",
        )
        # CREATED → COMPILED → PLANNED → RUNNING
        engine.transition_workflow(wf_id, WorkflowStatus.COMPILED)
        engine.transition_workflow(wf_id, WorkflowStatus.PLANNED)
        engine.transition_workflow(wf_id, WorkflowStatus.RUNNING)
        return wf_id

    # ── request_approval ─────────────────────────────────────────────────

    def test_request_approval_pauses_workflow(
        self,
        engine: OrchestratorEngine,
        running_workflow: uuid.UUID,
    ) -> None:
        """request_approval transitions RUNNING → PAUSED and emits HUMAN_APPROVAL_REQUESTED."""
        proposal_id = uuid.uuid4()
        reason = "High-risk filesystem operation"

        engine.request_approval(running_workflow, proposal_id, reason)

        status = engine.get_workflow_status(running_workflow)
        assert status == WorkflowStatus.PAUSED

        events = engine.events.read_all(running_workflow)
        approval_events = [e for e in events if e.event_type == EventType.HUMAN_APPROVAL_REQUESTED]
        assert len(approval_events) >= 1

        latest = approval_events[-1]
        assert str(proposal_id) == latest.payload.get("proposal_id")
        assert reason == latest.payload.get("reason")

    # ── approve ──────────────────────────────────────────────────────────

    def test_approve_resumes_workflow(
        self,
        engine: OrchestratorEngine,
        running_workflow: uuid.UUID,
    ) -> None:
        """Calling approve transitions PAUSED → RUNNING and emits HUMAN_APPROVAL_RECEIVED."""
        proposal_id = uuid.uuid4()
        engine.request_approval(running_workflow, proposal_id, "Review needed")

        engine.approve(running_workflow, proposal_id)

        status = engine.get_workflow_status(running_workflow)
        assert status == WorkflowStatus.RUNNING

        events = engine.events.read_all(running_workflow)
        approval_events = [e for e in events if e.event_type == EventType.HUMAN_APPROVAL_RECEIVED]
        assert len(approval_events) >= 1

        latest = approval_events[-1]
        assert str(proposal_id) == latest.payload.get("proposal_id")
        assert latest.payload.get("approved") is True

    # ── reject ───────────────────────────────────────────────────────────

    def test_reject_logs_reason_and_resumes(
        self,
        engine: OrchestratorEngine,
        running_workflow: uuid.UUID,
    ) -> None:
        """Calling reject transitions PAUSED → RUNNING with rejection reason in payload."""
        proposal_id = uuid.uuid4()
        reason = "This operation is too risky"
        engine.request_approval(running_workflow, proposal_id, "Review needed")

        engine.reject(running_workflow, proposal_id, reason)

        status = engine.get_workflow_status(running_workflow)
        assert status == WorkflowStatus.RUNNING

        events = engine.events.read_all(running_workflow)
        approval_events = [e for e in events if e.event_type == EventType.HUMAN_APPROVAL_RECEIVED]
        assert len(approval_events) >= 1

        latest = approval_events[-1]
        assert str(proposal_id) == latest.payload.get("proposal_id")
        assert latest.payload.get("approved") is False
        assert reason == latest.payload.get("reason")

    # ── Error cases ──────────────────────────────────────────────────────

    def test_approve_non_paused_raises_error(
        self,
        engine: OrchestratorEngine,
        running_workflow: uuid.UUID,
    ) -> None:
        """Approving a non-PAUSED workflow must raise ValueError."""
        proposal_id = uuid.uuid4()

        with pytest.raises(ValueError, match="expected paused"):
            engine.approve(running_workflow, proposal_id)

    def test_reject_non_paused_raises_error(
        self,
        engine: OrchestratorEngine,
        running_workflow: uuid.UUID,
    ) -> None:
        """Rejecting a non-PAUSED workflow must raise ValueError."""
        proposal_id = uuid.uuid4()

        with pytest.raises(ValueError, match="expected paused"):
            engine.reject(running_workflow, proposal_id)

    def test_request_approval_non_running_raises_error(
        self,
        engine: OrchestratorEngine,
    ) -> None:
        """Requesting approval on a non-RUNNING workflow must raise ValueError."""
        wf_id = engine.create_workflow(
            goal_id=uuid.uuid4(),
            repository_path="/tmp/test-repo",
        )
        # wf_id is CREATED, not RUNNING

        with pytest.raises(ValueError, match="expected running"):
            engine.request_approval(wf_id, uuid.uuid4(), "test")
