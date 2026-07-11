import shutil
import tempfile
from pathlib import Path

from durable_agent_runtime.domain import GoalSpecification
from durable_agent_runtime.experiments.runner import ExperimentRunner
from durable_agent_runtime.models.base import MockProvider

fixture_repo = Path("benchmarks/repositories/task-01-refactor").resolve()

with tempfile.TemporaryDirectory() as tmpdir:
    workspace = Path(tmpdir) / "repo"
    shutil.copytree(fixture_repo, workspace)

    provider = MockProvider()
    provider.set_fixture(
        "Rename the function compute_tax",
        {
            "tool_name": "run_command",
            "command": "python -m pytest tests/test_calculator.py -q",
            "intention": "Run the fixture test suite inside the staged repository",
            "risk_level": "low",
            "expected_effects": ["executes the benchmark test"],
            "is_terminal": True,
        },
    )

    runner = ExperimentRunner(data_dir=Path("data"), workspace=workspace, provider=provider)
    goal = GoalSpecification(
        raw_goal="Run the task-01 benchmark smoke test",
        normalized_goal="Rename the function compute_tax to calculate_tax",
        repository_path=str(workspace),
    )
    results = runner.run_comparison(goal)
    print(runner.save_report(results))
