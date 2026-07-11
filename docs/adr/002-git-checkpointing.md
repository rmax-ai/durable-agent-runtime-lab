# ADR-002: Git-based checkpointing

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

The runtime must survive forced process termination and resume from a valid state. Checkpoint strategies considered:

- **Filesystem snapshots (tar/rsync):** Simple but coarse. Doesn't capture incremental changes or provide history.
- **Distributed snapshots (e.g., Chandy-Lamport):** Overkill for single-node. Requires coordination between components.
- **Git commits:** The workspace IS a Git repository. Using Git as the checkpoint mechanism gives us: atomic commits, immutable history, diff inspection, branch isolation, and rollback to any previous commit. Every developer already has Git installed.

**Decision:**

Use **Git** as the canonical workspace checkpoint mechanism.

Before a mutating task: record the current commit. After successful postcondition verification: stage only intended files, create an atomic commit, record the commit hash in the event ledger. On failure: reset to the previous checkpoint commit.

Checkpoints in the domain model (`Checkpoint` in `checkpoint.py`) reference the Git commit SHA, not a full filesystem snapshot. Artifact storage (logs, model outputs) is separate and referenced by artifact IDs.

**Consequences:**

- **Easier:** No new infrastructure — Git is a hard requirement already.
- **Easier:** Human-debuggable — `git log`, `git diff`, `git show` work on checkpoint history.
- **Easier:** Branch isolation for parallel experiments.
- **Easier:** Rollback is a single `git reset --hard <commit>`.
- **Harder:** Large binary artifacts can't live in Git efficiently. Solution: artifacts stored separately, referenced by hash.
- **Harder:** Concurrent workflows modifying the same repo need branch isolation. Single-workflow-per-process model avoids this for v1.
- **Harder:** Force-push protection must be explicit. The orchestrator must never automatically force-push or modify remote branches.
