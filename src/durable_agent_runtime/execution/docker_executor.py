"""Docker-based sandbox executor (Section 6.6).

Runs tools in Docker containers with filesystem isolation, network disabled,
and enforced timeouts. Used for production sandboxed execution.
"""

import shlex
import subprocess
from pathlib import Path

from durable_agent_runtime.execution.tool_registry import ToolContext, ToolResult


class DockerExecutor:
    """Execute commands in Docker containers with filesystem isolation.

    Each execution spins up a fresh container with:
    - Network disabled (``--network none``)
    - Workspace mounted read-only at ``/workspace``
    - Output directory mounted writable at ``/output``
    - A Python-based timeout via ``subprocess.run(timeout=...)``
    """

    def __init__(self, image: str = "python:3.12-slim") -> None:
        self._image = image
        self._docker_available: bool | None = None

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_docker_available(self) -> bool:
        """Probe whether the ``docker`` CLI is functional on this system.

        Results are cached per-instance so repeated calls are cheap.
        """
        if self._docker_available is not None:
            return self._docker_available
        try:
            result = subprocess.run(
                ["docker", "info"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            self._docker_available = result.returncode == 0
        except (FileNotFoundError, subprocess.TimeoutExpired, Exception):
            self._docker_available = False
        return self._docker_available

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def execute(self, command: list[str], context: ToolContext) -> ToolResult:
        """Run *command* inside a disposable Docker container.

        Parameters
        ----------
        command:
            The command to run, expressed as a list of arguments (e.g.
            ``["echo", "hello"]``).
        context:
            Sandbox configuration including workspace root, timeout, and
            output size limits.

        Returns
        -------
        ToolResult
            Always returned — errors (including Docker being unavailable)
            are communicated through ``ToolResult.success`` / ``ToolResult.error``.
        """
        if not self._check_docker_available():
            return ToolResult(success=False, error="Docker not available")

        workspace = Path(context.workspace_root).resolve()
        output_dir = workspace / "output"

        # Ensure the output directory exists on the host so Docker's
        # bind mount doesn't fail.
        output_dir.mkdir(parents=True, exist_ok=True)

        # Build a single shell command that cd's into the workspace and
        # then runs the requested command.
        shell_cmd = f"cd /workspace && {shlex.join(command)}"

        docker_cmd = [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "-v",
            f"{workspace}:/workspace:ro",
            "-v",
            f"{output_dir}:/output:rw",
            self._image,
            "sh",
            "-c",
            shell_cmd,
        ]

        try:
            result = subprocess.run(
                docker_cmd,
                capture_output=True,
                text=True,
                timeout=context.timeout_seconds,
            )

            stdout = result.stdout[: context.max_output_bytes]
            stderr = result.stderr[: context.max_output_bytes]

            return ToolResult(
                success=(result.returncode == 0),
                output=stdout,
                exit_code=result.returncode,
                error=stderr if result.returncode != 0 else "",
            )
        except subprocess.TimeoutExpired:
            return ToolResult(
                success=False,
                exit_code=-1,
                error=f"Command timed out after {context.timeout_seconds}s",
            )
        except Exception as e:
            return ToolResult(success=False, exit_code=-1, error=str(e))
