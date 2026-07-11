# DAR v0.2.0 — Phase 2 Implementation Plan

> **For Hermes:** Use subagent-driven-development or Codex CLI. Independent phases run in parallel. Sequential phases follow the dependency graph below.

**Goal:** Upgrade from v0.1.0 research scaffold to v0.2.0 — a runnable experimental platform that can execute benchmark tasks with real models, sandboxed execution, multi-task DAG scheduling, and produce comparative experiment reports.

**Status:** Planning — not yet executing.

**Architecture:** The existing codebase has the domain models, orchestrator, event store, and experiment runner. This plan adds the three missing runtime capabilities (real models, Docker sandbox, multi-task scheduling), completes CLI stubs (human approval, fault injection), creates benchmark tasks per the spec (Section 21), and runs the first comparative experiment.

---

## Dependency Graph

```
Phase 1 (Real Providers) ──┐
Phase 2 (Docker Executor) ──┤
Phase 3 (Multi-Task DAG)  ──┼── PARALLEL (no cross-deps)
Phase 4 (Human Approval)  ──┘
          │
          ▼
Phase 5 (Benchmark Tasks) ─── depends on 1+2+3 (needs models, sandbox, multi-task)
          │
          ▼
Phase 6 (Fault Injection Wiring) ─── depends on 5 (needs benchmarks to inject faults into)
          │
          ▼
Phase 7 (Experiment Runs + Report) ─── depends on 5+6
```

### Critical Path

```
Phase 1 (longest: ~60 min for OpenAI adapter + tests)
  → Phase 5 → Phase 6 → Phase 7

Total estimated wall-clock: ~3-4 hours (sequential) or ~1.5 hours (parallel Phases 1-4)
```

---

## Phase Dependency Table

| Phase | Depends On | Can Run Parallel With | Est. Time | Est. Files |
|-------|-----------|----------------------|-----------|------------|
| 1 — Real Providers | — (existing protocol) | 2, 3, 4 | 60 min | 4 |
| 2 — Docker Executor | — (existing interface) | 1, 3, 4 | 30 min | 3 |
| 3 — Multi-Task DAG | — (existing orchestrator) | 1, 2, 4 | 45 min | 3 |
| 4 — Human Approval | — (existing orchestrator + CLI) | 1, 2, 3 | 20 min | 2 |
| 5 — Benchmark Tasks | 1, 2, 3 | — | 45 min | 10+ |
| 6 — Fault Injection | 5 | — | 30 min | 3 |
| 7 — Experiment Runs | 5, 6 | — | 30 min | 3 |

---

## Acceptance Criteria (v0.2.0)

- [ ] `dar run --runtime durable --task benchmarks/tasks/task-01.yaml` completes using OpenAI
- [ ] `dar run --runtime baseline --task benchmarks/tasks/task-01.yaml` completes using OpenAI
- [ ] `dar experiment run experiments/configs/core.yaml` produces a comparative report
- [ ] Docker sandbox executes tools with filesystem isolation and network disabled
- [ ] Multi-task DAG: tasks with unmet dependencies stay PENDING; ready tasks are dispatched in order
- [ ] `dar approve <wf-id> <proposal-id>` transitions workflow from PAUSED → RUNNING
- [ ] Fault injection triggers at configured event occurrence and is logged
- [ ] `dar verify-ledger <wf-id>` detects tampered events
- [ ] Benchmark tasks 1-6 all have YAML definitions, repository fixtures, and success checks
- [ ] Experiment report includes: success rates, model calls, tokens, wall-clock time, cost estimates

---

## Phase 1: Real Model Providers

**Dependencies:** None. The `ModelProvider` Protocol exists in `src/durable_agent_runtime/models/base.py`. The `MockProvider` is implemented and tested. This phase adds a real OpenAI-compatible provider.

**Files:**
- Create: `src/durable_agent_runtime/models/openai_provider.py`
- Create: `tests/unit/test_openai_provider.py`
- Modify: `src/durable_agent_runtime/models/__init__.py` (re-export)
- Create: `src/durable_agent_runtime/models/router.py` (cost-aware routing per Section 6.11)

### Task 1.1: OpenAI provider adapter

**Objective:** Implement `OpenAIProvider` that satisfies the `ModelProvider` Protocol.

**Files:**
- Create: `src/durable_agent_runtime/models/openai_provider.py`
- Create: `tests/unit/test_openai_provider.py`

```python
# openai_provider.py
class OpenAIProvider:
    """OpenAI-compatible provider using httpx (no openai SDK dependency)."""
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1", model: str = "gpt-4o"):
        ...
    async def generate_structured(self, request: ModelRequest, response_model: type[BaseModel]) -> ModelResponse:
        # POST to {base_url}/chat/completions with response_format json_schema
        # Parse, validate against response_model, return ModelResponse
        ...
```

