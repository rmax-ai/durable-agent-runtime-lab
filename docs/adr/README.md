# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the Durable Agent Runtime Lab project.

Each ADR documents a significant architectural decision: the context, the options considered, the decision made, and the consequences.

## ADR Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](adr/001-sqlite-jsonl-local-state.md) | SQLite + JSONL for local state | Accepted |
| [ADR-002](adr/002-git-checkpointing.md) | Git-based checkpointing | Accepted |
| [ADR-003](adr/003-jsonl-event-ledger.md) | JSONL append-only event ledger | Accepted |
| [ADR-004](adr/004-provider-neutral-model-interface.md) | Provider-neutral model interface | Accepted |
| [ADR-005](adr/005-docker-sandboxing.md) | Docker sandboxing with process fallback | Accepted |
| [ADR-006](adr/006-deterministic-orchestration.md) | Deterministic orchestration boundary | Accepted |
| [ADR-007](adr/007-no-vector-database-v1.md) | No vector database in v1 | Accepted |

## ADR Template

```markdown
# ADR-NNN: Title

**Status:** Proposed | Accepted | Deprecated | Superseded

**Date:** YYYY-MM-DD

**Context:**

What is the issue that we're seeing that is motivating this decision?

**Decision:**

What is the change that we're proposing and/or doing?

**Consequences:**

What becomes easier or more difficult to do because of this change?
```
