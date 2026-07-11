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

All 9 milestones implemented. 155 tests passing.

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

```python
from durable_agent_runtime.domain import GoalSpecification
from durable_agent_runtime.experiments.runner import ExperimentRunner

runner = ExperimentRunner(data_dir="data", workspace="/tmp/workspace")
goal = GoalSpecification(
    raw_goal="Fix the bug in auth.py",
    normalized_goal="Locate and fix the authentication bug",
    repository_path="/tmp/test-repo",
)
results = runner.run_comparison(goal)
runner.save_report(results)
```

## Testing

```bash
# All tests
uv run pytest                     # 155 tests

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

- Mock provider only — real model providers (OpenAI) not yet wired
- Docker executor not yet integrated (process executor only)
- Single-task-per-workflow in CLI; multi-task DAG not yet scheduled
- Human approval CLI stubs exist but approval flow not implemented
- Fault injection configured but not yet integrated into experiment runner

## License

MIT