**Acceptance criteria:**
- [ ] `OpenAIProvider` implements the `ModelProvider` Protocol
- [ ] Mock HTTPX transport test verifies request/response shape
- [ ] Structured output is validated against the Pydantic `response_model`
- [ ] `ModelResponse` includes token counts reported by the API
- [ ] API key loaded from env var `OPENAI_API_KEY` (no Hermes refs in source)

### Task 1.2: Model router

**Objective:** Implement cost-aware routing between advisor/planner/worker model classes (Section 6.11).

**Files:**
- Create: `src/durable_agent_runtime/models/router.py`
- Create: `tests/unit/test_model_router.py`

```python
# router.py
class ModelRouter:
    """Routes tasks to model classes by role: advisor, planner, worker."""
    def __init__(self, advisor: ModelProvider, planner: ModelProvider, worker: ModelProvider):
        ...
    def get_provider(self, role: str) -> ModelProvider: ...
```

**Acceptance criteria:**
- [ ] Three provider slots: advisor, planner, worker
- [ ] Same underlying provider can fill all three roles
- [ ] Router selects correct provider by role string
- [ ] Unknown role raises typed error

### Task 1.3: Wire provider into experiment runner

**Objective:** Update `ExperimentRunner` and both runtimes to accept a `ModelProvider` instead of always using `MockProvider`.

**Files:**
- Modify: `src/durable_agent_runtime/experiments/durable.py` — accept provider in constructor
- Modify: `src/durable_agent_runtime/experiments/baseline.py` — accept provider in constructor
- Modify: `src/durable_agent_runtime/experiments/runner.py` — pass provider through

**Acceptance criteria:**
- [ ] `DurableRuntime(provider=OpenAIProvider(...))` works
- [ ] `BaselineRuntime(provider=OpenAIProvider(...))` works
- [ ] `ExperimentRunner` accepts optional provider for both runtimes
- [ ] Default (no provider) falls back to `MockProvider`

---

## Phase 2: Docker Executor

**Dependencies:** None. The execution interface exists. Process executor is implemented. Add Docker sandbox.

**Files:**
- Create: `src/durable_agent_runtime/execution/docker_executor.py`
- Create: `tests/integration/test_docker_executor.py` (marked `@pytest.mark.docker`)
- Modify: `src/durable_agent_runtime/execution/__init__.py`

### Task 2.1: Docker sandbox executor

```python
# docker_executor.py
class DockerExecutor:
    """Execute commands in Docker containers with filesystem isolation."""
    def __init__(self, image: str = "python:3.12-slim"):
        ...
    def execute(self, command: list[str], context: ToolContext) -> ToolResult:
        # docker run --rm --network none -v workspace:/workspace:ro ...
        ...
```

**Acceptance criteria:**
- [ ] Docker container runs with network disabled (`--network none`)
- [ ] Workspace mounted read-only, output directory mounted writable
- [ ] Timeout enforced via `docker run --timeout`
- [ ] stdout/stderr captured and returned
- [ ] Docker unavailable → graceful error, not crash
- [ ] Tests marked `@pytest.mark.docker` and skipped in CI without Docker

### Task 2.2: Sandbox mode selection

**Objective:** `ToolContext.sandbox_mode` selects process vs docker executor at runtime.

**Files:**
- Modify: `src/durable_agent_runtime/execution/tool_registry.py` — add executor factory
- Create: `tests/unit/test_sandbox_selection.py`

---

## Phase 3: Multi-Task DAG Scheduler

**Dependencies:** None. Existing orchestrator engine handles single-task workflows. This adds dependency-aware scheduling.

**Files:**
- Create: `src/durable_agent_runtime/orchestration/scheduler.py`
- Create: `tests/unit/test_scheduler.py`
- Modify: `src/durable_agent_runtime/experiments/durable.py` — use scheduler

### Task 3.1: Dependency resolver

```python
# scheduler.py
class TaskScheduler:
    """Selects READY tasks from a Plan DAG based on dependency satisfaction."""
    def __init__(self, state_store: StateStore):
        ...
    def get_ready(self, workflow_id: UUID, plan: Plan) -> list[UUID]:
        # A task is READY when all its dependencies are COMMITTED
        ...
    def promote_pending(self, workflow_id: UUID, plan: Plan) -> int:
        # Transition PENDING → READY for tasks whose deps are all COMMITTED
        # Returns count of promoted tasks
        ...
```

