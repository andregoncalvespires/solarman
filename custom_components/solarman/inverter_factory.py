"""Builds the Inverter object from a config entry's options (blocking)."""
import os

import voluptuous as vol

from .const import *
from .scanner import InverterScanner
from .solarman import Inverter

_inverter_scanner = InverterScanner()


def build_inverter(hass, config) -> Inverter:
    """Reads the lookup yaml and may hit the network via InverterScanner:
    call from an executor thread, never from the event loop."""
    inverter_host = config.get(CONF_INVERTER_HOST)
    if inverter_host == "0.0.0.0":
        inverter_host = _inverter_scanner.get_ipaddress()

    inverter_port = config.get(CONF_INVERTER_PORT)
    inverter_sn = config.get(CONF_INVERTER_SERIAL)
    if inverter_sn == 0:
        inverter_sn = _inverter_scanner.get_serialno()

    inverter_mb_slaveid = config.get(CONF_INVERTER_MB_SLAVEID)
    if not inverter_mb_slaveid:
        inverter_mb_slaveid = DEFAULT_INVERTER_MB_SLAVEID
    lookup_file = config.get(CONF_LOOKUP_FILE)
    # relative to this file, so it works wherever the integration is installed
    path = os.path.join(os.path.dirname(__file__), 'inverter_definitions') + os.sep
    use_sun = config.get(CONF_USE_SUN, DEFAULT_USE_SUN)
    sun_elevation_threshold = config.get(CONF_SUN_ELEVATION_THRESHOLD, DEFAULT_SUN_ELEVATION_THRESHOLD)

    # Check input configuration.
    if inverter_host is None:
        raise vol.Invalid('configuration parameter [inverter_host] does not have a value')
    if inverter_sn is None:
        raise vol.Invalid('configuration parameter [inverter_serial] does not have a value')

    return Inverter(path, inverter_sn, inverter_host, inverter_port, inverter_mb_slaveid, lookup_file,
                    hass=hass, use_sun=use_sun, sun_elevation_threshold=sun_elevation_threshold,
                    options=config)
