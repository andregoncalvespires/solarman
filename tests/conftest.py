"""Load the pure-Python modules by path so tests do not need Home Assistant."""
import importlib.util
import pathlib
import sys

BASE = pathlib.Path(__file__).resolve().parent.parent / "custom_components" / "solarman"


def _load(name):
    spec = importlib.util.spec_from_file_location(f"solarman_pure_{name}", BASE / f"{name}.py")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


derived = _load("derived")
pv_monitor = _load("pv_monitor")
DEFINITIONS = BASE / "inverter_definitions"
