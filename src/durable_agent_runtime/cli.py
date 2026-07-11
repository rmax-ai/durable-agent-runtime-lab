"""CLI entry point — Durable Agent Runtime."""

import json
import shutil
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

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


def _resolve_experiment_provider_name(config: dict[str, Any], provider_name: str) -> str:
    """Resolve experiment provider from CLI override, config, then default."""
    resolved = (provider_name or str(config.get("provider", ""))).strip().lower() or "mock"
    if resolved not in {"mock", "openai"}:
        raise ValueError(f"unknown provider '{resolved}'. Use 'mock' or 'openai'.")
    return resolved


def _resolve_experiment_model_name(
    config: dict[str, Any],
    provider_name: str,
    model_name: str,
) -> str | None:
    """Resolve experiment model from CLI override, config, then provider default."""
    resolved = model_name.strip() or str(config.get("model", "")).strip()
    if provider_name == "openai":
        return resolved or "gpt-5.4-mini"
    return resolved or None


def _build_model_provider(provider_name: str, model_name: str | None) -> Any | None:
    """Construct a model provider instance for experiment execution."""
    import os

    if provider_name == "mock":
        return None
    if provider_name != "openai":
        raise ValueError(f"unknown provider '{provider_name}'. Use 'mock' or 'openai'.")

    from durable_agent_runtime.models.openai_provider import OpenAIProvider

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENAI_API_KEY not set. Set it via .envrc or environment.")
    return OpenAIProvider(api_key=api_key, model=model_name or "gpt-5.4-mini")


def _prepare_task_workspace(task_data: dict[str, Any], data_dir: Path, run_label: str) -> Path:
    """Copy a task repository fixture into an isolated run workspace."""
    task_id = task_data.get("task_id", "task")
    fixture_value = task_data.get("repository_fixture")

    if not fixture_value:
        raise ValueError(f"Task {task_id} is missing repository_fixture")

    fixture_path = Path(fixture_value)
    if not fixture_path.is_absolute():
        fixture_path = (Path.cwd() / fixture_path).resolve()
    else:
        fixture_path = fixture_path.resolve()

    if not fixture_path.exists() or not fixture_path.is_dir():
        raise FileNotFoundError(f"Repository fixture not found: {fixture_path}")

    workspace = data_dir / "runs" / task_id / run_label / "repo"
    workspace.parent.mkdir(parents=True, exist_ok=True)

    if workspace.exists():
        shutil.rmtree(workspace)

    shutil.copytree(fixture_path, workspace)
    return workspace


def _save_run_manifest(data_dir: Path, manifest: dict[str, Any]) -> Path:
    """Persist a run-level experiment manifest."""
    path = data_dir / "reports" / f"run-{manifest['run_id'][:8]}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(manifest, indent=2, default=str))
    return path


def _select_latest_report_path(pattern: str, reports_dir: Path) -> Path | None:
    """Return the newest report path for the given glob pattern."""
    candidates = list(reports_dir.glob(pattern))
    if not candidates:
        return None
    return max(candidates, key=lambda path: (path.stat().st_mtime, path.name))


def _format_task_summary_rows(task_summary: dict[str, dict[str, int]]) -> list[str]:
    """Render a task summary table for run-level reports."""
    output = []
    output.append("| Task | Baseline | Durable | Total |")
    output.append("|------|----------|---------|-------|")
    for task_name, stats in task_summary.items():
        output.append(
            f"| {task_name} | {stats['baseline_ok']}/{stats['total']} "
            f"| {stats['durable_ok']}/{stats['total']} | {stats['total']} |"
        )
    return output


def _summarize_error(value: Any, limit: int = 120) -> str:
    """Normalize one error value into a short single-line summary."""
    text = str(value or "").strip()
    if not text:
        return ""
    text = " ".join(text.split())
    if len(text) <= limit:
        return text
    return f"{text[: limit - 3]}..."


