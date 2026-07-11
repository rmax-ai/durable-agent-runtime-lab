# AGENTS.md — Durable Agent Runtime Lab

## Project Conventions

### Python

- **Version:** Python 3.12+
- **Type system:** Pydantic v2 for domain models, strict mypy for application code
- **Lint/format:** ruff (line-length 100, double quotes)
- **Testing:** pytest + Hypothesis for property-based tests
- **Package manager:** uv
- **Imports:** absolute imports from `durable_agent_runtime.*`

### Architecture Rules

1. **Domain models are canonical.** JSON Schemas are generated from Pydantic models — never maintain manual schemas alongside Python types.
2. **Deterministic code decides.** Models propose; application code validates, schedules, commits, retries, and enforces budgets.
3. **Events are immutable.** The JSONL event ledger is append-only. Hash chaining provides tamper evidence.
4. **State is reconstructable.** SQLite projections are derived from events — events are the source of truth.
5. **No Hermes references in source.** Use `.envrc` + `direnv` for API key injection. This repo must work standalone.

### Code Organization

- `domain/` — canonical Pydantic models, enums, state machines
- `orchestration/` — deterministic workflow engine
- `boundary/` — proposal verification, policy, authorization
- `execution/` — sandboxed tool execution
- `persistence/` — event store, state store, checkpoint store
- `models/` — provider interface and implementations
- `experiments/` — benchmark runner, fault injection, metrics

### Testing Standards

- **Unit tests** cover state transitions, validators, hashing, budgets, retry policies, idempotency, context assembly
- **Property-based tests** cover invariants: event sequence monotonicity, hash tamper detection, committed-action idempotency, terminal state immobility, round-trip preservation
- **Integration tests** cover full task execution with mock providers
- **Recovery tests** verify process termination resilience
- **Security tests** cover path traversal, command injection, secret leakage

### Commit Style

```
type: description

- Conventional Commits: feat, fix, chore, docs, test, refactor
- Reference issues: Closes #N
- Keep commits atomic per milestone/task
```
