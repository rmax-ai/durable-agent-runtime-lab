# ADR-001: SQLite + JSONL for local state

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

The Durable Agent Runtime needs persistent storage for workflow state, task state, events, checkpoints, and budget tracking. This is a research platform designed to run on a single machine or VPS — not a distributed system in v1. Options considered:

- **PostgreSQL:** Overkill for single-node research. Adds operational complexity (install, configure, backup) with no research benefit.
- **Temporal:** Powerful but heavyweight. Spec explicitly says "Do not introduce Temporal in the first implementation." Evaluation of Temporal belongs in a future milestone.
- **SQLite:** Zero-configuration, embedded, file-based. Sufficient for single-node workloads. Excellent for research reproducibility (single file can be archived with experiment data).
- **JSONL:** Append-only, human-readable, trivially inspectable with `tail`/`jq`. Perfect for immutable event logs where the primary operations are append and sequential scan.

**Decision:**

Use **SQLite** (via SQLAlchemy/SQLModel) for mutable state projections and **JSONL** for the append-only event ledger.

- SQLite stores: workflow state projections, task states, budget counters, checkpoint metadata, idempotency records
- JSONL stores: the canonical append-only event log with hash chaining

State is always reconstructable from events. SQLite projections are a performance optimization, not the source of truth.

**Consequences:**

- **Easier:** Reproducible experiments — a single directory contains the event log, SQLite DB, and Git repo. No external services.
- **Easier:** Human-inspectable — JSONL files are readable with standard tools. SQLite is queryable with `sqlite3`.
- **Easier:** Zero operational overhead for researchers.
- **Harder:** Scaling to multi-node deployments later would require migration (swap SQLite for PostgreSQL, JSONL for Kafka/compatible log). But the persistence interfaces (`EventStore`, `StateStore`) abstract the backend — migration is an implementation detail.
- **Harder:** Concurrent writers are limited (SQLite single-writer). Acceptable for v1 single-workflow-per-process model.
