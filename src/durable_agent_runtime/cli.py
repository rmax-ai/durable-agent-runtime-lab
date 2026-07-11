"""CLI entry point — Durable Agent Runtime."""

import json
from pathlib import Path
from typing import Any
from uuid import UUID

import typer
import yaml

app = typer.Typer(
    name="dar",
    help="Durable Agent Runtime CLI",
    no_args_is_help=True,
)

# ── Shared helpers ──────────────────────────────────────────────────────────

DATA_DIR = Path("data")


def _get_data_dir() -> Path:
    return Path("data")


def _load_task_yaml(task_path: str) -> dict[str, Any]:
    """Load a task YAML file and return its content as a dict."""
    path = Path(task_path)
    if not path.exists():
        # Try relative to the project root
        alt = Path.cwd() / task_path
        if alt.exists():
            path = alt
        else:
            raise FileNotFoundError(f"Task file not found: {task_path}")
    with open(path) as f:
        return yaml.safe_load(f)


def _task_yaml_to_goal(data: dict[str, Any]) -> Any:
    """Convert a task YAML dict to a GoalSpecification."""
    from durable_agent_runtime.domain import (
        Budget,
        Constraint,
        GoalSpecification,
        SuccessCriterion,
    )
    from durable_agent_runtime.domain.enums import ApprovalPolicy, RiskLevel

    task_id = data.get("task_id", "unknown")
    goal_text = data.get("goal", data.get("description", ""))
    repo_path = data.get("repository_fixture", ".")

    # Build success criteria from the task definition
    success_criteria = []
    for check in data.get("success_checks", []):
        sc = SuccessCriterion(
            name=check.get("type", "custom"),
            description=str(check.get("command", check.get("path", ""))),
            verification_method=check.get("type", "custom"),
            expected=check.get("pattern", check.get("command", "")),
        )
        success_criteria.append(sc)

    # Build constraints from forbidden_changes
    constraints = []
    for forbid in data.get("forbidden_changes", []):
        c = Constraint(
            name="forbidden_change",
            description=f"Do not modify: {forbid.get('path', 'unknown')}",
            constraint_type="file_scope",
            parameters=forbid,
        )
        constraints.append(c)

    return GoalSpecification(
        raw_goal=goal_text,
        normalized_goal=goal_text,
        repository_path=str(repo_path),
        constraints=constraints,
        success_criteria=success_criteria,
        risk_level=RiskLevel.MEDIUM,
        max_budget=Budget(),
        human_approval_policy=ApprovalPolicy.NONE,
        metadata={
            "task_id": task_id,
            "name": data.get("name", ""),
            "description": data.get("description", ""),
            "complexity": data.get("complexity", 1),
            "fault_injection_points": data.get("fault_injection_points", []),
        },
    )


def _load_experiment_config(config_path: str) -> dict[str, Any]:
    """Load an experiment YAML config file."""
    path = Path(config_path)
    if not path.exists():
        raise FileNotFoundError(f"Experiment config not found: {config_path}")
    with open(path) as f:
        raw = yaml.safe_load(f)
    exp = raw.get("experiment", raw)
    return exp


# ── Core commands ───────────────────────────────────────────────────────────


@app.command()
def version() -> None:
    """Print the DAR version."""
    import importlib.metadata

    try:
        v = importlib.metadata.version("durable-agent-runtime")
        typer.echo(f"dar v{v}")
    except importlib.metadata.PackageNotFoundError:
        typer.echo("dar v0.1.0 (development)")


@app.command()
def init() -> None:
    """Initialize a new DAR workspace."""
    data_dir = Path("data")
    data_dir.mkdir(parents=True, exist_ok=True)
    typer.echo(f"✅ DAR workspace initialized at {data_dir.absolute()}")


@app.command()
def run(
    runtime: str = typer.Option(..., help="Runtime to use: baseline or durable"),
    task: str = typer.Option(..., help="Path to task YAML definition"),
    output: str = typer.Option("text", help="Output format: text or json"),
) -> None:
    """Run a benchmark task."""
    if runtime not in ("baseline", "durable"):
        typer.echo(f"Error: runtime must be 'baseline' or 'durable', got '{runtime}'", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"Running task '{task}' with {runtime} runtime...")
    if output == "json":
        typer.echo(json.dumps({"status": "not_implemented", "runtime": runtime, "task": task}))
    else:
        typer.echo("⚠️  Full runtime execution not yet implemented — see roadmap.")


