# Durable Agent Runtime Lab

**Research-grade platform comparing conventional model-driven agent loops against typed, deterministic, durable workflows.**

## Research Thesis

> Long-horizon AI-agent reliability improves when stochastic model decisions are compiled into typed, deterministic, durable, verifiable workflows rather than executed through an unconstrained conversational tool loop.

The system provides two comparable agent runtimes:

| Runtime | Characteristics |
|---------|----------------|
| **Baseline** | Conventional model-driven tool loop; conversational state; direct sequential execution; simple retries; no durable event replay |
| **Durable** | Typed goal/plan representations; deterministic FSM orchestration; append-only event ledger; proposal→verify→commit boundary; sandboxed execution; checkpoints and recovery; idempotent tool calls; restart-safe |

## Architecture

```
User Goal → Goal Compiler → Typed Goal Spec → Planner → Typed Plan DAG
    → Deterministic Orchestrator → Task Scheduler → Model Proposer
    → Action Proposal → Policy/Schema Verifier → Sandboxed Executor
    → Postcondition Verifier → Commit/Reject → Append-Only Event Ledger
    → Checkpoint & Artifact Store
```

### Deterministic Boundary

Models are **stochastic proposal generators**. They interpret goals, propose plans, diagnose failures, and evaluate outputs. They **never** directly control workflow state transitions, retries, budgets, checkpoints, or sandbox boundaries — those are deterministic application code.

## Current Status

All 9 milestones implemented. 221 tests passing.

| Milestone | Description | Status |
|-----------|-------------|--------|
| M0 | Repository foundation (pyproject.toml, Makefile, AGENTS.md) | ✅ |
| M1 | Canonical Pydantic domain models (8 models, 12 enums, state machines) | ✅ |
| M2 | JSONL event ledger (hash chaining) + SQLite state store + orchestrator | ✅ |
| M3 | Tool boundary (registry, proposal verification, process executor, security) | ✅ |
| M4 | Git checkpoint manager + recovery/replay | ✅ |
| M5 | Model providers (mock + protocol) | ✅ |
| M6 | Full durable runtime end-to-end wiring | ✅ |
| M7 | Baseline runtime (conventional agent loop) | ✅ |
| M8 | Experiment framework (runner, metrics, report generation) | ✅ |
| M9 | Research release | ✅ |

## Quick Start

```bash
# Install
uv sync --extra dev

# Run tests (155 pass)
uv run pytest

# CLI
uv run dar version
uv run dar init
uv run dar --help
```

## Running an Experiment

The old `/tmp/workspace` and `/tmp/test-repo` snippet was incomplete: those paths were just placeholders and nothing created or populated them.

For a self-contained run, use the checked-in quickstart config. It stages a benchmark fixture into `data/runs/...` automatically and writes reports to `data/reports/`.

```bash
uv run dar experiment run --config experiments/configs/quickstart.yaml
uv run dar experiment report
```

For a real model-backed run, the experiment config can declare the provider and model. The CLI accepts overrides with precedence `CLI flag > config file > provider default`.

```bash
export OPENAI_API_KEY=...
uv run dar experiment run --config experiments/configs/core.yaml

# Override config on the command line
uv run dar experiment run \
  --config experiments/configs/core.yaml \
  --provider openai \
  --model gpt-4o-mini
```

If you want the equivalent Python API example, this script creates an isolated workspace, copies in a checked-in fixture repository, and runs both runtimes with a deterministic mock provider:

```python
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
    report_path = runner.save_report(results)
    print(report_path)
```

## Testing

```bash
# All tests
uv run pytest                     # 221 tests

# By category
uv run pytest tests/unit/         # Domain models, state machine, event store
uv run pytest tests/property/     # Hypothesis property-based tests
uv run pytest tests/integration/  # End-to-end runtime, boundary verification

# Lint & format
uv run ruff check src/ tests/
uv run ruff format src/ tests/
```

## Architecture Decision Records

See [docs/adr/](docs/adr/) for detailed decisions:
- ADR-001: SQLite + JSONL for local state
- ADR-002: Git-based checkpointing
- ADR-003: JSONL append-only event ledger
- ADR-004: Provider-neutral model interface
- ADR-005: Docker sandboxing with process fallback
- ADR-006: Deterministic orchestration boundary
- ADR-007: No vector database in v1

## Known Limitations

- OpenAI provider is wired, but live runs depend on local credentials and current API compatibility
- Docker executor not yet integrated (process executor only)
- Single-task-per-workflow in CLI; multi-task DAG not yet scheduled
- Human approval CLI stubs exist but approval flow not implemented
- Fault injection configured but not yet integrated into experiment runner

## License

MIT