**Acceptance criteria:**
- [ ] Task with no dependencies → immediately READY
- [ ] Task with unmet dependency → stays PENDING
- [ ] When dependency COMMITTED → task transitions to READY
- [ ] Circular dependencies detected and rejected
- [ ] Tasks with FAILED dependencies → transition to BLOCKED

### Task 3.2: Wire into durable runtime

**Objective:** `DurableRuntime.run_goal()` handles multi-task plans. Loop: get ready tasks → dispatch → wait → promote pending → repeat until all done or failed.

**Files:**
- Modify: `src/durable_agent_runtime/experiments/durable.py`

### Task 3.3: Multi-task integration test

**Files:**
- Create: `tests/integration/test_multi_task_dag.py`

**Acceptance criteria:**
- [ ] 3-task plan with chain topology (A → B → C) executes in order
- [ ] 4-task plan with diamond topology (A → B,C → D) executes A, then B+C parallel, then D
- [ ] Task with FAILED dependency → sibling unblocked, failed task stays FAILED

---

## Phase 4: Human Approval Flow

**Dependencies:** Existing orchestrator (pause/resume transitions), existing CLI stubs.

**Files:**
- Modify: `src/durable_agent_runtime/orchestration/engine.py` — add approval methods
- Modify: `src/durable_agent_runtime/cli.py` — implement `approve` and `reject` commands
- Create: `tests/integration/test_human_approval.py`

### Task 4.1: Approval methods on orchestrator

```python
# engine.py additions
def request_approval(self, workflow_id: UUID, proposal_id: UUID, reason: str) -> None:
    # Transition RUNNING → PAUSED, emit HUMAN_APPROVAL_REQUESTED event
    ...

def approve(self, workflow_id: UUID, proposal_id: UUID) -> None:
    # Transition PAUSED → RUNNING (if paused for this proposal)
    ...

def reject(self, workflow_id: UUID, proposal_id: UUID, reason: str) -> None:
    # Transition PAUSED → RUNNING with rejection logged
    ...
```

**Acceptance criteria:**
- [ ] `request_approval` emits `HUMAN_APPROVAL_REQUESTED` event
- [ ] `approve` emits `HUMAN_APPROVAL_RECEIVED`, transitions PAUSED → RUNNING
- [ ] `reject` logs rejection reason, transitions back to RUNNING
- [ ] Approving a non-paused workflow raises error
- [ ] Rejecting a non-pending approval raises error

### Task 4.2: CLI commands

```bash
dar approve <workflow-id> <proposal-id>
dar reject <workflow-id> <proposal-id> --reason "..."
```

**Acceptance criteria:**
- [ ] `dar approve` works when workflow is PAUSED with matching proposal
- [ ] `dar reject` logs rejection and resumes workflow
- [ ] Both commands accept `--output json` for machine readability

---

## Phase 5: Benchmark Tasks

**Dependencies:** Phases 1 (real models), 2 (Docker executor), 3 (multi-task DAG). Needs functional runtimes to validate benchmarks against.

**Files:** Create 6 benchmark task directories per Section 21 spec.

### Task 5.1: Task 01 — Small deterministic refactor

```
benchmarks/tasks/task-01.yaml
benchmarks/repositories/task-01-refactor/
benchmarks/expected-results/task-01/
```

**Spec (Section 21):** Rename a public function, update all call sites, preserve behavior, run tests.

### Task 5.2: Task 02 — Multi-file feature addition

Add a small API endpoint, update domain model, add tests, update documentation.

### Task 5.3: Task 03 — Failing dependency migration

Upgrade a dependency, repair breaking changes, run full tests.

### Task 5.4: Task 04 — Repository-wide config migration

Modify multiple config files, preserve invariants, validate generated output.

### Task 5.5: Task 05 — Delayed verification task

Make several changes, final failure appears only during integration tests.

### Task 5.6: Task 06 — Restart recovery task

Terminate runtime after mutating action, restart, verify no duplicate writes, complete successfully.

**Each task YAML must include:**
```yaml
task_id: task-01
name: Small deterministic refactor
description: ...
repository_fixture: benchmarks/repositories/task-01-refactor/
goal: "Rename function X to Y and update all call sites"
expected_files: [...]
forbidden_changes: [...]
success_checks:
  - type: test_pass
    command: pytest tests/
  - type: file_exists
    path: src/new_name.py
fault_injection_points: [...]
complexity: 1
```

---

## Phase 6: Fault Injection Wiring

**Dependencies:** Phase 5 (needs benchmark tasks to inject faults into). Fault injection types defined in `domain/enums.py` (FaultType). Not yet wired into experiment runner.

**Files:**
- Create: `src/durable_agent_runtime/experiments/fault_injection.py`
- Modify: `src/durable_agent_runtime/experiments/runner.py`
- Create: `tests/unit/test_fault_injection.py`