# ── Inspection commands ─────────────────────────────────────────────────────


@app.command()
def status(workflow_id: str) -> None:
    """Show current workflow status."""
    from durable_agent_runtime.persistence.state_store import StateStore

    try:
        wf_id = UUID(workflow_id)
    except ValueError:
        typer.echo(f"Error: invalid workflow ID: {workflow_id}", err=True)
        raise typer.Exit(1) from None

    store = StateStore(_get_data_dir())
    wf = store.get_workflow(wf_id)

    if not wf:
        typer.echo(f"No workflow found with ID: {workflow_id}")
        raise typer.Exit(1) from None

    typer.echo(f"Workflow: {wf.workflow_id}")
    typer.echo(f"  Status:       {wf.status}")
    typer.echo(f"  Last event:   {wf.last_event_sequence}")
    typer.echo(f"  Tokens used:  {wf.tokens_used}")
    typer.echo(f"  Model calls:  {wf.model_calls}")
    typer.echo(f"  Tool calls:   {wf.tool_calls}")
    typer.echo(f"  Est. cost:    ${wf.estimated_cost:.4f}")

    tasks = store.get_tasks_by_workflow(wf_id)
    if tasks:
        typer.echo(f"\n  Tasks ({len(tasks)}):")
        for t in tasks:
            typer.echo(f"    [{t.status}] {t.task_id[:8]}...")


@app.command()
def events(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
    limit: int = typer.Option(50, help="Maximum events to show"),
    output: str = typer.Option("text", help="Output format: text or json"),
) -> None:
    """List events for a workflow."""
    from durable_agent_runtime.persistence.event_store import EventStore

    try:
        wf_id = UUID(workflow_id)
    except ValueError:
        typer.echo(f"Error: invalid workflow ID: {workflow_id}", err=True)
        raise typer.Exit(1) from None

    store = EventStore(_get_data_dir())
    all_events = store.read_all(wf_id)
    all_events = all_events[-limit:]

    if output == "json":
        result = [e.model_dump(mode="json") for e in all_events]
        typer.echo(json.dumps(result, indent=2, default=str))
    else:
        if not all_events:
            typer.echo("No events found.")
            return
        for e in all_events:
            ts = e.timestamp.isoformat()[:19] if e.timestamp else "?"
            typer.echo(f"[{e.sequence:04d}] {ts}  {e.event_type.value}")


@app.command()
def verify_ledger(workflow_id: str) -> None:
    """Verify event ledger hash chain integrity."""
    from durable_agent_runtime.persistence.event_store import EventStore

    try:
        wf_id = UUID(workflow_id)
    except ValueError:
        typer.echo(f"Error: invalid workflow ID: {workflow_id}", err=True)
        raise typer.Exit(1) from None

    store = EventStore(_get_data_dir())
    valid, error = store.verify_chain(wf_id)

    if valid:
        typer.echo(f"✅ Ledger integrity verified for workflow {workflow_id}")
    else:
        typer.echo(f"❌ Ledger integrity FAILED: {error}", err=True)
        raise typer.Exit(1) from None


