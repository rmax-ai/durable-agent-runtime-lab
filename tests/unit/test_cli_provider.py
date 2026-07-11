from __future__ import annotations

import json
import os
from pathlib import Path

from typer.testing import CliRunner

from durable_agent_runtime import cli
from durable_agent_runtime.cli import app

runner = CliRunner()


def test_resolve_provider_name_prefers_cli_override() -> None:
    config = {"provider": "mock"}
    assert cli._resolve_experiment_provider_name(config, "openai") == "openai"


def test_resolve_provider_name_falls_back_to_config() -> None:
    config = {"provider": "openai"}
    assert cli._resolve_experiment_provider_name(config, "") == "openai"


def test_resolve_model_name_uses_provider_default_for_openai() -> None:
    assert cli._resolve_experiment_model_name({}, "openai", "") == "gpt-5.4-mini"


def test_resolve_model_name_prefers_cli_override() -> None:
    config = {"model": "gpt-4o-mini"}
    assert cli._resolve_experiment_model_name(config, "openai", "gpt-5") == "gpt-5"


def test_build_model_provider_uses_explicit_model(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    provider = cli._build_model_provider("openai", "gpt-4o-mini")
    assert provider is not None
    assert provider.model == "gpt-4o-mini"


def test_build_model_provider_requires_api_key(monkeypatch) -> None:
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    try:
        cli._build_model_provider("openai", "gpt-5.4-mini")
    except ValueError as exc:
        assert "OPENAI_API_KEY" in str(exc)
    else:
        raise AssertionError("Expected ValueError for missing API key")


def test_experiment_command_passes_provider_and_model(monkeypatch) -> None:
    captured: dict[str, str] = {}

    def fake_run(config_path: str, provider_name: str, model_name: str) -> None:
        captured["config_path"] = config_path
        captured["provider_name"] = provider_name
        captured["model_name"] = model_name

    monkeypatch.setattr(cli, "_cmd_experiment_run", fake_run)
    result = runner.invoke(
        app,
        [
            "experiment",
            "run",
            "--config",
            "experiments/configs/core.yaml",
            "--provider",
            "openai",
            "--model",
            "gpt-4o-mini",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "config_path": "experiments/configs/core.yaml",
        "provider_name": "openai",
        "model_name": "gpt-4o-mini",
    }


def test_cmd_experiment_run_uses_config_provider(monkeypatch, tmp_path: Path) -> None:
    captured: dict[str, object] = {}

    class FakeRunner:
        def __init__(self, data_dir: Path, workspace: Path, provider=None) -> None:
            captured["data_dir"] = data_dir
            captured["workspace"] = workspace
            captured["provider"] = provider

        def run_comparison(self, goal, faults=None):
            captured["goal"] = goal
            captured["faults"] = faults
            return {
                "metrics": {"baseline_success": True, "durable_success": True},
                "experiment_id": "abc12345",
                "baseline": {"success": True},
                "durable": {"success": True},
            }

        def save_report(self, results):
            path = tmp_path / "data" / "reports" / "experiment-abc12345.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("{}")
            return path

    class FakeProvider:
        def __init__(self, api_key: str, model: str) -> None:
            self.api_key = api_key
            self.model = model

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("OPENAI_API_KEY", "env-key")
    monkeypatch.setattr(cli, "_get_data_dir", lambda: tmp_path / "data")
    monkeypatch.setattr(
        cli,
        "_load_experiment_config",
        lambda _path: {
            "name": "config-driven",
            "tasks": ["benchmarks/tasks/task-01.yaml"],
            "repeats": 1,
            "faults": [],
            "provider": "openai",
            "model": "gpt-4o-mini",
        },
    )
    monkeypatch.setattr(
        cli,
        "_load_task_yaml",
        lambda _path: {
            "task_id": "task-01",
            "name": "Task 01",
            "goal": "Run fixture task",
            "repository_fixture": str(tmp_path / "fixture"),
        },
    )
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    (fixture / "README.md").write_text("fixture\n")
    monkeypatch.setattr(cli, "ExperimentRunner", FakeRunner, raising=False)
    monkeypatch.setattr(
        "durable_agent_runtime.experiments.runner.ExperimentRunner",
        FakeRunner,
    )
    monkeypatch.setattr(
        "durable_agent_runtime.models.openai_provider.OpenAIProvider",
        FakeProvider,
    )

    cli._cmd_experiment_run("experiments/configs/core.yaml")

    provider = captured["provider"]
    assert provider is not None
    assert provider.model == "gpt-4o-mini"
    assert provider.api_key == "env-key"
    assert str(captured["workspace"]).endswith("data/runs/task-01/repeat-1/repo")


def test_experiment_report_picks_latest_report_by_mtime(monkeypatch, tmp_path: Path) -> None:
    reports_dir = tmp_path / "data" / "reports"
    reports_dir.mkdir(parents=True)

    older = reports_dir / "experiment-zzzz0000.json"
    newer = reports_dir / "experiment-00000001.json"

    older.write_text(json.dumps({"experiment_id": "zzzz0000", "timestamp": "older"}))
    newer.write_text(json.dumps({"experiment_id": "00000001", "timestamp": "newer"}))

    os.utime(older, (100, 100))
    os.utime(newer, (200, 200))

    monkeypatch.setattr(cli, "_get_data_dir", lambda: tmp_path / "data")

    result = runner.invoke(app, ["experiment", "report"])

    assert result.exit_code == 0
    assert f"Using latest report: {newer}" in result.stdout
    assert "# Experiment Report: 00000001" in result.stdout


def test_experiment_report_renders_provider_and_model(monkeypatch, tmp_path: Path) -> None:
    reports_dir = tmp_path / "data" / "reports"
    reports_dir.mkdir(parents=True)

    report_path = reports_dir / "experiment-35c937f1.json"
    report_path.write_text(
        json.dumps(
            {
                "experiment_id": "35c937f1",
                "timestamp": "2026-07-12T10:00:00Z",
                "goal": "Quickstart",
                "provider": "openai",
                "model": "gpt-5.4-mini",
                "baseline": {"wall_clock_time": 1.2},
                "durable": {"wall_clock_time": 1.4, "model_calls": 1},
                "metrics": {
                    "baseline_success": True,
                    "durable_success": True,
                    "baseline_model_calls": 1,
                    "speedup": 0.86,
                },
            }
        )
    )

    monkeypatch.setattr(cli, "_get_data_dir", lambda: tmp_path / "data")

    result = runner.invoke(app, ["experiment", "report"])

    assert result.exit_code == 0
    assert "- **Provider:** openai" in result.stdout
    assert "- **Model:** gpt-5.4-mini" in result.stdout
    assert "live inference behavior" in result.stdout
