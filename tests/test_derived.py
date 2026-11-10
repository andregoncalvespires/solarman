import pytest
import yaml
from conftest import DEFINITIONS, derived


def load(name):
    return yaml.safe_load((DEFINITIONS / name).read_text())


def test_4mppt_has_four_inputs():
    assert derived.find_pv_inputs(load("deye_4mppt.yaml")) == [1, 2, 3, 4]


def test_no_collision_with_existing_names():
    # hybrid profiles already define "PV1 Power": it must not be redefined
    definition = load("deye_hybrid.yaml")
    names = {d["name"] for d in derived.derived_definitions(definition, derived.find_pv_inputs(definition), [])}
    assert "PV1 Power" not in names


@pytest.mark.parametrize("name", sorted(p.name for p in DEFINITIONS.glob("*.yaml")))
def test_every_profile_yields_unique_names(name):
    definition = load(name)
    inputs = derived.find_pv_inputs(definition)
    existing = [i["name"] for g in definition["parameters"] for i in g["items"]]
    new = [d["name"] for d in derived.derived_definitions(definition, inputs, inputs)]
    assert len(new) == len(set(new))
    assert not set(new) & set(existing)


def test_4mppt_definitions():
    definition = load("deye_4mppt.yaml")
    names = [d["name"] for d in derived.derived_definitions(definition, [1, 2, 3, 4], [1, 2, 3, 4])]
    assert names == ["PV1 Power", "PV2 Power", "PV3 Power", "PV4 Power", "PV Total Power",
                     "AC Output Load", "PV1 Relative Output", "PV2 Relative Output",
                     "PV3 Relative Output", "PV4 Relative Output"]


RAW = {"PV1 Voltage": 36.5, "PV1 Current": 8.2, "PV2 Voltage": 36.0, "PV2 Current": 0.0,
       "Total AC Output Power (Active)": 1060.0}


def test_compute_connected():
    out = derived.compute_derived(RAW, [1, 2], 2120, True)
    assert out["PV1 Power"] == 299.3     # product rounded as a whole
    assert out["PV2 Power"] == 0.0
    assert out["PV Total Power"] == 299.3
    assert out["AC Output Load"] == 50.0


def test_compute_disconnected_is_zero():
    out = derived.compute_derived({}, [1, 2], 2120, False)
    assert out == {"PV1 Power": 0.0, "PV2 Power": 0.0, "PV Total Power": 0.0, "AC Output Load": 0.0}


def test_load_unknown_without_capacity():
    assert "AC Output Load" not in derived.compute_derived(RAW, [1], None, True)