@app.command()
def inspect(workflow_id: str) -> None:
    """Detailed workflow inspection."""
    from durable_agent_runtime.persistence.event_store import EventStore
    from durable_agent_runtime.persistence.state_store import StateStore

    try:
        wf_id = UUID(workflow_id)
    except ValueError:
        typer.echo(f"Error: invalid workflow ID: {workflow_id}", err=True)
        raise typer.Exit(1) from None

    events = EventStore(_get_data_dir())
    state = StateStore(_get_data_dir())

    wf = state.get_workflow(wf_id)
    if not wf:
        typer.echo(f"No workflow found: {workflow_id}")
        raise typer.Exit(1) from None

    valid, err = events.verify_chain(wf_id)

    typer.echo("=" * 60)
    typer.echo(f"Workflow: {wf.workflow_id}")
    typer.echo(f"  Status:       {wf.status}")
    typer.echo(f"  Ledger:       {'✅ valid' if valid else '❌ ' + (err or 'unknown')}")
    typer.echo(f"  Events:       {wf.last_event_sequence + 1}")
    typer.echo(f"  Tokens:       {wf.tokens_used}")
    typer.echo(f"  Model calls:  {wf.model_calls}")
    typer.echo(f"  Tool calls:   {wf.tool_calls}")
    typer.echo(f"  Cost:         ${wf.estimated_cost:.4f}")

    tasks = state.get_tasks_by_workflow(wf_id)
    if tasks:
        typer.echo(f"\n  Tasks ({len(tasks)}):")
        for t in tasks:
            typer.echo(f"    [{t.status:14s}] {t.task_id}")
    typer.echo("=" * 60)


@app.command()
def checkpoint(workflow_id: str) -> None:
    """Create a manual checkpoint."""
    typer.echo("checkpoint — not yet implemented")


@app.command()
def replay(workflow_id: str) -> None:
    """Replay events for a workflow without model calls."""
    typer.echo("replay — not yet implemented")


@app.command()
def resume(workflow_id: str) -> None:
    """Resume a paused or recovered workflow."""
    typer.echo("resume — not yet implemented")


@app.command()
def cancel(workflow_id: str) -> None:
    """Cancel a workflow."""
    typer.echo("cancel — not yet implemented")


@app.command()
def approve(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
    proposal_id: str = typer.Argument(..., help="Proposal ID"),
) -> None:
    """Approve a human-approval-required action."""
    from durable_agent_runtime.orchestration.engine import OrchestratorEngine

    try:
        wf_id = UUID(workflow_id)
        prop_id = UUID(proposal_id)
    except ValueError:
        typer.echo("Error: invalid UUID format", err=True)
        raise typer.Exit(1) from None

    engine = OrchestratorEngine(_get_data_dir())
    try:
        engine.approve(wf_id, prop_id)
        typer.echo(f"✅ Approved proposal {proposal_id} for workflow {workflow_id}")
    except ValueError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1) from None


@app.command()
def reject(
    workflow_id: str = typer.Argument(..., help="Workflow ID"),
    proposal_id: str = typer.Argument(..., help="Proposal ID"),
    reason: str = typer.Option("", help="Rejection reason"),
) -> None:
    """Reject a human-approval-required action."""
    from durable_agent_runtime.orchestration.engine import OrchestratorEngine

    try:
        wf_id = UUID(workflow_id)
        prop_id = UUID(proposal_id)
    except ValueError:
        typer.echo("Error: invalid UUID format", err=True)
        raise typer.Exit(1) from None

    engine = OrchestratorEngine(_get_data_dir())
    try:
        engine.reject(wf_id, prop_id, reason)
        msg = f"Rejected proposal {proposal_id} for workflow {workflow_id}"
        if reason:
            msg += f" (reason: {reason})"
        typer.echo(f"✅ {msg}")
    except ValueError as e:
        typer.echo(f"❌ {e}", err=True)
        raise typer.Exit(1) from None


# ── Experiment commands (sub-Typer) ─────────────────────────────────────────


@app.command()
def experiment(
    action: str = typer.Argument(..., help="Action to perform: run, report"),
    config_path: str = typer.Option(
        "", "--config", "-c", help="Path to experiment config YAML (for 'run')"
    ),
    experiment_id: str = typer.Option(
        "", "--experiment-id", "-e", help="Experiment ID (for 'report')"
    ),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Report format: markdown or json"
    ),
) -> None:
    """Run experiments or generate reports.

    Examples:
      dar experiment run --config experiments/configs/core.yaml
      dar experiment report --experiment-id <id>
      dar experiment report --experiment-id <id> --format json
    """
    if action == "run":
        _cmd_experiment_run(config_path)
    elif action == "report":
        _cmd_experiment_report(experiment_id, output_format)
    else:
        typer.echo(f"Error: unknown action '{action}'. Use 'run' or 'report'.", err=True)
        raise typer.Exit(1) from None


