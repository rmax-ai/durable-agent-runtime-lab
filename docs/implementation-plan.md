# Implementation Plan — Durable Agent Runtime Lab

> **For Hermes:** Use subagent-driven-development or Codex CLI to implement per-milestone.

**Goal:** Build a research-grade platform comparing conventional model-driven agent loops against typed, deterministic, durable workflows.

**Status:** All 9 milestones complete. 155 tests passing. Both runtimes functional. Experiment runner operational.

**Architecture:** Python 3.12 + Pydantic v2 domain models → JSON Schema → typed pipelines. Deterministic orchestration (state machines, event sourcing, checkpointing) decoupled from stochastic model proposals.

---

## Milestone Status

| Milestone | Status | Tests | Key Artifacts |
|-----------|--------|-------|---------------|
| M0 — Repository Foundation | ✅ Complete | — | pyproject.toml, Makefile, AGENTS.md, 7 ADRs |
| M1 — Canonical Domain Model | ✅ Complete | 112 | 8 Pydantic models, 12 enums, state machines, JSON Schema |
| M2 — Event Ledger & State Machine | ✅ Complete | 28 | JSONL event store, SQLite projections, orchestrator engine |
| M3 — Tool Boundary & Executor | ✅ Complete | 7 | Tool registry, proposal verification, process executor, security |
| M4 — Checkpoints & Recovery | ✅ Complete | — | Git checkpoint manager, recovery replay |
| M5 — Model Providers | ✅ Complete | — | ModelProvider protocol, MockProvider |
| M6 — Full Durable Runtime | ✅ Complete | 4 | End-to-end workflow, proposal→verify→execute→commit cycle |
| M7 — Baseline Runtime | ✅ Complete | 1 | Conventional agent loop, same tools/provider |
| M8 — Experiment Framework | ✅ Complete | 3 | Runner, comparison metrics, JSON report generation |
| M9 — Research Release | ✅ Complete | — | README, docs, architecture diagrams, known limitations |

**Total:** 155 tests (98 unit + 14 property-based + 28 persistence + 12 integration + 3 experiments)

---

## Known Limitations (v0.1.0)

- Mock provider only — real model providers (OpenAI, Anthropic) not yet wired
- Docker executor not yet integrated; process executor used for all execution
- Multi-task DAG scheduling not yet implemented; single-task-per-workflow
- Human approval flow is CLI stubs only
- Fault injection configured but not yet wired into experiment runner
- No real benchmark tasks created (benchmarks/tasks/ directory exists but empty)
