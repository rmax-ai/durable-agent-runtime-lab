# ADR-005: Docker sandboxing with process fallback

**Status:** Accepted

**Date:** 2026-07-11

**Context:**

Tool execution must be sandboxed to prevent host system writes, restrict file paths, enforce timeouts, and control network access (Section 6.6). Options:

- **Process-level isolation (subprocess):** Simple, fast, no external dependency. But: no filesystem isolation, no network restriction, no resource limits beyond timeouts.
- **Docker containers:** Full filesystem isolation via volume mounts, network disablement, CPU/memory limits. Industry standard. But: requires Docker daemon, slower startup, heavier dependency for CI.
- **Firecracker / gVisor:** Stronger isolation (microVM). Overkill for v1 research platform.
- **Custom seccomp/chroot:** Fragile, platform-specific, hard to maintain.

**Decision:**

Use **Docker** as the primary sandbox implementation with a **process-based test backend**.

The `Executor` interface abstracts the backend:

```python
class Executor(Protocol):
    async def execute(self, command: list[str], context: ExecutionContext) -> ExecutionResult:
        ...
```

Two implementations:
1. `DockerExecutor` — uses Docker SDK or controlled CLI. Mounts workspace as read-only volume, output as writable. Network disabled by default. Enforces timeouts and resource limits.
2. `ProcessExecutor` — runs commands as subprocesses in a temporary directory. No filesystem isolation, but fast and works in CI without Docker. Used for unit tests and development.

The `SandboxMode` enum (`PROCESS` / `DOCKER`) selects the backend at runtime.

**Consequences:**

- **Easier:** Tests run without Docker via `ProcessExecutor` (marked `@pytest.mark.docker` for Docker-only tests).
- **Easier:** Interface abstraction supports future backends (Firecracker, gVisor) without changing core orchestration code.
- **Easier:** Development loop is fast (process mode avoids Docker startup overhead).
- **Harder:** Security guarantees differ between backends. Process mode provides no filesystem isolation — acceptable for trusted development environments, not for untrusted code execution.
- **Harder:** Docker image maintenance. The spec doesn't require custom images initially — standard Python images with workspace mounts suffice.