def _cmd_experiment_run(config_path: str) -> None:
    """Run an experiment from its config YAML."""
    from durable_agent_runtime.experiments.runner import ExperimentRunner

    if not config_path:
        typer.echo("Error: --config is required for 'dar experiment run'", err=True)
        raise typer.Exit(1) from None

    typer.echo(f"📋 Loading experiment config: {config_path}")
    config = _load_experiment_config(config_path)

    name = config.get("name", "Unnamed experiment")
    task_paths = config.get("tasks", [])
    repeats = config.get("repeats", 1)
    faults = config.get("faults", [])

    typer.echo(f"  Experiment: {name}")
    typer.echo(f"  Tasks:      {len(task_paths)} tasks x {repeats} repeats")
    typer.echo(f"  Faults:     {len(faults)} configured")
    typer.echo()

    data_dir = _get_data_dir()
    workspace = Path.cwd()

    runner = ExperimentRunner(
        data_dir=data_dir,
        workspace=workspace,
        provider=None,  # Uses MockProvider by default
    )

    experiment_start = time.monotonic()
    all_report_paths: list[Path] = []
    task_summary: dict[str, dict[str, int]] = {}

    for task_path in task_paths:
        typer.echo(f"  ── {task_path} ──")

        task_data = _load_task_yaml(task_path)
        goal = _task_yaml_to_goal(task_data)
        task_name = task_data.get("name", task_path)

        for repeat in range(repeats):
            label = f"      Run {repeat + 1}/{repeats}: "
            try:
                results = runner.run_comparison(
                    goal=goal,
                    faults=faults,
                )
                report_path = runner.save_report(results)
                all_report_paths.append(report_path)

                baseline_ok = results.get("metrics", {}).get("baseline_success", False)
                durable_ok = results.get("metrics", {}).get("durable_success", False)

                typer.echo(
                    f"{label}baseline={'✅' if baseline_ok else '❌'} "
                    f"durable={'✅' if durable_ok else '❌'} "
                    f"→ {report_path.name}"
                )

                # Track summary
                if task_name not in task_summary:
                    task_summary[task_name] = {"baseline_ok": 0, "durable_ok": 0, "total": 0}
                task_summary[task_name]["total"] += 1
                if baseline_ok:
                    task_summary[task_name]["baseline_ok"] += 1
                if durable_ok:
                    task_summary[task_name]["durable_ok"] += 1

            except Exception as exc:
                typer.echo(f"{label}⚠️  Error: {exc}", err=True)

    total_elapsed = time.monotonic() - experiment_start

    # ── Print summary table ─────────────────────────────────────────────
    typer.echo()
    typer.echo("=" * 64)
    typer.echo("  EXPERIMENT SUMMARY")
    typer.echo("=" * 64)

    typer.echo(f"\n  {'Task':<30s} {'Baseline':>10s} {'Durable':>10s} {'Total':>6s}")
    typer.echo(f"  {'─' * 30} {'─' * 10} {'─' * 10} {'─' * 6}")
    for tname, stats in task_summary.items():
        short_name = tname[:28]
        typer.echo(
            f"  {short_name:<30s} {stats['baseline_ok']:>4d}/{stats['total']:<4d} "
            f"{stats['durable_ok']:>4d}/{stats['total']:<4d} {stats['total']:>4d}"
        )

    typer.echo(f"\n  Total elapsed: {total_elapsed:.1f}s")
    typer.echo(f"  Reports saved: {len(all_report_paths)}")
    typer.echo(f"  Reports dir:   {data_dir / 'reports' / ''}")
    typer.echo()