### Task 6.1: Fault injector

```python
# fault_injection.py
class FaultInjector:
    """Deterministic fault injection from configuration (Section 22)."""
    def __init__(self, config: dict): ...
    def should_trigger(self, event_type: str, occurrence: int) -> bool: ...
    def get_fault(self, event_type: str) -> FaultType | None: ...
```

**Acceptance criteria:**
- [ ] `process_kill` trigger after Nth occurrence of specified event type
- [ ] `model_timeout` causes provider to raise TimeoutError
- [ ] `tool_timeout` causes executor to return timeout result
- [ ] `malformed_model_response` injects invalid JSON
- [ ] Fault configuration is deterministic (same config → same injection points)

### Task 6.2: Wire into experiment runner

**Acceptance criteria:**
- [ ] `ExperimentRunner.run_comparison()` accepts optional fault config
- [ ] Faults are applied to both runtimes during comparison
- [ ] Report includes fault injection summary (which faults triggered, where)

---

## Phase 7: Experiment Runs & Research Report

**Dependencies:** Phases 5 (benchmarks) + 6 (fault injection). The final deliverable.

**Files:**
- Create: `experiments/configs/core.yaml` — master experiment config
- Modify: `src/durable_agent_runtime/cli.py` — implement `dar experiment run/report`
- Create: `docs/research-report.md` — template

### Task 7.1: Experiment config

```yaml
# experiments/configs/core.yaml
experiment:
  name: "DAR v0.2.0 — Baseline vs Durable"
  runtimes: [baseline, durable]
  tasks: [task-01, task-02, task-03, task-04, task-05, task-06]
  repeats: 3
  provider: openai
  model: gpt-4o
  faults:
    - type: process_kill
      trigger: { event_type: ACTION_EXECUTION_SUCCEEDED, occurrence: 2 }
```

### Task 7.2: CLI experiment commands

```bash
dar experiment run experiments/configs/core.yaml
dar experiment report <experiment-id> --format markdown
```

**Acceptance criteria:**
- [ ] `dar experiment run` executes all tasks against both runtimes
- [ ] `dar experiment report` generates Markdown with tables
- [ ] `--output json` produces machine-readable report

### Task 7.3: Research report template

**Acceptance criteria:**
- [ ] Report includes: hypothesis, setup, task descriptions, runtime configs, provider/model versions, sample sizes, raw metrics, comparative results, cost-reliability trade-offs, threats to validity, limitations
- [ ] All numbers generated from actual execution, never fabricated
- [ ] Report distinguishes: observed results, architectural interpretation, speculative implications

---

## GitHub Issue Structure

| Issue | Title | Labels | Depends On |
|-------|-------|--------|------------|
| Epic #2 | [Epic] DAR v0.2.0 — Runnable Experimental Platform | `epic,status:ready` | #1 |
| #3 | Phase 1: Real model providers (OpenAI adapter + router) | `story,phase:2.1,status:ready` | — |
| #4 | Phase 2: Docker sandbox executor | `story,phase:2.2,status:ready` | — |
| #5 | Phase 3: Multi-task DAG scheduler | `story,phase:2.3,status:ready` | — |
| #6 | Phase 4: Human approval flow | `story,phase:2.4,status:ready` | — |
| #7 | Phase 5: 6 benchmark tasks | `story,phase:2.5,status:backlog` | #3, #4, #5 |
| #8 | Phase 6: Fault injection wiring | `story,phase:2.6,status:backlog` | #7 |
| #9 | Phase 7: Experiment runs + research report | `story,phase:2.7,status:backlog` | #7, #8 |

### Parallel Execution Order

```
Wave 1 (parallel — no deps):  #3, #4, #5, #6
Wave 2 (sequential):           #7 (after #3+#4+#5)
Wave 3 (sequential):           #8 (after #7)
Wave 4 (sequential):           #9 (after #7+#8)
```

---

## Verification Checklist (per-phase)

After each phase commit, run:

```bash
cd ~/src/durable-agent-runtime-lab
uv run ruff format src/ tests/ && uv run ruff check src/ tests/
uv run pytest tests/ -q
git diff --stat  # verify only expected files changed
```

## Total Scope Estimate

| Metric | Count |
|--------|-------|
| New source files | ~15 |
| Modified source files | ~8 |
| New test files | ~10 |
| Benchmark task files | ~12 (YAML + repos + expected) |
| Estimated new tests | ~40-50 |
| Total test target | ~200 tests |
| Estimated wall-clock | ~3-4 hours sequential, ~1.5 hours with parallel dispatch |