def _render_single_experiment_report(results: dict[str, Any]) -> str:
    """Generate Markdown for one experiment comparison."""
    exp_id = results.get("experiment_id", "unknown")[:8]
    goal = results.get("goal", "No goal specified")
    timestamp = results.get("timestamp", "unknown")

    baseline = results.get("baseline", {})
    durable = results.get("durable", {})
    metrics = results.get("metrics", {})
    faults_configured = results.get("faults_configured", 0)
    faults_triggered = results.get("faults_triggered", [])
    provider_name = str(results.get("provider", "")).strip() or "unknown (not recorded)"
    model_name = str(results.get("model", "")).strip() or "unknown (not recorded)"
    is_mock_provider = provider_name == "mock"

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
    output.append(f"- **Provider:** {provider_name}")
    output.append(f"- **Model:** {model_name}")
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
    if is_mock_provider:
        output.append(
            "With MockProvider, actual API costs are not incurred. "
            "Token estimates are based on simulated usage."
        )
    else:
        output.append(
            "This run used a real model provider. Any token counts, latency, and costs reflect "
            "live inference behavior captured during the experiment."
        )
    output.append("")
    output.append("## Limitations")
    output.append("")
    if is_mock_provider:
        output.append("- Results are from MockProvider, not real model inference.")
    elif provider_name == "unknown (not recorded)":
        output.append("- Provider metadata was not recorded in this report.")
    else:
        output.append("- Single-run behavior may vary across repeated live model executions.")
    output.append("- Single-run data — no statistical significance claimed.")
    output.append("- Fault injection is deterministic; real-world failures are stochastic.")
    output.append("")

    return "\n".join(output)


def _render_run_report(manifest: dict[str, Any]) -> str:
    """Generate Markdown for one multi-experiment run manifest."""
    run_id = str(manifest.get("run_id", "unknown"))[:8]
    experiment_name = manifest.get("experiment_name", "Unnamed experiment")
    config_path = manifest.get("config_path", "unknown")
    provider_name = str(manifest.get("provider", "")).strip() or "unknown (not recorded)"
    model_name = str(manifest.get("model", "")).strip() or "unknown (not recorded)"
    started_at = manifest.get("started_at", "unknown")
    finished_at = manifest.get("finished_at", "unknown")
    repeats = manifest.get("repeats", 0)
    faults_configured = manifest.get("faults_configured", 0)
    task_summary = manifest.get("task_summary", {})
    total_elapsed = manifest.get("total_elapsed_seconds", "N/A")
    total_reports = manifest.get("reports_saved", 0)
    entries = manifest.get("entries", [])

    baseline_total = sum(stats.get("baseline_ok", 0) for stats in task_summary.values())
    durable_total = sum(stats.get("durable_ok", 0) for stats in task_summary.values())
    comparisons_total = sum(stats.get("total", 0) for stats in task_summary.values())

    output = []
    output.append(f"# Experiment Run Report: {run_id}")
    output.append("")
    output.append(f"**Started:** {started_at}")
    output.append(f"**Finished:** {finished_at}")
    output.append("")
    output.append("---")
    output.append("")
    output.append("## Setup")
    output.append("")
    output.append(f"- **Experiment:** {experiment_name}")
    output.append(f"- **Config:** {config_path}")
    output.append(f"- **Run ID:** {run_id}")
    output.append(f"- **Provider:** {provider_name}")
    output.append(f"- **Model:** {model_name}")
    output.append(f"- **Repeats per task:** {repeats}")
    output.append(f"- **Faults configured:** {faults_configured}")
    output.append(f"- **Reports saved:** {total_reports}")
    output.append("")
    output.append("## Aggregate Results")
    output.append("")
    output.extend(_format_task_summary_rows(task_summary))
    output.append("")
    output.append("| Overall Metric | Baseline | Durable | Total |")
    output.append("|----------------|----------|---------|-------|")
    output.append(
        f"| Successful comparisons | {baseline_total}/{comparisons_total} "
        f"| {durable_total}/{comparisons_total} | {comparisons_total} |"
    )
    output.append("")
    output.append(f"- **Total elapsed:** {total_elapsed}s")
    output.append("")
    output.append("## Individual Reports")
    output.append("")
    output.append("| Task | Repeat | Baseline | Durable | Report | Failure Detail |")
    output.append("|------|--------|----------|---------|--------|----------------|")
    for entry in entries:
        report_name = Path(entry.get("report_path", "")).name or "unknown"
        failure_parts = []
        if not entry.get("baseline_success"):
            baseline_error = _summarize_error(entry.get("baseline_error"))
            if baseline_error:
                failure_parts.append(f"baseline: {baseline_error}")
        if not entry.get("durable_success"):
            durable_error = _summarize_error(entry.get("durable_error"))
            if durable_error:
                failure_parts.append(f"durable: {durable_error}")
        failure_detail = " | ".join(failure_parts) or "—"
        output.append(
            f"| {entry.get('task_name', 'unknown')} | {entry.get('repeat', '?')} "
            f"| {'✅' if entry.get('baseline_success') else '❌'} "
            f"| {'✅' if entry.get('durable_success') else '❌'} | {report_name} "
            f"| {failure_detail} |"
        )
    output.append("")

    return "\n".join(output)


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
    run_id: str = typer.Option("", "--run-id", help="Run ID (for 'report')"),
    output_format: str = typer.Option(
        "markdown", "--format", "-f", help="Report format: markdown or json"
    ),
    provider_name: str = typer.Option(
        "", "--provider", "-p", help="Model provider override: mock or openai"
    ),
    model_name: str = typer.Option("", "--model", "-m", help="Model override for provider runs"),
) -> None:
    """Run experiments or generate reports.

    Examples:
      dar experiment run --config experiments/configs/quickstart.yaml
      dar experiment run --config experiments/configs/core.yaml
      dar experiment run --config experiments/configs/core.yaml \
        --provider openai --model gpt-4o-mini
      dar experiment report --run-id <id>
      dar experiment report --experiment-id <id>
      dar experiment report --experiment-id <id> --format json
    """
    if action == "run":
        _cmd_experiment_run(config_path, provider_name, model_name)
    elif action == "report":
        _cmd_experiment_report(experiment_id, run_id, output_format)
    else:
        typer.echo(f"Error: unknown action '{action}'. Use 'run' or 'report'.", err=True)
        raise typer.Exit(1) from None


