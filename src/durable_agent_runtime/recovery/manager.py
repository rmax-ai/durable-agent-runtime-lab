"""Git-based checkpoint manager (Section 6.9, ADR-002).

Uses Git commits as canonical workspace checkpoints. Records commit SHA
in checkpoint events. Supports rollback via git reset.
"""

import subprocess
from pathlib import Path
from uuid import UUID

from durable_agent_runtime.domain import Checkpoint
from durable_agent_runtime.domain.enums import WorkflowStatus
from durable_agent_runtime.persistence.event_store import EventStore


class GitCheckpointManager:
    """Manages Git-based checkpoints for workflow recovery."""

    def __init__(self, repo_path: Path, event_store: EventStore) -> None:
        self.repo_path = Path(repo_path).resolve()
        self.events = event_store

    def _git(self, *args: str) -> str:
        """Run a git command in the repo."""
        result = subprocess.run(
            ["git", "-C", str(self.repo_path), *list(args)],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return result.stdout.strip()

    def current_commit(self) -> str:
        """Get the current HEAD commit SHA."""
        return self._git("rev-parse", "HEAD")

    def is_clean(self) -> bool:
        """Check if the working tree is clean."""
        return self._git("status", "--porcelain") == ""

    def create_checkpoint(
        self,
        workflow_id: UUID,
        workflow_status: WorkflowStatus,
        last_event_sequence: int,
        tokens_used: int = 0,
        model_calls: int = 0,
        tool_calls: int = 0,
        estimated_cost: float = 0.0,
    ) -> Checkpoint:
        """Create a new checkpoint recording the current Git commit."""
        commit = self.current_commit()
        branch = self._git("rev-parse", "--abbrev-ref", "HEAD")

        checkpoint = Checkpoint(
            workflow_id=workflow_id,
            sequence=last_event_sequence,
            git_commit=commit,
            git_branch=branch,
            workflow_status=workflow_status,
            last_event_sequence=last_event_sequence,
            tokens_used=tokens_used,
            model_calls=model_calls,
            tool_calls=tool_calls,
            estimated_cost=estimated_cost,
        )
        return checkpoint

    def stage_and_commit(self, message: str, paths: list[str] | None = None) -> str:
        """Stage files and create a commit. Returns commit SHA."""
        if paths:
            self._git("add", *paths)
        else:
            self._git("add", "-A")
        self._git("commit", "-m", message)
        return self.current_commit()

    def rollback_to(self, commit: str) -> None:
        """Hard reset to a previous commit."""
        self._git("reset", "--hard", commit)

    def rollback_to_checkpoint(self, checkpoint: Checkpoint) -> None:
        """Reset the repository to a checkpoint's commit."""
        self.rollback_to(checkpoint.git_commit)
