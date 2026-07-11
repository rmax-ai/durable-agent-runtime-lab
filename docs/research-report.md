# DAR v0.2.0 — Baseline vs Durable Runtime Comparison

> **Important:** All numbers in this report are from actual execution of the Durable Agent Runtime Lab. No results are fabricated. See [Statement on Results](#statement-on-fabricating-results).

---

## Hypothesis

The durable runtime — built on event-sourcing, deterministic checkpointing, idempotency tracking, and hash-chained ledger integrity — will match or exceed the baseline runtime's task success rate while providing stronger guarantees around failure recovery, auditability, and tamper evidence.

The baseline runtime serves as the **control condition**: a conventional model→tool→repeat loop with no persistence, no recovery, and no state machine. Any overhead introduced by the durable runtime's additional machinery is expected to be small relative to the cost of model inference.

---

## Experimental Setup

| Parameter | Value |
|-----------|-------|
| **Project** | Durable Agent Runtime Lab v0.2.0 |
| **Repository** | `~/src/durable-agent-runtime-lab` |
| **Executor** | ProcessExecutor (sandboxed subprocess) |
| **Data directory** | `./data/` (event ledgers, state DB, checkpoints, reports) |
| **Workspace** | `./benchmarks/repositories/` (per-task fixture directories) |

---

## Task Descriptions

### Task 01 — Small deterministic refactor
Rename a public function (`compute_tax` → `calculate_tax`) in a single file and update all call sites in the test file.

- **Repository fixture:** `benchmarks/repositories/task-01-refactor/`
- **Complexity:** 1 (single-file change)
- **Success checks:** test pass, file contains new name, file does not contain old name

### Task 02 — Multi-file feature addition
Add a small API endpoint, update the domain model, add tests, and update documentation.

- **Repository fixture:** `benchmarks/repositories/task-02-feature/`
- **Complexity:** 2 (multi-file change)
- **Success checks:** test pass, endpoint returns expected response

### Task 03 — Failing dependency migration
Upgrade a dependency (`pydantic>=1.0` → `pydantic>=2.0`), repair breaking changes (`BaseSettings` → `BaseModel` / `SettingsConfigDict`), run full tests.

- **Repository fixture:** `benchmarks/repositories/task-03-migration/`
- **Complexity:** 2 (breaking change migration)
- **Success checks:** test pass, no references to removed APIs

### Task 04 — Repository-wide config migration
Modify multiple config files (YAML, TOML), preserve invariants (key structure, data types), validate generated output.

- **Repository fixture:** `benchmarks/repositories/task-04-config/`
- **Complexity:** 2 (cross-file consistency)
- **Success checks:** schema validation, key preservation

### Task 05 — Delayed verification task
Make several changes where the final failure only appears during integration tests.

- **Repository fixture:** `benchmarks/repositories/task-05-delayed/`
- **Complexity:** 3 (delayed-failure detection)
- **Success checks:** test pass, no residual breaking changes

### Task 06 — Restart recovery task
Terminate the runtime after a mutating action, restart, verify no duplicate writes, and complete successfully.

- **Repository fixture:** `benchmarks/repositories/task-06-recovery/`
- **Complexity:** 3 (recovery-specific)
- **Success checks:** test pass, idempotent execution, no duplicates

---

## Runtime Configurations

### Baseline Runtime

```python
# Simplified: no persistence, no recovery, no state machine
for iteration in range(max_iterations):
    proposal = model.propose(...)
    result = executor.execute(proposal)
    append_to_conversation(result)
    if result.success and enough_iterations:
        break
```

**Characteristics:**
- No event ledger
- No checkpointing
- No retry or recovery logic
- No budget enforcement
- Single-pass conversation loop
- Process executor only

### Durable Runtime

```python
# Full pipeline: orchestrate → propose → verify → execute → commit
engine = OrchestratorEngine(data_dir)
boundary = BoundaryService(engine.state)
scheduler = TaskScheduler(engine.state, engine)

for epoch until all tasks committed:
    ready = scheduler.promote_pending(wf_id, plan)
    for task in ready:
        proposal = ...                # model proposes
        if boundary.verify(proposal):  # policy check
            result = executor.execute(proposal)
            engine.commit(proposal)     # event ledger append
```

**Characteristics:**
- Event-sourced ledger with hash-chain integrity
- SQLite state projections
- Deterministic checkpointing
- Multi-task DAG scheduler with dependency resolution
- Boundary verification (policy, schema, authorization)
- Idempotency tracking (dedup on re-execution)
- Fault injection system

---

## Provider and Model Versions

| Component | Value |
|-----------|-------|
| **Provider** | MockProvider (deterministic, no API calls) |
| **Model** | `mock/v1` |
| **Token simulation** | ¼ of input length + 50 output tokens per call |
| **Cost simulation** | $0 (MockProvider — no real inference) |

When real providers are used (OpenAI, Anthropic, etc.), version and pricing details will be recorded here.

---

## Fault Configurations

Faults are configured declaratively in `experiments/configs/core.yaml` and injected deterministically by `FaultInjector` (Section 22).

```yaml
faults:
  - type: process_kill
    trigger:
      event_type: action_execution_succeeded
      occurrence: 2
  - type: tool_timeout
    trigger:
      tool_name: run_tests
      occurrence: 1
```

Each fault type maps to a `FaultType` enum:
- `process_kill` — raises `SystemExit(137)` at the configured occurrence
- `model_timeout` — raises `TimeoutError` from the model provider
- `tool_timeout` — reduces executor timeout to 1 second
- `malformed_model_response` — skips the current proposal cycle
- `tool_nonzero_exit`, `transient_filesystem_error`, `corrupted_artifact`, etc.

---

## Sample Sizes

| Parameter | Value |
|-----------|-------|
| **Tasks per experiment** | Configurable (default: 2—6 benchmark tasks) |
| **Repeats per task** | Configurable (default: 3) |
| **Total runs per experiment** | tasks × repeats × 2 runtimes |
| **Minimum for significance** | ≥5 repeats per task per runtime |
| **Seed** | Deterministic — same config → same fault injection points |

---

## Raw Metric Summary

> The following metrics are populated by `dar experiment run` and displayed by `dar experiment report`.

| Task | Runtime | Success | Model Calls | Wall-clock (s) | Est. Cost ($) |
|------|---------|---------|-------------|----------------|---------------|
| task-01 | baseline | ... | ... | ... | $0 |
| task-01 | durable | ... | ... | ... | $0 |
| task-02 | baseline | ... | ... | ... | $0 |
| ... | ... | ... | ... | ... | ... |

**Aggregate:**

| Metric | Baseline | Durable | Delta |
|--------|----------|---------|-------|
| Success rate | ... | ... | ... |
| Mean model calls | ... | ... | ... |
| Mean wall-clock (s) | ... | ... | ... |
| Mean cost ($) | $0 | $0 | $0 |

---

## Comparative Results

### Primary outcome: task success rate

| Runtime | Tasks Succeeded | Tasks Total | Success Rate |
|---------|----------------|-------------|--------------|
| Baseline | ... | ... | ... |
| Durable | ... | ... | ... |

### Secondary outcomes

| Runtime | Mean Model Calls | Mean Wall-clock (s) | Mean Cost ($) |
|---------|-----------------|---------------------|---------------|
| Baseline | ... | ... | $0 |
| Durable | ... | ... | $0 |

### With fault injection

| Runtime | Tasks Succeeded | Tasks Total | Success Rate | Faults Triggered |
|---------|----------------|-------------|--------------|------------------|
| Baseline | ... | ... | ... | ... |
| Durable | ... | ... | ... | ... |

---

## Qualitative Failure Analysis

For each task that failed in either runtime, document:
1. **Task** and **runtime**
2. **Observed symptom** (what went wrong)
3. **Root cause** (architecture vs. implementation vs. configuration)
4. **Workaround** (if any)

| Task | Runtime | Failure | Cause | Workaround |
|------|---------|---------|-------|------------|
| ... | ... | ... | ... | ... |

---

## Cost–Reliability Trade-offs

### Interpretation

The durable runtime adds architectural overhead:
- Event storage (JSONL file I/O per mutation)
- SQLite state projections (DB writes per event)
- Checkpoint serialization
- Boundary verification (additional model calls or policy checks)

In exchange, it provides:
- **Auditability:** full event history with tamper-evident hash chain
- **Recoverability:** deterministic replay from last checkpoint
- **Idempotency:** safe re-execution after crash
- **Multi-task DAG scheduling:** dependency-aware task dispatch

### When the trade-off is favorable

- Long-running workflows (minutes to hours) where a crash would lose progress
- Regulated environments requiring audit trails
- Multi-step tasks where intermediate state must be preserved
- Systems where tamper evidence is a requirement

### When the trade-off may not be worth it

- Very short tasks (seconds) where overhead dominates runtime
- Read-only or stateless tasks
- Environments with no persistence requirements

---

## Threats to Validity

1. **MockProvider limitation.** All results are based on simulated model responses, not real model inference. Real models exhibit stochastic behavior, latency variance, and cost that MockProvider cannot reproduce.
2. **Deterministic fault injection.** Our fault injector fires at exact occurrences, which tests recovery code paths but does not model real-world failure distributions (e.g., Poisson arrival of network errors).
3. **Small sample size.** With 3× repeats per configuration, individual task-level results lack statistical significance. Confidence intervals require ≥10 repeats.
4. **Single repository fixture.** Benchmarks use simplified fixture repositories, not production-scale codebases. Scaling effects (I/O contention, database growth, checkpoint size) are not tested.
5. **No network or resource contention.** All execution is local. Distributed or cloud deployments introduce latency, partial failure, and concurrency issues not covered here.
6. **Process executor only.** Docker sandbox mode is not exercised. Filesystem isolation and network policies may interact with runtime behavior differently.

---

## Implementation Limitations

1. **SQLite projection is single-threaded.** For high-throughput workflows, the state store may become a bottleneck.
2. **No automatic log rotation.** JSONL event files grow unboundedly. Production deployments would need rotation or archival.
3. **Checkpoint size is unbounded.** The full event chain is serialized. For long workflows with many events, checkpoint size grows proportionally.
4. **No distributed consensus.** The runtime is a single-node system. Multi-node deployments would require an external consensus protocol (Raft, etc.).
5. **No circuit breaker.** Persistent failures at a single step can cause infinite retry loops (mitigated by budget limits).
6. **MockProvider replaces all model calls.** The baseline and durable runtimes do not use real model providers in this experiment iteration.

---

## Next Experiments

1. **Real provider comparison.** Replace MockProvider with OpenAI `gpt-4o` and Anthropic `claude-3.5-sonnet` to measure real latency, cost, and success rates.
2. **Fault injection sensitivity.** Vary fault occurrence (occurrence 1, 2, 3, 5, 10) to map recovery success as a function of fault timing.
3. **Scaling benchmark.** Increase task complexity and number of tasks. Measure checkpoint size, event count, and wall-clock overhead.
4. **Docker sandbox comparison.** Repeat with `DockerExecutor` to measure filesystem isolation overhead.
5. **Long-horizon tasks.** Design a task with 50+ model/tool iterations to stress-test event store growth and checkpoint performance.
6. **Mixed fault types.** Combine process kill + tool timeout + malformed response in a single run to simulate complex failure scenarios.

---

## Statement on Fabricating Results

> **All numbers in this report are generated from actual execution of the Durable Agent Runtime Lab software.** The `dar experiment run` command executes real code paths in both runtimes, collects metrics, and persists results as JSON reports. The `dar experiment report` command reads those JSON files and formats them as human-readable Markdown. No numbers, success rates, or metrics are hard-coded, imputed, or fabricated. Any value shown as `...` indicates a placeholder for a future experiment run that has not yet been executed.
>
> To reproduce any result in this report:
> ```bash
> cd ~/src/durable-agent-runtime-lab
> uv run dar experiment run experiments/configs/core.yaml
> uv run dar experiment report
> ```
>
> The raw JSON reports are stored in `data/reports/experiment-<id>.json` and can be inspected directly.
