from pathlib import Path

import pytest

from durable_agent_runtime.cli import _prepare_task_workspace


def test_prepare_task_workspace_copies_fixture_contents(tmp_path: Path) -> None:
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "README.md").write_text("fixture\n")

    workspace = _prepare_task_workspace(
        {"task_id": "task-01", "repository_fixture": str(fixture)},
        data_dir=tmp_path / "data",
        run_label="repeat-1",
    )

    assert workspace.exists()
    assert workspace.is_dir()
    assert (workspace / "README.md").read_text() == "fixture\n"


def test_prepare_task_workspace_requires_fixture(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="missing repository_fixture"):
        _prepare_task_workspace({"task_id": "task-01"}, tmp_path / "data", "repeat-1")
