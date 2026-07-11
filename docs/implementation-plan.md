# Implementation Plan — Durable Agent Runtime Lab

> **For Hermes:** Use subagent-driven-development or Codex CLI to implement per-milestone.

**Goal:** Build a research-grade platform comparing conventional model-driven agent loops against typed, deterministic, durable workflows.

**Architecture:** Python 3.12 + Pydantic v2 domain models → JSON Schema → typed pipelines. Deterministic orchestration (state machines, event sourcing, checkpointing) decoupled from stochastic model proposals. Two comparable runtimes sharing the same tools and provider interfaces.

**Tech Stack:** Python 3.12, Pydantic v2, Typer, SQLAlchemy/SQLModel, SQLite, JSONL, Hypothesis, ruff, mypy, pytest

---

## Acceptance Criteria

- [ ] Package installs with `uv sync --extra dev`
- [ ] CLI opens with `uv run dar --help`
- [ ] All 8 canonical domain models produce valid JSON Schema
- [ ] Python and JSON schemas cannot diverge (generated from same source)
- [ ] Invalid state transitions are rejected with typed errors
- [ ] Event hash chaining integrity
- [ ] All 98 unit + 14 property tests pass
- [ ] Lint clean (ruff), format clean
- [ ] Package importable: `from durable_agent_runtime.domain import GoalSpecification, ...`

---

## Milestone Status

| Milestone | Status |
|-----------|--------|
| M0 — Repository Foundation | ✅ Complete |
| M1 — Canonical Domain Model | ✅ Complete |
| M2 — Event Ledger & State Machine | 🔜 Next |
| M3 — Tool Boundary & Executor | Backlog |
| M4 — Checkpoints & Recovery | Backlog |
| M5 — Goal Compiler, Planner, Model Router | Backlog |
| M6 — Full Durable Runtime | Backlog |
| M7 — Baseline Runtime | Backlog |
| M8 — Experiment Framework | Backlog |
| M9 — Research Release | Backlog |

---

## Architecture Decisions (ADRs)

See [docs/adr/](adr/) for detailed Architecture Decision Records:

1. **ADR-001**: SQLite + JSONL for local state (not Temporal, not PostgreSQL)
2. **ADR-002**: Git-based checkpointing (not distributed snapshots)
3. **ADR-003**: JSONL append-only event ledger (not Kafka, not database events table)
4. **ADR-004**: Provider-neutral model interface with mock provider
5. **ADR-005**: Docker sandboxing with process-based test backend
6. **ADR-006**: Deterministic orchestration — models propose, code decides
7. **ADR-007**: No vector database in v1 — deterministic retrieval first

---

## Next Milestone: M2 — Event Ledger & State Machine

**Dependencies:** M1 complete

**Files to create:**
- `src/durable_agent_runtime/persistence/event_store.py` — append-only JSONL store with hash chaining
- `src/durable_agent_runtime/persistence/state_store.py` — SQLite state projections from events
- `src/durable_agent_runtime/persistence/database.py` — SQLAlchemy/SQLModel setup
- `src/durable_agent_runtime/orchestration/engine.py` — deterministic orchestrator using state machine
- `tests/unit/test_event_store.py` — hash integrity, append-only, replay
- `tests/unit/test_state_store.py` — projection correctness
- `tests/integration/test_event_ledger.py` — end-to-end event flow

**Acceptance criteria:**
- Events can only be appended, never modified
- Tampered event hash chains are detected
- Workflow state can be reconstructed from events alone
- SQLite projections match event ledger state
