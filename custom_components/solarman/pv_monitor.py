"""Detect a PV module that produces much less than its siblings.

Pure Python, no Home Assistant imports.

Each monitored input is compared against the *median of the other inputs*
(clouds hit all modules alike, so the ratio stays ~100 %). A module is flagged
when its ratio stays below `threshold` for `on_seconds` of *valid* time, and
cleared when it stays above the recovery level for `off_seconds` of valid time.
Time only advances on valid samples (inverter connected, sun high enough,
enough reference power), so nights and dark mornings pause the clocks instead
of resetting them.
"""
from __future__ import annotations

from statistics import median

MIN_MONITORED_INPUTS = 3   # needed to tell *which* module is the odd one out
MAX_STEP_SECONDS = 120     # longer gaps (restart, outage) are not counted
OPEN_CIRCUIT_VOLTAGE = 5.0  # V
NO_CURRENT = 0.05           # A

HINT_OPEN_CIRCUIT = "open_circuit_suspected"      # ~0 V: connector / cable / panel
HINT_NO_CURRENT = "voltage_without_current"       # voltage present, no current: input / MPPT
HINT_LOW_OUTPUT = "low_output"


class PVBalanceMonitor:
    def __init__(self, inputs: list[int], threshold: float = 0.5,
                 recovery: float | None = None, on_seconds: float = 1800,
                 off_seconds: float = 600, min_power: float = 50.0,
                 min_elevation: float = 15.0):
        self.inputs = sorted(set(inputs))
        self.threshold = threshold
        self.recovery = min(0.95, threshold + 0.2) if recovery is None else recovery
        self.on_seconds = on_seconds
        self.off_seconds = off_seconds
        self.min_power = min_power
        self.min_elevation = min_elevation

        self.problem: dict[int, bool] = {n: False for n in self.inputs}
        self.since: dict[int, float] = {}
        self.ratios: dict[int, float | None] = {n: None for n in self.inputs}
        self.hints: dict[int, str] = {}
        self._bad: dict[int, float] = {n: 0.0 for n in self.inputs}
        self._good: dict[int, float] = {n: 0.0 for n in self.inputs}
        self._last_ts: float | None = None

    @property
    def enabled(self) -> bool:
        return len(self.inputs) >= MIN_MONITORED_INPUTS

    @property
    def problem_modules(self) -> list[int]:
        return [n for n in self.inputs if self.problem[n]]

    @property
    def has_problem(self) -> bool:
        return any(self.problem.values())

    def restore(self, modules: list[int], since: dict[int, float] | None = None) -> None:
        """Re-apply a previously saved problem state (after a restart)."""
        for n in modules:
            if n in self.problem:
                self.problem[n] = True
                if since and n in since:
                    self.since[n] = since[n]

    def update(self, now: float, powers: dict[int, float], elevation: float | None,
               connected: bool, readings: dict[int, tuple[float, float]] | None = None) -> None:
        """Feed one sample. `now` is epoch seconds; `readings` is {n: (V, A)}."""
        if not self.enabled:
            return
        step = 0.0 if self._last_ts is None else min(max(now - self._last_ts, 0.0), MAX_STEP_SECONDS)
        self._last_ts = now

        sun_ok = elevation is None or elevation >= self.min_elevation
        have_all = all(n in powers for n in self.inputs)
        if not (connected and sun_ok and have_all):
            self.ratios = {n: None for n in self.inputs}
            return

        for n in self.inputs:
            ref = median([powers[j] for j in self.inputs if j != n])
            if ref < self.min_power:
                self.ratios[n] = None
                continue
            ratio = powers[n] / ref
            self.ratios[n] = ratio

            if not self.problem[n]:
                if ratio < self.threshold:
                    self._bad[n] += step
                elif ratio >= self.recovery:
                    self._bad[n] = 0.0
                if self._bad[n] >= self.on_seconds:
                    self.problem[n] = True
                    self.since[n] = now - self._bad[n]
                    self._good[n] = 0.0
            else:
                if ratio >= self.recovery:
                    self._good[n] += step
                    if self._good[n] >= self.off_seconds:
                        self.problem[n] = False
                        self.since.pop(n, None)
                        self.hints.pop(n, None)
                        self._bad[n] = 0.0
                        self._good[n] = 0.0
                else:
                    self._good[n] = 0.0

            if self.problem[n]:
                self.hints[n] = self._hint(n, (readings or {}).get(n))

    @staticmethod
    def _hint(n: int, reading: tuple[float, float] | None) -> str:
        if reading is None:
            return HINT_LOW_OUTPUT
        volt, amp = reading
        if volt < OPEN_CIRCUIT_VOLTAGE:
            return HINT_OPEN_CIRCUIT
        if amp < NO_CURRENT:
            return HINT_NO_CURRENT
        return HINT_LOW_OUTPUT
