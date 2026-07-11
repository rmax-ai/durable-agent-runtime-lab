"""Integration test: end-to-end durable runtime execution."""

import tempfile
import uuid
from pathlib import Path

from durable_agent_runtime.domain import GoalSpecification
from durable_agent_runtime.experiments.durable import DurableRuntime
from durable_agent_runtime.models.base import ModelTransientError


class TestDurableRuntimeE2E:
    def test_simple_goal_executes_and_completes(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            from durable_agent_runtime.models.base import MockProvider

            provider = MockProvider()
            # Register a fixture so the model "proposes" echo hello world
            provider.set_fixture(
                "Run echo",
                {
                    "tool_name": "run_command",
                    "command": "echo hello world",
                    "intention": "Echo hello world as requested",
                    "risk_level": "low",
                    "expected_effects": ["prints 'hello world'"],
                    "is_terminal": True,
                },
            )

            runtime = DurableRuntime(data_dir, workspace, provider=provider)
            goal = GoalSpecification(
                raw_goal="Echo hello world",
                normalized_goal="Run echo hello world",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            assert result["success"] is True
            assert "hello world" in result.get("output", "").lower()
            assert provider.call_count == 1  # model was actually called

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

    def test_model_proposal_failure_marks_task_failed_and_preserves_error(self) -> None:
        class FailingProvider:
            async def generate_structured(self, request, response_model):
                raise ModelTransientError("upstream timeout")

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace, provider=FailingProvider())
            goal = GoalSpecification(
                raw_goal="Fail proposal",
                normalized_goal="Force proposal failure",
                repository_path=str(workspace),
            )

            result = runtime.run_goal(goal)

            assert result["success"] is False
            assert (
                result["task_results"][result["task_id"]]["error"]
                == "Model proposal failed: upstream timeout"
            )

            task_row = runtime.engine.state.get_task(uuid.UUID(result["task_id"]))
            assert task_row is not None
            assert task_row.status == "failed"


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

    def test_baseline_preserves_last_model_error(self) -> None:
        from durable_agent_runtime.experiments.baseline import BaselineRuntime

        class FailingProvider:
            async def generate_structured(self, request, response_model):
                raise ModelTransientError("upstream rejected request")

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = BaselineRuntime(workspace, provider=FailingProvider())
            goal = GoalSpecification(
                raw_goal="Test baseline failure",
                normalized_goal="Run baseline failure test",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            assert result["success"] is False
            assert result["iterations"] == 0
            assert result["tool_calls"] == 0
            assert result["error"] == "Model proposal failed: upstream rejected request"

    def test_baseline_requires_terminal_success(self) -> None:
        from durable_agent_runtime.experiments.baseline import BaselineRuntime

        class NonTerminalProvider:
            def __init__(self) -> None:
                self.call_count = 0

            async def generate_structured(self, request, response_model):
                self.call_count += 1
                return type(
                    "Resp",
                    (),
                    {
                        "content": {
                            "tool_name": "run_command",
                            "command": "echo still-working",
                            "intention": "Keep investigating",
                            "risk_level": "low",
                            "expected_effects": [],
                            "is_terminal": False,
                        }
                    },
                )()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            provider = NonTerminalProvider()
            runtime = BaselineRuntime(workspace, provider=provider)
            goal = GoalSpecification(
                raw_goal="Need more than one step",
                normalized_goal="Do not stop after first successful command",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            assert result["success"] is False
            assert result["tool_calls"] == 5

    def test_baseline_uses_success_criteria_when_repo_is_correct(self) -> None:
        from durable_agent_runtime.domain import SuccessCriterion
        from durable_agent_runtime.experiments.baseline import BaselineRuntime

        class NonTerminalProvider:
            async def generate_structured(self, request, response_model):
                return type(
                    "Resp",
                    (),
                    {
                        "content": {
                            "tool_name": "run_command",
                            "command": "printf 'done\\n' > result.txt",
                            "intention": "Write expected output",
                            "risk_level": "low",
                            "expected_effects": [],
                            "is_terminal": False,
                        }
                    },
                )()

        with tempfile.TemporaryDirectory() as tmpdir:
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = BaselineRuntime(workspace, provider=NonTerminalProvider())
            goal = GoalSpecification(
                raw_goal="Write result file",
                normalized_goal="Write result file",
                repository_path=str(workspace),
                success_criteria=[
                    SuccessCriterion(
                        name="result_file_contains",
                        description="result.txt",
                        verification_method="file_contains",
                        expected="done\n",
                    ),
                    SuccessCriterion(
                        name="result_file_verifies",
                        description="python -c \"from pathlib import Path; "
                        "assert Path('result.txt').read_text() == 'done\\n'\"",
                        verification_method="test_pass",
                        expected="python -c \"from pathlib import Path; "
                        "assert Path('result.txt').read_text() == 'done\\n'\"",
                    ),
                ],
            )
            result = runtime.run_goal(goal)

            assert result["success"] is True
            assert result["tool_calls"] == 1
            assert result["model_calls"] == 1
            assert result["error"] == ""


class TestDurableRuntimeRetryBehavior:
    def test_retry_wait_tasks_are_retried(self) -> None:
        class FlakyProvider:
            def __init__(self) -> None:
                self.call_count = 0

            async def generate_structured(self, request, response_model):
                self.call_count += 1
                command = "false" if self.call_count == 1 else "echo done"
                return type(
                    "Resp",
                    (),
                    {
                        "content": {
                            "tool_name": "run_command",
                            "command": command,
                            "intention": "Retry until success",
                            "risk_level": "low",
                            "expected_effects": [],
                            "is_terminal": True,
                        }
                    },
                )()

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            runtime = DurableRuntime(data_dir, workspace, provider=FlakyProvider())
            goal = GoalSpecification(
                raw_goal="Retry once",
                normalized_goal="Retry after a failed command",
                repository_path=str(workspace),
            )
            result = runtime.run_goal(goal)

            assert result["success"] is True
            assert result["task_summary"]["committed"] == 1


class TestExperimentRunner:
    def test_comparison_runs_both_runtimes(self) -> None:
        from durable_agent_runtime.experiments.runner import ExperimentRunner
        from durable_agent_runtime.models.base import MockProvider

        with tempfile.TemporaryDirectory() as tmpdir:
            data_dir = Path(tmpdir) / "data"
            workspace = Path(tmpdir) / "workspace"
            workspace.mkdir()

            provider = MockProvider()
            provider.set_fixture(
                "Run comparison",
                {
                    "tool_name": "run_command",
                    "command": "echo comparison complete",
                    "intention": "Complete the comparison task",
                    "risk_level": "low",
                    "expected_effects": ["prints completion message"],
                    "is_terminal": True,
                },
            )

            runner = ExperimentRunner(data_dir, workspace, provider=provider)
            goal = GoalSpecification(
                raw_goal="Compare runtimes",
                normalized_goal="Run comparison",
                repository_path=str(workspace),
            )

            results = runner.run_comparison(goal)
            assert results["baseline"]["success"] is True
            assert results["durable"]["success"] is True
            assert results["provider"] == "mock"
            assert results["model"] == "mock/v1"
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
