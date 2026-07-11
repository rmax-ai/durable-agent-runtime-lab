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
from durable_agent_runtime.experiments.fault_injection import FaultInjector

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
        """Run both runtimes on the same goal and compare results.

        If *faults* is provided, a :class:`FaultInjector` is created and
        passed to both runtimes so that deterministic faults are applied
        during execution.
        """
        results: dict[str, Any] = {
            "experiment_id": str(uuid.uuid4()),
            "timestamp": datetime.now(UTC).isoformat(),
            "goal": goal.raw_goal,
            "goal_id": str(goal.goal_id),
        }

        # Build fault config if provided
        fault_config: dict[str, Any] = {"faults": faults} if faults else {}
        fault_injector = FaultInjector(fault_config) if faults else None

        # Run baseline
        baseline_start = time.monotonic()
        baseline = BaselineRuntime(
            self.workspace,
            provider=self._provider,
            fault_injector=fault_injector,
        )
        try:
            baseline_result = baseline.run_goal(goal)
        except SystemExit:
            baseline_result = {
                "workflow_id": str(uuid.uuid4()),
                "success": False,
                "error": "process_killed",
                "iterations": 0,
                "output": "",
                "model_calls": 0,
            }
        baseline_time = time.monotonic() - baseline_start

        # Run durable
        durable_start = time.monotonic()
        durable = DurableRuntime(
            self.data_dir,
            self.workspace,
            provider=self._provider,
            fault_injector=fault_injector,
        )
        try:
            durable_result = durable.run_goal(goal)
        except SystemExit:
            durable_result = {
                "workflow_id": str(uuid.uuid4()),
                "success": False,
                "error": "process_killed",
                "task_id": "",
                "output": "",
                "task_results": {},
                "task_summary": {"total": 0, "committed": 0, "failed": 0, "blocked": 0},
            }
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

        # Fault injection summary
        if fault_injector is not None:
            results["faults_configured"] = len(faults or [])
            results["faults_triggered"] = fault_injector.triggered_faults
        else:
            results["faults_configured"] = 0
            results["faults_triggered"] = []

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
