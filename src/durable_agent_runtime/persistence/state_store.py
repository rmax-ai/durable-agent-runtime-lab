"""SQLite-based state projections from event ledger.

Reconstructs workflow and task state from the canonical event log.
Provides idempotency tracking for mutating actions.
"""

from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from sqlmodel import Field, Session, SQLModel, select

from durable_agent_runtime.domain.enums import TaskStatus, WorkflowStatus
from durable_agent_runtime.persistence.database import get_engine, init_db

# ── SQLModel tables ─────────────────────────────────────────────────────────


class WorkflowStateRow(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "workflow_state"

    workflow_id: str = Field(primary_key=True)
    status: str = Field(default=WorkflowStatus.CREATED.value)
    active_plan_id: str | None = Field(default=None)
    current_phase: str = Field(default="")
    last_event_sequence: int = Field(default=-1)
    tokens_used: int = Field(default=0)
    model_calls: int = Field(default=0)
    tool_calls: int = Field(default=0)
    estimated_cost: float = Field(default=0.0)
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class TaskStateRow(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "task_state"

    task_id: str = Field(primary_key=True)
    workflow_id: str = Field(index=True)
    status: str = Field(default=TaskStatus.PENDING.value)
    attempt_count: int = Field(default=0)
    last_error: str | None = Field(default=None)
    committed_at: str | None = Field(default=None)
    updated_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


class IdempotencyRow(SQLModel, table=True):  # type: ignore[call-arg]
    __tablename__ = "idempotency"

    idempotency_key: str = Field(primary_key=True)
    workflow_id: str = Field(index=True)
    proposal_hash: str = Field(default="")
    execution_status: str = Field(default="")
    execution_result_json: str = Field(default="{}")
    created_at: str = Field(default_factory=lambda: datetime.now(UTC).isoformat())


# ── State Store ─────────────────────────────────────────────────────────────


class StateStore:
    """Read/write interface for SQLite state projections.

    Not the source of truth — the event ledger is. These tables are
    projections for fast query access.
    """

    def __init__(self, data_dir: Path) -> None:
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.engine = get_engine(self.data_dir)
        init_db(self.engine)

    def _session(self) -> Session:
        return Session(self.engine)

    # ── Workflow state ──────────────────────────────────────────────────

    def upsert_workflow(self, workflow_id: UUID, status: WorkflowStatus, **kwargs: object) -> None:
        with self._session() as session:
            existing = session.get(WorkflowStateRow, str(workflow_id))
            if existing:
                existing.status = status.value
                for k, v in kwargs.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.now(UTC).isoformat()
            else:
                row = WorkflowStateRow(
                    workflow_id=str(workflow_id),
                    status=status.value,
                    **{k: v for k, v in kwargs.items() if hasattr(WorkflowStateRow, k)},
                )
                session.add(row)
            session.commit()

    def get_workflow(self, workflow_id: UUID) -> WorkflowStateRow | None:
        with self._session() as session:
            return session.get(WorkflowStateRow, str(workflow_id))

    # ── Task state ──────────────────────────────────────────────────────

    def upsert_task(
        self, task_id: UUID, workflow_id: UUID, status: TaskStatus, **kwargs: object
    ) -> None:
        with self._session() as session:
            existing = session.get(TaskStateRow, str(task_id))
            if existing:
                existing.status = status.value
                for k, v in kwargs.items():
                    setattr(existing, k, v)
                existing.updated_at = datetime.now(UTC).isoformat()
            else:
                row = TaskStateRow(
                    task_id=str(task_id),
                    workflow_id=str(workflow_id),
                    status=status.value,
                    **{k: v for k, v in kwargs.items() if hasattr(TaskStateRow, k)},
                )
                session.add(row)
            session.commit()

    def get_task(self, task_id: UUID) -> TaskStateRow | None:
        with self._session() as session:
            return session.get(TaskStateRow, str(task_id))

    def get_tasks_by_workflow(self, workflow_id: UUID) -> list[TaskStateRow]:
        with self._session() as session:
            stmt = select(TaskStateRow).where(TaskStateRow.workflow_id == str(workflow_id))
            return list(session.exec(stmt).all())

    # ── Idempotency ─────────────────────────────────────────────────────

    def record_idempotency(
        self,
        idempotency_key: str,
        workflow_id: UUID,
        proposal_hash: str = "",
        execution_status: str = "",
        execution_result_json: str = "{}",
    ) -> None:
        with self._session() as session:
            existing = session.get(IdempotencyRow, idempotency_key)
            if existing:
                existing.execution_status = execution_status
                existing.execution_result_json = execution_result_json
            else:
                row = IdempotencyRow(
                    idempotency_key=idempotency_key,
                    workflow_id=str(workflow_id),
                    proposal_hash=proposal_hash,
                    execution_status=execution_status,
                    execution_result_json=execution_result_json,
                )
                session.add(row)
            session.commit()

    def get_idempotency(self, idempotency_key: str) -> IdempotencyRow | None:
        with self._session() as session:
            return session.get(IdempotencyRow, idempotency_key)

    def is_duplicate(self, idempotency_key: str) -> bool:
        """Check if an idempotency key has already been committed."""
        row = self.get_idempotency(idempotency_key)
        return row is not None and row.execution_status == "committed"
