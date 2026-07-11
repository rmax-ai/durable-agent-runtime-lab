# ADR-003: JSONL append-only event ledger

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

Every meaningful state transition must create an immutable event (Section 6.8). Options for the event store:

- **Database events table (SQLite):** Simple to query, supports transactions. But: mutable by SQL UPDATE/DELETE, harder to prove immutability, mixes mutable projections with immutable source of truth.
- **Kafka / Redpanda:** Production-grade distributed log. Overkill for single-node research. Adds operational complexity.
- **JSONL (JSON Lines):** One JSON object per line. Append-only by design (open in append mode, never seek backward to overwrite). Human-readable with `tail`/`jq`. Trivially archiveable. Hash-chaining provides tamper evidence.

**Decision:**

Use **JSONL (JSON Lines)** for the canonical append-only event ledger.

Each event is a single JSON object on one line. Events are written in append-only mode (`open(path, "a")`). Hash chaining (SHA-256 of previous event + current payload) provides tamper-evident integrity — any modification to any event in the chain is detectable by verifying the hash chain from the last event backward.

Replay is a linear forward scan of the JSONL file. State reconstruction filters events by workflow_id and applies them in sequence order.

**Consequences:**

- **Easier:** Human-inspectable — `tail -f events.jsonl | jq .` during development.
- **Easier:** Archivable — a single `.jsonl` file is the complete event history.
- **Easier:** Append-only guarantee — no SQL UPDATE path to accidentally mutate events.
- **Easier:** Hash chain verification — `verify-ledger` command replays and recomputes hashes.
- **Harder:** No random access by event ID without an index. Solution: SQLite projections provide indexed query access. The JSONL is the source of truth; SQLite is a read-optimized cache.
- **Harder:** High-write-throughput scenarios would create large files. Acceptable for research workloads (hundreds to low thousands of events per workflow).
