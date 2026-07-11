"""CLI entry point — Durable Agent Runtime."""

import json
import uuid
from pathlib import Path
from uuid import UUID

import typer

app = typer.Typer(
    name="dar",
    help="Durable Agent Runtime CLI",
    no_args_is_help=True,
)

# ── Shared helpers ──────────────────────────────────────────────────────────

DATA_DIR = Path("data")


def _get_data_dir() -> Path:
    return Path("data")


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
        raise typer.Exit(1)

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
        raise typer.Exit(1)

    store = StateStore(_get_data_dir())
    wf = store.get_workflow(wf_id)

    if not wf:
        typer.echo(f"No workflow found with ID: {workflow_id}")
        raise typer.Exit(1)

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
        raise typer.Exit(1)

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
        raise typer.Exit(1)

    store = EventStore(_get_data_dir())
    valid, error = store.verify_chain(wf_id)

    if valid:
        typer.echo(f"✅ Ledger integrity verified for workflow {workflow_id}")
    else:
        typer.echo(f"❌ Ledger integrity FAILED: {error}", err=True)
        raise typer.Exit(1)


@app.command()
def inspect(workflow_id: str) -> None:
    """Detailed workflow inspection."""
    from durable_agent_runtime.persistence.event_store import EventStore
    from durable_agent_runtime.persistence.state_store import StateStore

    try:
        wf_id = UUID(workflow_id)
    except ValueError:
        typer.echo(f"Error: invalid workflow ID: {workflow_id}", err=True)
        raise typer.Exit(1)

    events = EventStore(_get_data_dir())
    state = StateStore(_get_data_dir())

    wf = state.get_workflow(wf_id)
    if not wf:
        typer.echo(f"No workflow found: {workflow_id}")
        raise typer.Exit(1)

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
def approve(workflow_id: str, proposal_id: str) -> None:
    """Approve a human-approval-required action."""
    typer.echo("approve — not yet implemented")


@app.command()
def reject(workflow_id: str, proposal_id: str, reason: str = typer.Option("", help="Rejection reason")) -> None:
    """Reject a human-approval-required action."""
    typer.echo("reject — not yet implemented")


@app.command()
def experiment(
    action: str = typer.Argument(..., help="Action: run or report"),
    config: str = typer.Option("", help="Experiment config path"),
    experiment_id: str = typer.Option("", help="Experiment ID for reports"),
) -> None:
    """Run or report on experiments."""
    typer.echo("experiment — not yet implemented")


if __name__ == "__main__":
    app()
