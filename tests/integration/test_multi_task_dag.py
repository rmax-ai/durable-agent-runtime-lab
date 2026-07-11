"""Integration test: multi-task DAG execution with DurableRuntime."""

import tempfile
import uuid
from pathlib import Path

from durable_agent_runtime.domain import GoalSpecification, Plan, Task
from durable_agent_runtime.experiments.durable import DurableRuntime


class TestMultiTaskDAGIntegration:
    """End-to-end multi-task DAG execution through DurableRuntime."""

    def test_three_task_chain(self) -> None:
        """A→B→C chain executes sequentially through the DAG loop."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Execute chain A→B→C",
                normalized_goal="Run three sequential tasks",
                repository_path=str(workspace),
            )

            goal_id = uuid.uuid4()
            a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            plan = Plan(
                goal_id=goal_id,
                tasks=[
                    Task(task_id=a, title="Task A", description="First in chain", dependencies=[]),
                    Task(task_id=b, title="Task B", description="Depends on A", dependencies=[a]),
                    Task(task_id=c, title="Task C", description="Depends on B", dependencies=[b]),
                ],
            )

            result = runtime.run_goal(goal, plan=plan)

            assert result["success"] is True, f"Expected success, got: {result.get('error')}"
            assert result["task_summary"]["total"] == 3
            assert result["task_summary"]["committed"] == 3
            assert result["task_summary"]["failed"] == 0
            assert result["task_summary"]["blocked"] == 0

    def test_diamond_topology(self) -> None:
        """A→B,C→D: A first, B+C parallel, D last."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Execute diamond A→B,C→D",
                normalized_goal="Run diamond DAG",
                repository_path=str(workspace),
            )

            goal_id = uuid.uuid4()
            a, b, c, d = uuid.uuid4(), uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            plan = Plan(
                goal_id=goal_id,
                tasks=[
                    Task(task_id=a, title="Root", description="Root task", dependencies=[]),
                    Task(task_id=b, title="Branch 1", description="Left branch", dependencies=[a]),
                    Task(task_id=c, title="Branch 2", description="Right branch", dependencies=[a]),
                    Task(task_id=d, title="Merge", description="Merge branch", dependencies=[b, c]),
                ],
            )

            result = runtime.run_goal(goal, plan=plan)

            assert result["success"] is True, f"Expected success, got: {result.get('error')}"
            assert result["task_summary"]["total"] == 4
            assert result["task_summary"]["committed"] == 4
            assert result["task_summary"]["failed"] == 0
            assert result["task_summary"]["blocked"] == 0

    def test_independent_tasks_execute(self) -> None:
        """All independent tasks execute successfully."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Run independent tasks",
                normalized_goal="Run parallel tasks",
                repository_path=str(workspace),
            )

            goal_id = uuid.uuid4()
            a, b, c = uuid.uuid4(), uuid.uuid4(), uuid.uuid4()
            plan = Plan(
                goal_id=goal_id,
                tasks=[
                    Task(task_id=a, title="Task 1", description="Independent", dependencies=[]),
                    Task(task_id=b, title="Task 2", description="Independent", dependencies=[]),
                    Task(task_id=c, title="Task 3", description="Independent", dependencies=[]),
                ],
            )

            result = runtime.run_goal(goal, plan=plan)

            assert result["success"] is True, f"Expected success, got: {result.get('error')}"
            assert result["task_summary"]["total"] == 3
            assert result["task_summary"]["committed"] == 3

    def test_single_task_backward_compat(self) -> None:
        """Without a plan, run_goal still works as before (single task)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Echo backward compat",
                normalized_goal="Run single task",
                repository_path=str(workspace),
            )

            goal.goal_id = uuid.uuid4()
            result = runtime.run_goal(goal)

            assert result["success"] is True
            assert result["task_summary"]["total"] == 1
            assert result["task_summary"]["committed"] == 1
