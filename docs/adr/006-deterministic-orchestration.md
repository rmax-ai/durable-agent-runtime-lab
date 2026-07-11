# ADR-006: Deterministic orchestration boundary

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

The core design principle (Section 5) states: "The model must be treated as a stochastic proposal generator." The model proposes actions; deterministic application code decides whether to execute them. This boundary is the architecture's central thesis.

Options:
- **Model-driven orchestration:** The model decides state transitions, retry policies, budget enforcement. Flexible but non-deterministic — same input can produce different workflow paths. Makes reproducibility and reliability measurement impossible.
- **Hybrid (model + rules):** Model proposes state transitions, rules validate them. Better, but still gives the model too much control over workflow semantics.
- **Deterministic orchestration:** Every state transition, retry, budget check, and permission enforcement is implemented in normal application code. The model is a pure function: task context in, action proposal out. The orchestrator validates and commits.

**Decision:**

Use **strict deterministic orchestration**. The model may interpret goals, propose plans, propose actions, diagnose failures, suggest revisions, and evaluate qualitative outputs. It must **never** directly control: workflow state transitions, event ordering, retry limits, permission enforcement, budget enforcement, checkpoint creation, task claiming, commit rules, idempotency, rollback execution, sandbox boundaries, or final success status.

The boundary is enforced at the code level: the `ModelProposer` module has no imports from `orchestration/`, `boundary/`, or `persistence/`. It receives a `TaskContext` and returns an `ActionProposal`. The orchestrator owns everything downstream.

**Consequences:**

- **Easier:** Reproducible experiments — same inputs produce same workflow paths. The only non-determinism is the model output, which is captured and can be replayed.
- **Easier:** Testable — the orchestrator can be tested with mock model providers injecting specific proposals.
- **Easier:** Security — permission and budget enforcement can't be bypassed by model prompt injection.
- **Easier:** Debugging — every decision is traceable to a specific line of application code, not a model's opaque reasoning.
- **Harder:** Less flexible — the orchestrator can't adapt to novel situations the model identifies without code changes.
- **Harder:** More code to write — every policy, retry strategy, and validation rule must be implemented explicitly.
