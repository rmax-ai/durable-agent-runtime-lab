"""Tests for deterministic fault injection (Phase 6, Section 22)."""

import pytest

from durable_agent_runtime.domain.enums import FaultType
from durable_agent_runtime.experiments.fault_injection import FaultInjector


class TestFaultInjectorConstruction:
    """FaultInjector creation and validation."""

    def test_empty_config_no_faults(self) -> None:
        injector = FaultInjector({"faults": []})
        assert injector.triggered_faults == []

    def test_empty_config_dict_no_faults(self) -> None:
        injector = FaultInjector({})
        assert injector.triggered_faults == []

    def test_unknown_fault_type_raises(self) -> None:
        config = {
            "faults": [
                {"type": "nonexistent_fault", "trigger": {"event_type": "test", "occurrence": 1}},
            ]
        }
        with pytest.raises(ValueError, match="Unknown fault type"):
            FaultInjector(config)

    def test_empty_trigger_raises(self) -> None:
        config = {
            "faults": [
                {"type": "process_kill", "trigger": {}},
            ]
        }
        with pytest.raises(ValueError, match="empty trigger"):
            FaultInjector(config)


class TestDeterministicTriggering:
    """Fault injection fires at the correct occurrence every time."""

    def test_single_fault_fires_at_correct_occurrence(self) -> None:
        config = {
            "faults": [
                {
                    "type": "process_kill",
                    "trigger": {"event_type": "action_execution_succeeded", "occurrence": 2},
                },
            ]
        }
        injector = FaultInjector(config)

        # Occurrence 1 — should NOT trigger
        assert injector.should_trigger("action_execution_succeeded", 1) is False
        assert injector.get_fault("action_execution_succeeded") is None

        # Occurrence 2 — SHOULD trigger
        assert injector.should_trigger("action_execution_succeeded", 2) is True
        ft = injector.get_fault("action_execution_succeeded")
        assert ft == FaultType.PROCESS_KILL

    def test_get_fault_tracks_counter_correctly(self) -> None:
        """get_fault auto-increments and returns the fault at the right count."""
        config = {
            "faults": [
                {
                    "type": "tool_timeout",
                    "trigger": {"event_type": "action_execution_started", "occurrence": 3},
                },
            ]
        }
        injector = FaultInjector(config)

        # First two calls — no fault
        assert injector.get_fault("action_execution_started") is None
        assert injector.get_fault("action_execution_started") is None

        # Third call — fault triggers
        ft = injector.get_fault("action_execution_started")
        assert ft == FaultType.TOOL_TIMEOUT

        # Fourth call — back to no fault
        assert injector.get_fault("action_execution_started") is None

    def test_no_trigger_below_threshold(self) -> None:
        """Faults don't fire before the configured occurrence."""
        config = {
            "faults": [
                {
                    "type": "model_timeout",
                    "trigger": {"event_type": "action_proposed", "occurrence": 5},
                },
            ]
        }
        injector = FaultInjector(config)

        for i in range(1, 5):
            result = injector.get_fault("action_proposed")
            assert result is None, f"Fault triggered unexpectedly at occurrence {i}"

    def test_deterministic_same_config_same_result(self) -> None:
        """Two injectors with the same config produce the same trigger sequence."""
        config = {
            "faults": [
                {
                    "type": "process_kill",
                    "trigger": {"event_type": "task_claimed", "occurrence": 1},
                },
            ]
        }

        for _ in range(3):
            injector = FaultInjector(config)
            assert injector.get_fault("task_claimed") == FaultType.PROCESS_KILL
            assert injector.get_fault("task_claimed") is None


class TestMultipleFaults:
    """Multiple faults in the same configuration."""

    def test_multiple_faults_different_event_types(self) -> None:
        config = {
            "faults": [
                {
                    "type": "process_kill",
                    "trigger": {"event_type": "workflow_created", "occurrence": 1},
                },
                {
                    "type": "tool_timeout",
                    "trigger": {"event_type": "action_execution_started", "occurrence": 2},
                },
            ]
        }
        injector = FaultInjector(config)

        # First trigger: process_kill on workflow_created
        ft1 = injector.get_fault("workflow_created")
        assert ft1 == FaultType.PROCESS_KILL

        # action_execution_started occurrences
        ft2 = injector.get_fault("action_execution_started")
        assert ft2 is None  # occurrence 1 — no trigger

        ft3 = injector.get_fault("action_execution_started")
        assert ft3 == FaultType.TOOL_TIMEOUT  # occurrence 2 — trigger

    def test_multiple_faults_same_event_type(self) -> None:
        """Two faults on the same event_type at different occurrences."""
        config = {
            "faults": [
                {
                    "type": "model_timeout",
                    "trigger": {"event_type": "action_proposed", "occurrence": 1},
                },
                {
                    "type": "malformed_model_response",
                    "trigger": {"event_type": "action_proposed", "occurrence": 3},
                },
            ]
        }
        injector = FaultInjector(config)

        # Occurrence 1: model_timeout
        assert injector.get_fault("action_proposed") == FaultType.MODEL_TIMEOUT

        # Occurrence 2: no fault
        assert injector.get_fault("action_proposed") is None

        # Occurrence 3: malformed_model_response
        assert injector.get_fault("action_proposed") == FaultType.MALFORMED_MODEL_RESPONSE


