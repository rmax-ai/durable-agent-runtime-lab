"""Experiment framework — benchmark runner and metrics (Section 20-21, Milestone 8).

Runs a task against both runtimes, injects faults, collects metrics,
and generates comparison reports.
"""

from __future__ import annotations

import json
import time
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from durable_agent_runtime.domain import GoalSpecification
from durable_agent_runtime.experiments.baseline import BaselineRuntime
from durable_agent_runtime.experiments.durable import DurableRuntime

if TYPE_CHECKING:
    from durable_agent_runtime.models.base import ModelProvider


class ExperimentRunner:
    """Runs controlled experiments comparing baseline vs durable runtime."""

    def __init__(
        self,
        data_dir: Path,
        workspace: Path,
        provider: ModelProvider | None = None,
    ) -> None:
        self.data_dir = Path(data_dir)
        self.workspace = Path(workspace)
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self._provider = provider

    def run_comparison(
        self,
        goal: GoalSpecification,
        faults: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        """Run both runtimes on the same goal and compare results."""
        results: dict[str, Any] = {
            "experiment_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "goal": goal.raw_goal,
            "goal_id": str(goal.goal_id),
        }

        # Run baseline
        baseline_start = time.monotonic()
        baseline = BaselineRuntime(self.workspace, provider=self._provider)
        baseline_result = baseline.run_goal(goal)
        baseline_time = time.monotonic() - baseline_start

        # Run durable
        durable_start = time.monotonic()
        durable = DurableRuntime(self.data_dir, self.workspace, provider=self._provider)
        durable_result = durable.run_goal(goal)
        durable_time = time.monotonic() - durable_start

        results["baseline"] = {
            **baseline_result,
            "wall_clock_time": round(baseline_time, 3),
        }
        results["durable"] = {
            **durable_result,
            "wall_clock_time": round(durable_time, 3),
        }

        # Metrics
        results["metrics"] = {
            "baseline_success": baseline_result["success"],
            "durable_success": durable_result["success"],
            "speedup": round(baseline_time / max(durable_time, 0.001), 2),
            "baseline_model_calls": baseline_result.get("model_calls", 0),
        }

        # Fault injection
        if faults:
            results["faults_configured"] = len(faults)

        return results

    def save_report(self, results: dict[str, Any], output_path: Path | None = None) -> Path:
        """Save experiment results as JSON."""
        path = (
            output_path
            or self.data_dir / "reports" / f"experiment-{results['experiment_id'][:8]}.json"
        )
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(results, indent=2, default=str))
        return path
