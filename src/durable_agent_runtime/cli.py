"""CLI entry point — minimal stub for Milestone 0."""

import typer

app = typer.Typer(
    name="dar",
    help="Durable Agent Runtime CLI",
    no_args_is_help=True,
)


@app.command()
def version() -> None:
    """Print the DAR version."""
    import importlib.metadata

    try:
        v = importlib.metadata.version("durable-agent-runtime")
        print(f"dar v{v}")
    except importlib.metadata.PackageNotFoundError:
        print("dar v0.1.0 (development)")


@app.command()
def init() -> None:
    """Initialize a new DAR workspace."""
    print("dar init — not yet implemented")


@app.command()
def run(
    runtime: str = typer.Option(..., help="Runtime to use: baseline or durable"),
    task: str = typer.Option(..., help="Path to task YAML definition"),
) -> None:
    """Run a benchmark task."""
    print(f"dar run --runtime {runtime} --task {task} — not yet implemented")


if __name__ == "__main__":
    app()
