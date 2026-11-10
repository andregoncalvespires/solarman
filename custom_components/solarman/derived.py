"""Derived (calculated) values for Solarman inverters.

Pure Python, no Home Assistant imports, so it can be unit-tested stand-alone.
"""
from __future__ import annotations

import re

_PV_VOLTAGE = re.compile(r"^PV(\d+) Voltage$")

AC_POWER_NAME = "Total AC Output Power (Active)"
RATED_POWER_NAME = "Rated Power"
LOAD_NAME = "AC Output Load"
PV_TOTAL_NAME = "PV Total Power"


def pv_power_name(n: int) -> str:
    return f"PV{n} Power"


def pv_relative_name(n: int) -> str:
    return f"PV{n} Relative Output"


def _item_names(parameter_definition: dict) -> set[str]:
    return {
        item["name"]
        for group in parameter_definition.get("parameters", [])
        for item in group.get("items", [])
    }


def find_pv_inputs(parameter_definition: dict) -> list[int]:
    """PV input numbers that have both a Voltage and a Current item."""
    names = _item_names(parameter_definition)
    inputs = []
    for name in names:
        match = _PV_VOLTAGE.match(name)
        if match and f"PV{match.group(1)} Current" in names:
            inputs.append(int(match.group(1)))
    return sorted(inputs)


def derived_definitions(parameter_definition: dict, pv_inputs: list[int],
                        monitored: list[int]) -> list[dict]:
    """Sensor definitions (same shape as the yaml items) for derived values.

    Names already provided by the yaml profile are never redefined.
    """
    existing = _item_names(parameter_definition)
    out: list[dict] = []

    def add(item: dict) -> None:
        if item["name"] not in existing:
            out.append({**item, "derived": True})

    for n in pv_inputs:
        add({"name": pv_power_name(n), "class": "power", "state_class": "measurement",
             "uom": "W", "icon": "mdi:solar-power"})
    if pv_inputs:
        add({"name": PV_TOTAL_NAME, "class": "power", "state_class": "measurement",
             "uom": "W", "icon": "mdi:solar-power"})
    if AC_POWER_NAME in existing:
        add({"name": LOAD_NAME, "class": "", "state_class": "measurement",
             "uom": "%", "icon": "mdi:gauge"})
    for n in monitored:
        add({"name": pv_relative_name(n), "class": "", "state_class": "measurement",
             "uom": "%", "icon": "mdi:percent", "diagnostic": True})
    return out


def compute_derived(raw: dict, pv_inputs: list[int], ac_max_power: float | None,
                    connected: bool) -> dict:
    """Derived values for one poll.

    When the inverter is not connected (night / unreachable) powers and load
    are reported as 0 so graphs and energy dashboards stay continuous.
    """
    out: dict = {}
    total = 0.0
    for n in pv_inputs:
        power = None
        if connected:
            volt = raw.get(f"PV{n} Voltage")
            amp = raw.get(f"PV{n} Current")
            if volt is not None and amp is not None:
                power = round(float(volt) * float(amp), 1)
        else:
            power = 0.0
        if power is not None:
            out[pv_power_name(n)] = power
            total += power
    if pv_inputs and (connected or out):
        out[PV_TOTAL_NAME] = round(total, 1)

    if not connected:
        out[LOAD_NAME] = 0.0
    else:
        ac = raw.get(AC_POWER_NAME)
        if ac is not None and ac_max_power and ac_max_power > 0:
            out[LOAD_NAME] = round(float(ac) / float(ac_max_power) * 100, 1)
    return out
