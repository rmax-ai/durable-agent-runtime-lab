"""Integration tests for the Docker sandbox executor.

All tests in this module carry the ``@pytest.mark.docker`` marker so they
are only run when explicitly requested (``uv run pytest -m docker``) or
in CI environments that have Docker installed.
"""

import subprocess

import pytest

from durable_agent_runtime.execution.docker_executor import DockerExecutor
from durable_agent_runtime.execution.tool_registry import ToolContext

# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _docker_available() -> bool:
    """Return ``True`` if the ``docker`` CLI is reachable and responsive."""
    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
        return False


# ------------------------------------------------------------------
# Tests
# ------------------------------------------------------------------


@pytest.mark.docker
def test_docker_echo_succeeds() -> None:
    """A trivial echo command should succeed inside the Docker container."""
    if not _docker_available():
        pytest.skip("Docker is not available on this system")

    executor = DockerExecutor()
    context = ToolContext(workspace_root="/tmp")
    result = executor.execute(["echo", "hello from docker"], context)

    assert result.success, f"Expected success, got error: {result.error}"
    assert "hello from docker" in result.output


@pytest.mark.docker
def test_timeout_enforced() -> None:
    """A command that sleeps longer than the timeout should be killed."""
    if not _docker_available():
        pytest.skip("Docker is not available on this system")

    executor = DockerExecutor()
    context = ToolContext(workspace_root="/tmp", timeout_seconds=1)
    result = executor.execute(["sleep", "10"], context)

    assert not result.success
    assert "timed out" in result.error.lower()


@pytest.mark.docker
def test_graceful_error_when_docker_missing() -> None:
    """When Docker is unavailable the executor must not crash."""
    executor = DockerExecutor()
    # Bypass the real availability check so we test the error path
    executor._docker_available = False  # type: ignore[assignment]

    context = ToolContext(workspace_root="/tmp")
    result = executor.execute(["echo", "test"], context)

    assert not result.success
    assert result.error == "Docker not available"
