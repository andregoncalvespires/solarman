"""The Solarman Collector integration."""

import logging

from homeassistant.core import HomeAssistant
from homeassistant.config_entries import ConfigEntry

from .const import *
from .inverter_factory import build_inverter
from .services import register_services

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[str] = ["sensor", "binary_sensor"]


def register_services_compat(hass: HomeAssistant, inverter) -> None:
    """Call register_services() in a way that works across integration
    releases: some require register_services(hass, inverter), others only
    accept register_services(hass)."""
    try:
        register_services(hass, inverter)
    except TypeError:
        register_services(hass)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Solarman Collector from a config entry."""
    _LOGGER.debug(f'__init__.py:async_setup_entry({entry.as_dict()})')
    # Building the inverter reads yaml (and may hit the network): keep it
    # off the event loop.
    inverter = await hass.async_add_executor_job(build_inverter, hass, entry.options)
    hass.data.setdefault(DOMAIN, {})[entry.entry_id] = inverter
    register_services_compat(hass, inverter)
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    _LOGGER.debug(f'__init__.py:async_unload_entry({entry.as_dict()})')
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        inverter = hass.data.get(DOMAIN, {}).pop(entry.entry_id, None)
        if inverter is not None:
            await hass.async_add_executor_job(inverter.disconnect_from_server)
    return unload_ok


async def update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Options changed: reload so the new settings take effect."""
    _LOGGER.debug(f'__init__.py:update_listener({entry.as_dict()})')
    await hass.config_entries.async_reload(entry.entry_id)