class TestToolFaults:
    """Faults keyed on tool_name rather than event_type."""

    def test_tool_based_fault_triggers_correctly(self) -> None:
        config = {
            "faults": [
                {
                    "type": "tool_timeout",
                    "trigger": {"tool_name": "run_tests", "occurrence": 1},
                },
            ]
        }
        injector = FaultInjector(config)

        ft = injector.get_fault_for_tool("run_tests")
        assert ft == FaultType.TOOL_TIMEOUT

    def test_tool_based_fault_tracks_counter(self) -> None:
        config = {
            "faults": [
                {
                    "type": "tool_timeout",
                    "trigger": {"tool_name": "run_tests", "occurrence": 2},
                },
            ]
        }
        injector = FaultInjector(config)

        assert injector.get_fault_for_tool("run_tests") is None  # occurrence 1
        assert injector.get_fault_for_tool("run_tests") == FaultType.TOOL_TIMEOUT  # occurrence 2

    def test_tool_fault_ignores_other_tools(self) -> None:
        config = {
            "faults": [
                {
                    "type": "tool_timeout",
                    "trigger": {"tool_name": "run_tests", "occurrence": 1},
                },
            ]
        }
        injector = FaultInjector(config)

        # Different tool — no trigger
        assert injector.get_fault_for_tool("deploy") is None
        # Target tool — triggers
        assert injector.get_fault_for_tool("run_tests") == FaultType.TOOL_TIMEOUT


class TestMixedEventAndToolFaults:
    """Event-type and tool-name faults in the same config."""

    def test_event_and_tool_faults_independent(self) -> None:
        config = {
            "faults": [
                {
                    "type": "process_kill",
                    "trigger": {"event_type": "workflow_created", "occurrence": 1},
                },
                {
                    "type": "tool_timeout",
                    "trigger": {"tool_name": "run_tests", "occurrence": 2},
                },
            ]
        }
        injector = FaultInjector(config)

        # Event fault triggers independently of tool counters
        assert injector.get_fault("workflow_created") == FaultType.PROCESS_KILL

        # Tool fault has its own counter
        assert injector.get_fault_for_tool("run_tests") is None  # tool occurrence 1
        assert injector.get_fault_for_tool("run_tests") == FaultType.TOOL_TIMEOUT  # tool occ 2


class TestTriggeredFaultsTracking:
    """The injector records which faults have triggered."""

    def test_triggered_faults_empty_initially(self) -> None:
        injector = FaultInjector(
            {"faults": [{"type": "process_kill", "trigger": {"event_type": "x", "occurrence": 1}}]}
        )
        assert injector.triggered_faults == []

    def test_triggered_faults_records_after_fire(self) -> None:
        config = {
            "faults": [
                {"type": "process_kill", "trigger": {"event_type": "test_event", "occurrence": 1}},
            ]
        }
        injector = FaultInjector(config)
        injector.get_fault("test_event")
        assert len(injector.triggered_faults) == 1
        assert injector.triggered_faults[0]["type"] == "process_kill"

    def test_triggered_faults_with_multiple_fires(self) -> None:
        config = {
            "faults": [
                {"type": "process_kill", "trigger": {"event_type": "evt_a", "occurrence": 1}},
                {"type": "tool_timeout", "trigger": {"event_type": "evt_b", "occurrence": 2}},
            ]
        }
        injector = FaultInjector(config)
        injector.get_fault("evt_a")
        injector.get_fault("evt_b")  # occurrence 1 — no trigger
        injector.get_fault("evt_b")  # occurrence 2 — trigger

        assert len(injector.triggered_faults) == 2

    def test_triggered_faults_isolated_tool_and_event(self) -> None:
        config = {
            "faults": [
                {"type": "process_kill", "trigger": {"event_type": "evt", "occurrence": 1}},
                {"type": "tool_timeout", "trigger": {"tool_name": "tool_x", "occurrence": 1}},
            ]
        }
        injector = FaultInjector(config)
        injector.get_fault("evt")
        injector.get_fault_for_tool("tool_x")
        assert len(injector.triggered_faults) == 2


class TestShouldTrigger:
    """should_trigger is a pure query that doesn't mutate state."""

    def test_should_trigger_does_not_mutate(self) -> None:
        config = {
            "faults": [
                {
                    "type": "model_timeout",
                    "trigger": {"event_type": "call_model", "occurrence": 3},
                },
            ]
        }
        injector = FaultInjector(config)

        # Calling should_trigger doesn't advance the counter or record faults
        assert injector.should_trigger("call_model", 3) is True
        assert injector.triggered_faults == []
        # get_fault still returns the fault because should_trigger didn't consume it
        assert injector.get_fault("call_model") is None  # occurrence 1
        assert injector.get_fault("call_model") is None  # occurrence 2
        assert injector.get_fault("call_model") == FaultType.MODEL_TIMEOUT  # occurrence 3
