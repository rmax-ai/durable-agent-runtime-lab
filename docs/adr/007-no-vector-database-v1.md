# ADR-007: No vector database in v1

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

The memory system (Section 6.10) requires three tiers: working memory (active task context), episodic memory (structured events), and procedural/semantic memory (repository instructions, coding standards, tool docs). Vector databases (Chroma, Qdrant, pgvector) are commonly used for semantic retrieval in agent systems.

The spec explicitly states: "Do not implement a vector database initially. Use deterministic retrieval from paths, tags, task IDs, event types, repository manifests, lightweight full-text search. Add vector retrieval only if experiments demonstrate a clear need."

**Decision:**

Use **deterministic retrieval** for all memory tiers in v1.0.

- **Working memory:** Assembled per-task from the task specification, current plan fragment, relevant file content, and applicable policies.
- **Episodic memory:** SQL queries against structured event data — filter by task_id, event_type, causation_id, correlation_id.
- **Procedural/semantic memory:** File-based lookup from repository manifests (AGENTS.md, pyproject.toml, coding standards in docs/), tag-based retrieval, and lightweight full-text search (SQLite FTS5 or `ripgrep`).

No embedding vectors. No cosine similarity. No semantic search.

**Consequences:**

- **Easier:** No operational dependency on a vector database. Everything works from files and SQLite.
- **Easier:** Deterministic behavior — retrieval results are predictable and reproducible.
- **Easier:** Faster iteration — no index building, no embedding API costs during development.
- **Harder:** Less "intelligent" retrieval — the model can't ask "find similar past failures" unless those are tagged or queryable by event type. This is acceptable for v1 benchmark tasks which are small and well-scoped.
- **Harder:** May limit scalability for projects with 1000+ files where codebase-wide search is needed. Mitigation: ripgrep is fast enough for single-repo scale, and FTS5 handles structured text search well.
- **Future:** If experiments show that semantic retrieval meaningfully improves task completion rates, this decision can be revisited. The `memory/` module exposes an interface that a vector-backed implementation can satisfy.
