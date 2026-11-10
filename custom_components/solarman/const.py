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

# --- Derived sensors / PV module monitoring ---
# AC capacity used for "AC Output Load". 0 = use the inverter's "Rated Power" register.
CONF_AC_MAX_POWER = 'ac_max_power'
CONF_PV_MONITOR = 'pv_monitor'
CONF_PV_MONITORED_INPUTS = 'pv_monitored_inputs'
CONF_PV_PROBLEM_THRESHOLD = 'pv_problem_threshold'
CONF_PV_PROBLEM_MINUTES = 'pv_problem_minutes'
CONF_PV_MIN_POWER = 'pv_min_power'
CONF_PV_MIN_SUN_ELEVATION = 'pv_min_sun_elevation'
DEFAULT_AC_MAX_POWER = 0
DEFAULT_PV_MONITOR = True
DEFAULT_PV_MONITORED_INPUTS = ['1', '2', '3', '4']
DEFAULT_PV_PROBLEM_THRESHOLD = 50   # % of the other modules' median output
DEFAULT_PV_PROBLEM_MINUTES = 30     # minutes of valid samples below threshold
DEFAULT_PV_MIN_POWER = 50           # W the reference must reach to evaluate
DEFAULT_PV_MIN_SUN_ELEVATION = 15.0  # degrees
PV_RECOVERY_MINUTES = 10

SENSOR_PREFIX = 'Solarman'
