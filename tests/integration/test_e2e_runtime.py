"""Integration test: end-to-end durable runtime execution."""

import tempfile
import uuid
from pathlib import Path

from durable_agent_runtime.domain import GoalSpecification
from durable_agent_runtime.experiments.durable import DurableRuntime


class TestDurableRuntimeE2E:
    def test_simple_goal_executes_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Echo hello world",
                normalized_goal="Run echo hello world",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            assert result["success"] is True
            assert (
                "hello world" in result.get("output", "").lower()
                or "echo" in result.get("output", "").lower()
            )

    def test_workflow_events_are_recorded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Simple task",
                normalized_goal="Run a simple task",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            wf_id = result["workflow_id"]
            events = runtime.engine.events.read_all(uuid.UUID(wf_id))
            assert len(events) > 3  # CREATED, COMPILED, PLANNED, RUNNING, plus task events

            valid, error = runtime.engine.events.verify_chain(uuid.UUID(wf_id))
            assert valid is True
            assert error is None

    def test_workflow_state_tracked(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Track state",
                normalized_goal="Track workflow state",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            wf_state = runtime.engine.state.get_workflow(uuid.UUID(result["workflow_id"]))
            assert wf_state is not None
            assert wf_state.status in ("completed", "failed")


class TestBaselineRuntimeE2E:
    def test_baseline_executes(self) -> None:
        from durable_agent_runtime.experiments.baseline import BaselineRuntime

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = BaselineRuntime(workspace)
            goal = GoalSpecification(
                raw_goal="Test baseline",
                normalized_goal="Run baseline test",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            assert "workflow_id" in result
            assert "model_calls" in result


class TestExperimentRunner:
    def test_comparison_runs_both_runtimes(self) -> None:
        from durable_agent_runtime.experiments.runner import ExperimentRunner

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runner = ExperimentRunner(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Compare runtimes",
                normalized_goal="Run comparison",
                repository_path=str(workspace),
            )

            results = runner.run_comparison(goal)
            assert results["baseline"]["success"] is True
            assert results["durable"]["success"] is True
            assert "metrics" in results
            assert "speedup" in results["metrics"]

    def test_report_saved_to_disk(self) -> None:
        from durable_agent_runtime.experiments.runner import ExperimentRunner

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runner = ExperimentRunner(data_dir, workspace)
            goal = GoalSpecification(
                raw_goal="Save report",
                normalized_goal="Save experiment report",
                repository_path=str(workspace),
            )

            results = runner.run_comparison(goal)
            report_path = runner.save_report(results)
            assert report_path.exists()
            assert report_path.stat().st_size > 0
