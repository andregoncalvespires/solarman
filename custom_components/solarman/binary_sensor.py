"""Binary sensor: a PV module produces much less than its siblings."""
import logging
from datetime import datetime, timezone

from homeassistant.components.binary_sensor import BinarySensorDeviceClass, BinarySensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_NAME, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from .const import *

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback):
    inverter = hass.data[DOMAIN][entry.entry_id]
    if inverter.pv_monitor.enabled:
        async_add_entities([SolarmanPVProblem(entry.options.get(CONF_NAME), inverter)])


class SolarmanPVProblem(BinarySensorEntity, RestoreEntity):
    """On while at least one monitored PV module is out of balance.

    Attributes tell which module(s) (`problem_modules`), since when, a coarse
    cause hint and the current relative output of every monitored module.
    """

    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_should_poll = True

    def __init__(self, inverter_name, inverter):
        self._inverter_name = inverter_name
        self._inverter = inverter
        self._sn = inverter.serial

    @property
    def name(self):
        return f"{self._inverter_name} PV Problem"

    @property
    def unique_id(self):
        return f"{self._inverter_name}_{self._sn}_pv_problem"

    @property
    def icon(self):
        return "mdi:solar-panel-large" if not self.is_on else "mdi:alert-circle"

    @property
    def device_info(self):
        return {
            "identifiers": {(DOMAIN, self._sn)},
            "name": self._inverter_name,
            "model": self._inverter.lookup_file,
        }

    @property
    def is_on(self):
        return self._inverter.pv_monitor.has_problem

    @property
    def extra_state_attributes(self):
        monitor = self._inverter.pv_monitor
        return {
            "problem_modules": [f"PV{n}" for n in monitor.problem_modules],
            "problem_since": {
                f"PV{n}": datetime.fromtimestamp(monitor.since[n], timezone.utc).isoformat()
                for n in monitor.problem_modules if n in monitor.since
            },
            "hint": {f"PV{n}": monitor.hints[n] for n in monitor.problem_modules if n in monitor.hints},
            "relative_output": {
                f"PV{n}": round(monitor.ratios[n] * 100, 1)
                for n in monitor.inputs if monitor.ratios.get(n) is not None
            },
            "monitored_inputs": [f"PV{n}" for n in monitor.inputs],
        }

    def update(self):
        self._inverter.update()

    async def async_added_to_hass(self):
        await super().async_added_to_hass()
        last = await self.async_get_last_state()
        if last is None or last.state != STATE_ON:
            return
        try:
            modules = [int(m[2:]) for m in last.attributes.get("problem_modules", [])]
            since = {}
            for key, iso in (last.attributes.get("problem_since") or {}).items():
                since[int(key[2:])] = datetime.fromisoformat(iso).timestamp()
            self._inverter.pv_monitor.restore(modules, since)
        except (TypeError, ValueError) as err:
            _LOGGER.debug(f"Could not restore PV problem state: {err}")
