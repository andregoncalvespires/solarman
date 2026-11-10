"""Smoke test of the full integration against a fake data logger.

Needs pytest-homeassistant-custom-component (installed in CI).
"""
from datetime import timedelta
from unittest.mock import patch

import pytest

pytest.importorskip("pytest_homeassistant_custom_component")

from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import State
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
    mock_restore_cache,
)

import custom_components.solarman.solarman as solarman_module

DOMAIN = "solarman"


@pytest.fixture(autouse=True)
def _enable(enable_custom_integrations):
    yield


def fake_registers():
    regs = [0] * 0x7D                      # request range 0x0001..0x007D
    def put(addr, value):
        regs[addr - 1] = value
    for n, (volt, amp) in enumerate([(365, 82), (360, 80), (0, 0), (362, 81)]):
        put(0x6D + 2 * n, volt)            # PVn voltage (x0.1 V)
        put(0x6E + 2 * n, amp)             # PVn current (x0.1 A)
    put(0x10, 21200)                       # Rated Power (x0.1 W) -> 2120 W
    put(0x56, 10600)                       # AC power low word (x0.1 W) -> 1060 W
    put(0x3B, 2)                           # Normal
    put(0x3F, 1000)                        # Total Production (validation min)
    return regs


def entry():
    return MockConfigEntry(domain=DOMAIN, title="inv", options={
        "name": "Solarman Teste", "inverter_host": "192.0.2.10", "inverter_port": 8899,
        "inverter_serial": 1234567890, "inverter_mb_slaveid": 1,
        "lookup_file": "deye_4mppt.yaml", "use_sun_for_polling": False,
    })


async def test_setup_poll_reload_unload(hass):
    regs = fake_registers()
    with patch.object(solarman_module, "PySolarmanV5") as modbus:
        modbus.return_value.read_holding_registers.side_effect = (
            lambda register_addr, quantity: regs[register_addr - 1: register_addr - 1 + quantity])
        config_entry = entry()
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        async_fire_time_changed(hass, dt_util.utcnow() + timedelta(seconds=90))
        await hass.async_block_till_done(wait_background_tasks=True)

        assert hass.states.get("sensor.solarman_teste_pv1_power").state == "299.3"
        assert hass.states.get("sensor.solarman_teste_pv3_power").state == "0.0"
        assert float(hass.states.get("sensor.solarman_teste_pv_total_power").state) > 0
        assert hass.states.get("sensor.solarman_teste_ac_output_load").state == "50.0"
        problem = hass.states.get("binary_sensor.solarman_teste_pv_problem")
        assert problem is not None and problem.state == "off"

        # Changing options reloads the entry (used to raise KeyError before)
        hass.config_entries.async_update_entry(
            config_entry, options={**config_entry.options, "pv_problem_minutes": 45})
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


async def test_problem_state_is_restored_after_restart(hass):
    mock_restore_cache(hass, [State(
        "binary_sensor.solarman_teste_pv_problem", "on",
        {"problem_modules": ["PV3"], "problem_since": {"PV3": "2026-08-26T14:00:00+00:00"}})])
    with patch.object(solarman_module, "PySolarmanV5"):
        config_entry = entry()
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.solarman_teste_pv_problem")
    assert state.state == "on"
    assert state.attributes["problem_modules"] == ["PV3"]
    assert state.attributes["problem_since"]["PV3"].startswith("2026-08-26T14:00")