def _cmd_experiment_run(
    config_path: str,
    provider_name: str = "",
    model_name: str = "",
) -> None:
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
    resolved_provider_name = _resolve_experiment_provider_name(config, provider_name)
    resolved_model_name = _resolve_experiment_model_name(
        config,
        resolved_provider_name,
        model_name,
    )

    typer.echo(f"  Experiment: {name}")
    typer.echo(f"  Tasks:      {len(task_paths)} tasks x {repeats} repeats")
    typer.echo(f"  Faults:     {len(faults)} configured")
    typer.echo(f"  Provider:   {resolved_provider_name}")
    if resolved_model_name:
        typer.echo(f"  Model:      {resolved_model_name}")
    typer.echo()

    data_dir = _get_data_dir()
    try:
        provider = _build_model_provider(resolved_provider_name, resolved_model_name)
    except ValueError as exc:
        typer.echo(f"Error: {exc}", err=True)
        raise typer.Exit(1) from None

    experiment_start = time.monotonic()
    run_started_at = datetime.now(UTC).isoformat()
    run_id = str(uuid4())
    all_report_paths: list[Path] = []
    task_summary: dict[str, dict[str, int]] = {}
    run_entries: list[dict[str, Any]] = []

    for task_path in task_paths:
        typer.echo(f"  ── {task_path} ──")

        task_data = _load_task_yaml(task_path)
        task_name = task_data.get("name", task_path)

        for repeat in range(repeats):
            label = f"      Run {repeat + 1}/{repeats}: "
            try:
                run_label = f"repeat-{repeat + 1}"
                task_workspace = _prepare_task_workspace(task_data, data_dir, run_label)
                goal = _task_yaml_to_goal(task_data).model_copy(
                    update={"repository_path": str(task_workspace)}
                )
                runner = ExperimentRunner(
                    data_dir=data_dir,
                    workspace=task_workspace,
                    provider=provider,  # None = MockProvider
                )
                results = runner.run_comparison(
                    goal=goal,
                    faults=faults,
                )
                report_path = runner.save_report(results)
                all_report_paths.append(report_path)

                baseline_ok = results.get("metrics", {}).get("baseline_success", False)
                durable_ok = results.get("metrics", {}).get("durable_success", False)
                run_entries.append(
                    {
                        "task_path": task_path,
                        "task_name": task_name,
                        "repeat": repeat + 1,
                        "workspace": str(task_workspace),
                        "report_path": str(report_path),
                        "experiment_id": results.get("experiment_id", ""),
                        "baseline_success": baseline_ok,
                        "durable_success": durable_ok,
                        "baseline_error": results.get("baseline", {}).get("error", ""),
                        "durable_error": results.get("durable", {}).get("error", ""),
                    }
                )

                typer.echo(
                    f"{label}baseline={'✅' if baseline_ok else '❌'} "
                    f"durable={'✅' if durable_ok else '❌'} "
                    f"→ {report_path.name} "
                    f"(workspace: {task_workspace})"
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
    run_manifest = {
        "run_id": run_id,
        "experiment_name": name,
        "config_path": config_path,
        "provider": resolved_provider_name,
        "model": resolved_model_name or "",
        "started_at": run_started_at,
        "finished_at": datetime.now(UTC).isoformat(),
        "tasks": task_paths,
        "repeats": repeats,
        "faults_configured": len(faults),
        "reports_saved": len(all_report_paths),
        "report_paths": [str(path) for path in all_report_paths],
        "task_summary": task_summary,
        "entries": run_entries,
        "total_elapsed_seconds": round(total_elapsed, 3),
    }
    run_manifest_path = _save_run_manifest(data_dir, run_manifest)

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
    typer.echo(f"  Run report:    {run_manifest_path.name}")
    typer.echo(f"  Reports dir:   {data_dir / 'reports' / ''}")
    typer.echo()


def _cmd_experiment_report(experiment_id: str, run_id: str, output_format: str) -> None:
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
        with open(report_path) as f:
            results = json.load(f)
        if output_format == "json":
            typer.echo(json.dumps(results, indent=2, default=str))
            return
        typer.echo(_render_single_experiment_report(results))
        return

    if run_id:
        report_path = reports_dir / f"run-{run_id[:8]}.json"
        if not report_path.exists():
            report_path = Path(run_id)
            if not report_path.exists():
                typer.echo(
                    f"Run report not found: run-{run_id[:8]}.json "
                    f"(checked {reports_dir} and {run_id})",
                    err=True,
                )
                raise typer.Exit(1) from None
        with open(report_path) as f:
            results = json.load(f)
        if output_format == "json":
            typer.echo(json.dumps(results, indent=2, default=str))
            return
        typer.echo(_render_run_report(results))
        return

    latest_run = _select_latest_report_path("run-*.json", reports_dir)
    if latest_run is not None:
        typer.echo(f"Using latest run report: {latest_run}")
        with open(latest_run) as f:
            results = json.load(f)
        if output_format == "json":
            typer.echo(json.dumps(results, indent=2, default=str))
            return
        typer.echo(_render_run_report(results))
        return

    report_path = _select_latest_report_path("experiment-*.json", reports_dir)
    if report_path is None:
        typer.echo("No experiment reports found in data/reports/", err=True)
        raise typer.Exit(1) from None
    typer.echo(f"Using latest report: {report_path}")

    with open(report_path) as f:
        results = json.load(f)

    if output_format == "json":
        typer.echo(json.dumps(results, indent=2, default=str))
        return

    typer.echo(_render_single_experiment_report(results))
    return


# ── Import time for monotonic clock ─────────────────────────────────────────
import time  # noqa: E402

if __name__ == "__main__":
    app()
