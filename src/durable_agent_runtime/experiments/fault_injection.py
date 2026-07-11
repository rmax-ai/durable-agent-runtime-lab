"""Deterministic fault injection subsystem (Section 22).

FaultInjector reads a declarative config and deterministically triggers
faults at configured event/tool occurrence points during a benchmark run.
"""

from __future__ import annotations

from typing import Any

from durable_agent_runtime.domain.enums import FaultType


class FaultInjector:
    """Deterministic fault injection from configuration.

    Tracks occurrence counters per event_type or tool_name across the run.
    Same config + same event sequence = same injection points every run.

    Config format::

        config = {
            "faults": [
                {"type": "process_kill",
                 "trigger": {"event_type": "action_execution_succeeded", "occurrence": 2}},
                {"type": "tool_timeout",
                 "trigger": {"tool_name": "run_tests", "occurrence": 1}},
            ]
        }
    """

    def __init__(self, config: dict[str, Any]) -> None:
        self._faults: list[dict[str, Any]] = list(config.get("faults", []))
        self._validate()
        # Internal occurrence counters per key (event_type or "tool:<tool_name>")
        self._counters: dict[str, int] = {}
        # Track which faults have triggered during the run
        self._triggered: list[dict[str, Any]] = []

    # ── Public API ──────────────────────────────────────────────────────────

    def should_trigger(self, event_type: str, occurrence: int) -> bool:
        """Return True if a fault should trigger at this *event_type* + *occurrence*.

        This is a pure query — it does not mutate internal state.  Use
        :meth:`get_fault` to actually consume (and record) the fault.
        """
        return self._match_event_fault(event_type, occurrence) is not None

    def get_fault(self, event_type: str) -> FaultType | None:
        """Return the fault type to inject for *event_type*, or *None*.

        This method **auto-increments** the internal occurrence counter for
        *event_type* and checks whether any configured fault matches the
        resulting count.  If a match is found the fault is recorded in
        :attr:`triggered_faults` and the fault type is returned.

        Callers must invoke this at the right moment in the runtime loop
        (e.g. once per incoming event, before/after tool execution).
        """
        # Increment counter for this event_type
        self._counters[event_type] = self._counters.get(event_type, 0) + 1
        current = self._counters[event_type]
        return self._match_and_record(event_type, current)

    def get_fault_for_tool(self, tool_name: str) -> FaultType | None:
        """Return the fault type to inject for *tool_name*, or *None*.

        Analogue of :meth:`get_fault` but keyed on tool_name rather than
        event_type.  Used for faults like ``tool_timeout`` that trigger
        on specific tool invocations.
        """
        key = f"tool:{tool_name}"
        self._counters[key] = self._counters.get(key, 0) + 1
        current = self._counters[key]
        match = self._match_tool_fault(tool_name, current)
        if match is not None:
            self._triggered.append(match)
            return FaultType(match["type"])
        return None

    @property
    def triggered_faults(self) -> list[dict[str, Any]]:
        """Faults that have triggered so far during this run (copy)."""
        return list(self._triggered)

    # ── Internal helpers ────────────────────────────────────────────────────

    def _validate(self) -> None:
        known_types = {ft.value for ft in FaultType}
        for fault in self._faults:
            ft = fault.get("type", "")
            if ft not in known_types:
                raise ValueError(f"Unknown fault type: {ft!r}. Valid types: {sorted(known_types)}")
            trigger = fault.get("trigger", {})
            if not trigger:
                raise ValueError(
                    f"Fault {ft!r} has an empty trigger — must specify event_type or tool_name"
                )

    def _match_event_fault(self, event_type: str, occurrence: int) -> dict[str, Any] | None:
        for fault in self._faults:
            trigger = fault.get("trigger", {})
            if trigger.get("event_type") == event_type and trigger.get("occurrence") == occurrence:
                return fault
        return None

    def _match_tool_fault(self, tool_name: str, occurrence: int) -> dict[str, Any] | None:
        for fault in self._faults:
            trigger = fault.get("trigger", {})
            if trigger.get("tool_name") == tool_name and trigger.get("occurrence") == occurrence:
                return fault
        return None

    def _match_and_record(self, event_type: str, occurrence: int) -> FaultType | None:
        match = self._match_event_fault(event_type, occurrence)
        if match is not None:
            self._triggered.append(match)
            return FaultType(match["type"])
        return None
