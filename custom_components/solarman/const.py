from datetime import timedelta
import os

DOMAIN = 'solarman'

DEFAULT_PORT_INVERTER = 8899
DEFAULT_INVERTER_MB_SLAVEID = 1
DEFAULT_LOOKUP_FILE = 'deye_hybrid.yaml'

LOOKUP_FILES = (sorted([f for f in os.listdir(os.path.dirname(__file__) + '/inverter_definitions') if f.endswith('.yaml')]))


MIN_TIME_BETWEEN_UPDATES = timedelta(seconds=15)

CONF_INVERTER_HOST = 'inverter_host'
CONF_INVERTER_PORT = 'inverter_port'
CONF_INVERTER_SERIAL = 'inverter_serial'
CONF_INVERTER_MB_SLAVEID = 'inverter_mb_slaveid'
CONF_LOOKUP_FILE = 'lookup_file'

# --- Sun-aware polling ---
# Skip Modbus queries while the sun is below the configured elevation so the
# integration stops hammering (and warning about) a data-logger that is
# powered off overnight, and resumes automatically once HA's sun.sun entity
# reports the elevation is back above the threshold.
CONF_USE_SUN = 'use_sun_for_polling'
CONF_SUN_ELEVATION_THRESHOLD = 'sun_elevation_threshold'
DEFAULT_USE_SUN = True
# A few degrees below the geometric horizon: PV strings/loggers usually pick
# up enough diffuse light to power on a little before actual sunrise and
# stay up a little after sunset, so 0° would clip real data at the edges.
DEFAULT_SUN_ELEVATION_THRESHOLD = -4.0

SENSOR_PREFIX = 'Solarman'
