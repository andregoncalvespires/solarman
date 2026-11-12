import socket
import threading
import yaml
import logging
import struct
import time
from homeassistant.util import Throttle
from datetime import datetime
from .parser import ParameterParser
from .derived import (RATED_POWER_NAME, compute_derived, derived_definitions,
                      find_pv_inputs, pv_power_name)
from .pv_monitor import MIN_MONITORED_INPUTS, PVBalanceMonitor
from .const import *
from pysolarmanv5 import PySolarmanV5


log = logging.getLogger(__name__)

QUERY_RETRY_ATTEMPTS = 2

class Inverter:
    def __init__(self, path, serial, host, port, mb_slaveid, lookup_file, hass=None,
                 use_sun=DEFAULT_USE_SUN, sun_elevation_threshold=DEFAULT_SUN_ELEVATION_THRESHOLD,
                 options=None):
        self._modbus = None
        self._serial = serial
        self.path = path
        self._host = host
        self._port = port
        self._mb_slaveid = mb_slaveid
        self._current_val = None
        self._status_connection = -1
        self.status_lastUpdate = "N/A"
        self.lookup_file = lookup_file
        self.lock = threading.Lock()
        self.hass = hass
        self.use_sun = use_sun
        self.sun_elevation_threshold = sun_elevation_threshold

        if not self.lookup_file or lookup_file == 'parameters.yaml':
            self.lookup_file = 'deye_hybrid.yaml'

        with open(self.path + self.lookup_file) as f:
            self.parameter_definition = yaml.full_load(f)

        # --- derived values and PV module monitoring ---
        options = options or {}
        self._ac_max_power_option = float(options.get(CONF_AC_MAX_POWER, DEFAULT_AC_MAX_POWER) or 0)
        self._rated_power_seen = None
        self.pv_inputs = find_pv_inputs(self.parameter_definition)
        monitored = []
        if options.get(CONF_PV_MONITOR, DEFAULT_PV_MONITOR):
            wanted = {int(n) for n in options.get(CONF_PV_MONITORED_INPUTS, DEFAULT_PV_MONITORED_INPUTS)}
            monitored = [n for n in self.pv_inputs if n in wanted]
        threshold = float(options.get(CONF_PV_PROBLEM_THRESHOLD, DEFAULT_PV_PROBLEM_THRESHOLD)) / 100
        self.pv_monitor = PVBalanceMonitor(
            monitored if len(monitored) >= MIN_MONITORED_INPUTS else [],
            threshold=threshold,
            on_seconds=float(options.get(CONF_PV_PROBLEM_MINUTES, DEFAULT_PV_PROBLEM_MINUTES)) * 60,
            off_seconds=PV_RECOVERY_MINUTES * 60,
            min_power=float(options.get(CONF_PV_MIN_POWER, DEFAULT_PV_MIN_POWER)),
            min_elevation=float(options.get(CONF_PV_MIN_SUN_ELEVATION, DEFAULT_PV_MIN_SUN_ELEVATION)),
        )
        self._derived_definitions = derived_definitions(
            self.parameter_definition, self.pv_inputs, self.pv_monitor.inputs)

    @property
    def serial(self):
        return self._serial

    @property
    def status_connection(self):
        return 'Connected' if self._status_connection == 1 else 'Diconnected'

    def is_connected_to_server(self):
        return self._modbus != None

    def connect_to_server(self):
        if self._modbus:
            return self._modbus
        log.info(f"Connecting to solarman data logger {self._host}:{self._port} (serial {self._serial}, slave id {self._mb_slaveid})")
        self._modbus = PySolarmanV5(self._host, self._serial, port=self._port, mb_slave_id=self._mb_slaveid, logger=None, auto_reconnect=True, socket_timeout=15)

    def disconnect_from_server(self):
        if self._modbus:
            try:
                log.info(f"Disconnecting from solarman data logger {self._host}:{self._port}")
                self._modbus.disconnect()
            finally:
                self._modbus = None

    def send_request(self, params, start, end, mb_fc):
        length = end - start + 1
        match mb_fc:
            case 3:
                response  = self._modbus.read_holding_registers(register_addr=start, quantity=length)
            case 4:
                response  = self._modbus.read_input_registers(register_addr=start, quantity=length)
        params.parse(response, start, length)        


    def _sun_elevation(self):
        """Current sun elevation in degrees, or None when unknown."""
        if self.hass is None:
            return None
        sun_state = self.hass.states.get('sun.sun')
        if sun_state is None:
            return None
        try:
            return float(sun_state.attributes.get('elevation'))
        except (TypeError, ValueError):
            return None

    def _ac_max_power(self):
        if self._ac_max_power_option > 0:
            return self._ac_max_power_option
        return self._rated_power_seen

    def _apply_values(self, raw, connected):
        """Publish a poll result: raw values + derived values, and feed the
        PV balance monitor. Call with the lock held (or from a single thread)."""
        values = dict(raw)
        try:
            rated = raw.get(RATED_POWER_NAME)
            if rated:
                self._rated_power_seen = float(rated)
            derived = compute_derived(raw, self.pv_inputs, self._ac_max_power(), connected)
            values.update(derived)

            monitor = self.pv_monitor
            if monitor.enabled:
                powers = {n: derived[pv_power_name(n)] for n in monitor.inputs if pv_power_name(n) in derived}
                readings = {}
                for n in monitor.inputs:
                    volt, amp = raw.get(f'PV{n} Voltage'), raw.get(f'PV{n} Current')
                    if volt is not None and amp is not None:
                        readings[n] = (float(volt), float(amp))
                monitor.update(time.time(), powers, self._sun_elevation(), connected, readings)
                for n in monitor.inputs:
                    ratio = monitor.ratios.get(n)
                    if ratio is not None:
                        values[f'PV{n} Relative Output'] = round(ratio * 100, 1)
        except Exception as e:  # never let derived values break polling
            log.warning(f"Computing derived values failed [{type(e).__name__}: {e}]")
        self._current_val = values

    def _sun_allows_polling(self):
        """Return False while the sun is far enough below the horizon that
        the logger is expected to be unpowered/unreachable."""
        if not self.use_sun or self.hass is None:
            return True

        sun_state = self.hass.states.get('sun.sun')
        if sun_state is None:
            # sun integration not available for some reason: fail open,
            # keep the previous (always-poll) behaviour.
            return True

        try:
            elevation = float(sun_state.attributes.get('elevation'))
        except (TypeError, ValueError):
            return True

        return elevation >= self.sun_elevation_threshold

    @Throttle (MIN_TIME_BETWEEN_UPDATES)
    def update (self):
        if not self._sun_allows_polling():
            sun_state = self.hass.states.get('sun.sun')
            next_rising = sun_state.attributes.get('next_rising') if sun_state else 'unknown'
            log.debug(
                f"Sun elevation below {self.sun_elevation_threshold}°, skipping inverter "
                f"query for {self._host}:{self._port}. Expected back around {next_rising}."
            )
            if self._status_connection != 0:
                self.disconnect_from_server()
            self._status_connection = 0
            with self.lock:
                self._apply_values({}, False)
            return
        self.get_statistics()
        return


    def get_statistics(self):
        result = 1
        params = ParameterParser(self.parameter_definition)
        requests = self.parameter_definition['requests']
        log.debug(f"Starting to query for [{len(requests)}] ranges...")

        with self.lock:
            try:
                isConnected = self._status_connection == 1
                for request in requests:
                    start = request['start']
                    end = request['end']
                    mb_fc = request['mb_functioncode']
                    log.debug(f"Querying [{start} - {end}]...")

                    attempts_left = QUERY_RETRY_ATTEMPTS
                    while attempts_left > 0:
                        attempts_left -= 1
                        try:
                            self.connect_to_server()
                            self.send_request(params, start, end, mb_fc)
                            result = 1
                        except Exception as e:
                            result = 0
                            log.log((logging.WARNING if isConnected else logging.DEBUG), f"Querying [{start} - {end}] failed with exception [{type(e).__name__}: {e}]")
                            self.disconnect_from_server()
                        if result == 0:
                            log.log((logging.WARNING if isConnected else logging.DEBUG), f"Querying [{start} - {end}] failed, [{attempts_left}] retry attempts left")
                        else:
                            log.debug(f"Querying [{start} - {end}] succeeded")
                            break
                    if result == 0:
                        log.log((logging.WARNING if isConnected else logging.DEBUG), f"Querying registers [{start} - {end}] failed, aborting.")
                        break

                if result == 1:
                    log.debug(f"All queries succeeded, exposing updated values.")
                    self.status_lastUpdate = datetime.now().strftime("%m/%d/%Y, %H:%M:%S")
                    self._status_connection = 1
                    self._apply_values(params.get_result(), True)
                else:
                    self._status_connection = 0
                    # Clear cached previous results to not report stale and incorrect data
                    self._apply_values({}, False)
                    self.disconnect_from_server()
            except Exception as e:
                log.warning(f"Querying inverter {self._serial} at {self._host}:{self._port} failed on connection start with exception [{type(e).__name__}: {e}]")
                self._status_connection = 0
                # Clear cached previous results to not report stale and incorrect data
                self._apply_values({}, False)
                self.disconnect_from_server()

    def get_current_val(self):
        return self._current_val

    def get_sensors(self):
        params = ParameterParser(self.parameter_definition)
        return params.get_sensors () + self._derived_definitions

    # Service calls
    def service_read_holding_register(self, register):
        log.debug(f'Service Call: read_holding_register : [{register}]')

        with self.lock:
            try:
                wasConnected = self.is_connected_to_server()
                self.connect_to_server()
                response = self._modbus.read_holding_registers(register, 1)
                log.info(f'Service Call: read_holding_registers : [{register}] value [{response}]')
                if (not wasConnected):
                    self.disconnect_from_server()
            except Exception as e:
                log.warning(f"Service Call: read_holding_registers : [{register}] failed with exception [{type(e).__name__}: {e}]")
                self.disconnect_from_server()
                raise e
               
        return response

    def service_read_multiple_holding_registers(self, register, count):
        log.debug(f'Service Call: read_holding_register : [{register}], count : {count}')

        with self.lock:
            try:
                wasConnected = self.is_connected_to_server()
                self.connect_to_server()
                response = self._modbus.read_holding_registers(register, count)
                log.info(f'Service Call: read_holding_registers : [{register}] value [{response}]')
                if (not wasConnected):
                    self.disconnect_from_server()
            except Exception as e:
                log.warning(f"Service Call: read_holding_registers : [{register}] failed with exception [{type(e).__name__}: {e}]")
                self.disconnect_from_server()
                raise e
               
        return response


    def service_write_holding_register(self, register, value):
        log.debug(f'Service Call: write_holding_register : [{register}], value : [{value}]')
        with self.lock:
            try:
                wasConnected = self.is_connected_to_server()
                self.connect_to_server()
                self._modbus.write_holding_register(register, value)
                if (not wasConnected):
                    self.disconnect_from_server()
            except Exception as e:
                log.warning(f"Service Call: write_holding_register : [{register}], value : [{value}] failed with exception [{type(e).__name__}: {e}]")
                self.disconnect_from_server()
                raise e
        return

    def service_write_multiple_holding_registers(self, register, values):
        log.debug(f'Service Call: write_multiple_holding_registers: [{register}], values : [{values}]')
        with self.lock:
            try:
                wasConnected = self.is_connected_to_server()
                self.connect_to_server()
                self._modbus.write_multiple_holding_registers(register, values)
                if (not wasConnected):
                    self.disconnect_from_server()
            except Exception as e:
                log.warning(f"Service Call: write_multiple_holding_registers: [{register}], values : [{values}] failed with exception [{type(e).__name__}: {e}]")
                self.disconnect_from_server()
                raise e
        return

