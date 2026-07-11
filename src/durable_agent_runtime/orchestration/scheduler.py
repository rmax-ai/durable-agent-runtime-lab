"""Multi-task DAG scheduler — dependency-aware task dispatch (Section 9.3).

Selects READY tasks from a Plan DAG based on dependency satisfaction.
PENDING tasks are promoted to READY when all dependencies COMMITTED.
Circular dependencies are detected and rejected upfront.
"""

from uuid import UUID

from durable_agent_runtime.domain.enums import TaskStatus
from durable_agent_runtime.domain.plan import Plan, Task
from durable_agent_runtime.orchestration.engine import OrchestratorEngine
from durable_agent_runtime.persistence.state_store import StateStore


class TaskScheduler:
    """Selects READY tasks from a Plan DAG based on dependency satisfaction.

    Operates purely on state projections for reads and uses the orchestrator
    engine for valid state transitions that also emit events.
    """

    def __init__(self, state_store: StateStore, engine: OrchestratorEngine | None = None) -> None:
        self.state = state_store
        self._engine = engine

    # ── Public API ──────────────────────────────────────────────────────────

    def get_ready(self, workflow_id: UUID, plan: Plan) -> list[UUID]:
        """Return task IDs whose status is READY in the state store.

        Tasks are promoted to READY by a prior call to *promote_pending*;
        this method simply queries current state.
        """
        all_tasks = self.state.get_tasks_by_workflow(workflow_id)
        return [
            UUID(row.task_id) for row in all_tasks if TaskStatus(row.status) == TaskStatus.READY
        ]

    def promote_pending(self, workflow_id: UUID, plan: Plan) -> int:
        """Transition PENDING → READY for tasks whose dependencies are all COMMITTED.

        Also transitions PENDING → READY → BLOCKED for tasks whose deps are FAILED
        (via the valid READY → BLOCKED transition in the state machine).

        Returns the count of tasks promoted to READY.
        """
        promoted = 0
        for task in plan.tasks:
            row = self.state.get_task(task.task_id)
            if row is None:
                continue
            current = TaskStatus(row.status)
            if current != TaskStatus.PENDING:
                continue

            if self._are_deps_satisfied(task, self.state):
                self._transition_task(task.task_id, workflow_id, TaskStatus.READY)
                promoted += 1
            elif self._has_failed_dep(task, self.state):
                # PENDING→READY (valid) → BLOCKED (valid from READY)
                self._transition_task(task.task_id, workflow_id, TaskStatus.READY)
                self._transition_task(task.task_id, workflow_id, TaskStatus.BLOCKED)
        return promoted

    # ── Dependency checks ───────────────────────────────────────────────────

    def _are_deps_satisfied(self, task: Task, state: StateStore) -> bool:
        """All dependencies are COMMITTED."""
        for dep_id in task.dependencies:
            row = state.get_task(dep_id)
            if row is None:
                return False
            status = TaskStatus(row.status)
            if status != TaskStatus.COMMITTED:
                # If it's FAILED it will be handled by _has_failed_dep
                return False
        return True

    def _has_failed_dep(self, task: Task, state: StateStore) -> bool:
        """At least one dependency is FAILED (terminal)."""
        for dep_id in task.dependencies:
            row = state.get_task(dep_id)
            if row is None:
                continue
            if TaskStatus(row.status) == TaskStatus.FAILED:
                return True
        return False

    def _transition_task(self, task_id: UUID, workflow_id: UUID, target: TaskStatus) -> None:
        """Transition task state via engine (if available) else raw state store."""
        if self._engine is not None:
            self._engine.transition_task(task_id, workflow_id, target)
        else:
            self.state.upsert_task(task_id, workflow_id, target)

    # ── Circular dependency detection ───────────────────────────────────────

    def detect_circular_deps(self, plan: Plan) -> list[list[UUID]]:
        """DFS-based cycle detection.

        Returns a list of cycles found in the plan's dependency graph.
        Each cycle is a list of task IDs forming a circular chain.
        Returns an empty list if there are no cycles.
        """
        task_ids = {t.task_id for t in plan.tasks}
        dep_map: dict[UUID, list[UUID]] = {}
        for task in plan.tasks:
            dep_map[task.task_id] = [d for d in task.dependencies if d in task_ids]

        white, gray, black = 0, 1, 2
        color: dict[UUID, int] = dict.fromkeys(task_ids, white)
        parent: dict[UUID, UUID | None] = dict.fromkeys(task_ids, None)
        cycles: list[list[UUID]] = []

        def dfs(node: UUID, path: list[UUID]) -> None:
            color[node] = gray
            path.append(node)
            for neighbour in dep_map.get(node, []):
                if colour := color.get(neighbour, white):
                    if colour == gray:
                        # Found a cycle — extract it
                        cycle_start = path.index(neighbour)
                        cycle = path[cycle_start:]
                        cycles.append(cycle)
                    elif colour == black:
                        continue
                else:
                    parent[neighbour] = node
                    dfs(neighbour, path)
            path.pop()
            color[node] = black

        for tid in task_ids:
            if color[tid] == white:
                dfs(tid, [])

        return cycles