def _cmd_experiment_report(experiment_id: str, output_format: str) -> None:
    """Generate a report from saved experiment results."""
    data_dir = _get_data_dir()
    reports_dir = data_dir / "reports"

    if not reports_dir.exists():
        typer.echo("No reports directory found. Run an experiment first.", err=True)
        raise typer.Exit(1) from None

    if experiment_id:
        # Load specific report
        report_path = reports_dir / f"experiment-{experiment_id[:8]}.json"
        if not report_path.exists():
            # Try exact match
            report_path = Path(experiment_id)
            if not report_path.exists():
                typer.echo(
                    f"Report not found: experiment-{experiment_id[:8]}.json "
                    f"(checked {reports_dir} and {experiment_id})",
                    err=True,
                )
                raise typer.Exit(1) from None
    else:
        # Load all reports and merge
        json_files = sorted(reports_dir.glob("experiment-*.json"))
        if not json_files:
            typer.echo("No experiment reports found in data/reports/", err=True)
            raise typer.Exit(1) from None
        # Use the latest report
        report_path = json_files[-1]
        typer.echo(f"Using latest report: {report_path}")

    with open(report_path) as f:
        results = json.load(f)

    if output_format == "json":
        typer.echo(json.dumps(results, indent=2, default=str))
        return

    # ── Generate Markdown report ────────────────────────────────────────
    exp_id = results.get("experiment_id", "unknown")[:8]
    goal = results.get("goal", "No goal specified")
    timestamp = results.get("timestamp", "unknown")

    baseline = results.get("baseline", {})
    durable = results.get("durable", {})
    metrics = results.get("metrics", {})
    faults_configured = results.get("faults_configured", 0)
    faults_triggered = results.get("faults_triggered", [])

    output = []
    output.append(f"# Experiment Report: {exp_id}")
    output.append("")
    output.append(f"**Generated:** {timestamp}")
    output.append("")
    output.append("---")
    output.append("")
    output.append("## Hypothesis")
    output.append("")
    output.append(
        "The durable runtime (event-sourced, checkpointed, deterministic) "
        "will match or exceed the baseline runtime in task success rate while "
        "providing stronger guarantees around recovery and auditability."
    )
    output.append("")
    output.append("## Setup")
    output.append("")
    output.append(f"- **Goal:** {goal}")
    output.append(f"- **Experiment ID:** {exp_id}")
    output.append("- **Provider:** MockProvider (deterministic)")
    output.append("")
    output.append("## Results")
    output.append("")
    output.append("| Metric | Baseline | Durable |")
    output.append("|--------|----------|---------|")
    output.append(
        f"| Success | {'✅' if metrics.get('baseline_success') else '❌'} "
        f"| {'✅' if metrics.get('durable_success') else '❌'} |"
    )
    output.append(
        f"| Wall-clock time (s) | {baseline.get('wall_clock_time', 'N/A')} "
        f"| {durable.get('wall_clock_time', 'N/A')} |"
    )
    output.append(
        f"| Model calls | {metrics.get('baseline_model_calls', 'N/A')} "
        f"| {durable.get('model_calls', 'N/A')} |"
    )
    output.append(f"| Speedup (baseline/durable) | — | {metrics.get('speedup', 'N/A')} |")
    output.append("")
    output.append("## Fault Injection Summary")
    output.append("")
    output.append(f"- **Faults configured:** {faults_configured}")
    output.append(f"- **Faults triggered:** {len(faults_triggered)}")
    if faults_triggered:
        output.append("")
        output.append("| Fault Type | Trigger |")
        output.append("|------------|---------|")
        for ft in faults_triggered:
            trigger = ft.get("trigger", {})
            trigger_desc = trigger.get("event_type", trigger.get("tool_name", "unknown"))
            output.append(f"| {ft.get('type', 'unknown')} | {trigger_desc} |")
    output.append("")
    output.append("## Cost Analysis")
    output.append("")
    output.append(
        "With MockProvider, actual API costs are not incurred. "
        "Token estimates are based on simulated usage."
    )
    output.append("")
    output.append("## Limitations")
    output.append("")
    output.append("- Results are from MockProvider, not real model inference.")
    output.append("- Single-run data — no statistical significance claimed.")
    output.append("- Fault injection is deterministic; real-world failures are stochastic.")
    output.append("")

    report_text = "\n".join(output)
    typer.echo(report_text)


# ── Import time for monotonic clock ─────────────────────────────────────────
import time  # noqa: E402

if __name__ == "__main__":
    app()
