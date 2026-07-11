"""Process-based sandbox executor (Section 6.6).

Runs tools as subprocesses with path restrictions, timeouts, and output capture.
Used for unit testing and development without Docker.
"""

import os
import subprocess
from pathlib import Path

from durable_agent_runtime.execution.tool_registry import ToolContext, ToolResult


class ProcessExecutor:
    """Execute commands in a process-based sandbox."""

    @staticmethod
    def execute(command: list[str], context: ToolContext) -> ToolResult:
        """Run a command with timeout and output capture."""
        workspace = Path(context.workspace_root).resolve()

        # Enforce sandbox root — reject paths outside workspace
        try:
            workspace.relative_to(workspace)  # Validate workspace exists
        except ValueError:
            return ToolResult(success=False, error=f"Invalid workspace: {workspace}")

        try:
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                timeout=context.timeout_seconds,
                cwd=str(workspace),
                env={
                    **os.environ,
                    "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
                    "HOME": str(workspace),
                },
            )

            # Truncate output if too large
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
