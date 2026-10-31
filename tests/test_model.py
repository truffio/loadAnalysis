"""C-MODEL cases from docs/test-cases.md."""

import math
from pathlib import Path

import pytest
from conftest import (
    BANDS,
    delp,
    find,
    fx,
    has_error,
    path_of,
    pick,
    setp,
    swap,
    warnings_at,
)
from pydantic import BaseModel

import ela.model
from ela.validate import validate


def accepted(doc):
    result = validate(doc)
    assert result.errors == []
    assert result.definition is not None
    return result


def rejected(doc):
    result = validate(doc)
    assert result.errors
    assert result.definition is None
    return result


def unknown_key_warnings(result, key):
    return [w for w in result.warnings if f"'{key}'" in w.message and "unknown" in w.message.lower()]


TOP_KEYS = ["meta", "settings", "sources", "buses", "trus", "contactors", "loads", "scenarios"]


@pytest.mark.tc("TC-MOD-001")
@pytest.mark.parametrize("key", TOP_KEYS)
def test_top_level_key_required(key):
    doc = fx("FX-SINGLE")
    del doc[key]
    assert has_error(rejected(doc), "$", key)


@pytest.mark.tc("TC-MOD-001")
def test_top_level_accepted_including_empty_trus():
    accepted(fx("FX-SINGLE"))
    doc = fx("FX-SINGLE")
    doc["trus"] = []
    doc["contactors"] = [c for c in doc["contactors"] if not c["id"].startswith("TRU1")]
    accepted(doc)


@pytest.mark.tc("TC-MOD-002")
@pytest.mark.parametrize("key", ["aircraft", "revision"])
def test_meta_required_keys(key):
    assert has_error(rejected(delp(fx("FX-SINGLE"), f"$.meta.{key}")), "$.meta", key)


@pytest.mark.tc("TC-MOD-002")
def test_meta_description_is_optional():
    with_it = accepted(setp(fx("FX-SINGLE"), "$.meta.description", "x"))
    without = accepted(fx("FX-SINGLE"))
    assert unknown_key_warnings(with_it, "description") == []
    assert unknown_key_warnings(without, "description") == []


@pytest.mark.tc("TC-MOD-003")
def test_values_held_with_no_conversion():
    doc = fx("FX-SINGLE")
    setp(doc, "$.sources[0].capacity.transient", 135000)
    setp(doc, "$.sources[0].voltage", 115)
    setp(doc, "$.settings.safety_margin", 0.10)
    setp(doc, "$.trus[0].efficiency", 0.85)
    defn = accepted(doc).definition
    assert defn.sources[0].capacity.transient == 135000
    assert defn.sources[0].voltage == 115
    assert defn.settings.safety_margin == 0.10
    assert defn.trus[0].efficiency == 0.85


@pytest.mark.tc("TC-MOD-004")
def test_global_margin_required():
    doc = delp(fx("FX-SINGLE"), "$.settings.safety_margin")
    assert has_error(rejected(doc), "$.settings", "safety_margin")


@pytest.mark.tc("TC-MOD-004")
@pytest.mark.parametrize("bad", [True, "0.10", math.nan])
def test_global_margin_strict(bad):
    rejected(setp(fx("FX-SINGLE"), "$.settings.safety_margin", bad))


@pytest.mark.tc("TC-MOD-004")
def test_global_margin_accepted():
    accepted(setp(fx("FX-SINGLE"), "$.settings.safety_margin", 0.10))


@pytest.mark.tc("TC-MOD-005")
@pytest.mark.parametrize("band", BANDS)
@pytest.mark.parametrize("obj", ["$.loads[0].power", "$.sources[0].capacity"])
def test_all_three_bands_required(obj, band):
    rejected(delp(fx("FX-SINGLE"), f"{obj}.{band}"))


@pytest.mark.tc("TC-MOD-005")
def test_all_three_bands_accepted():
    accepted(fx("FX-SINGLE"))


@pytest.mark.tc("TC-MOD-006")
def test_band_labels_default():
    labels = accepted(fx("FX-SINGLE")).definition.settings.bands
    assert (labels.transient.label, labels.short_term.label, labels.continuous.label) == (
        "Transient",
        "5 s",
        "Continuous",
    )


@pytest.mark.tc("TC-MOD-006")
def test_band_label_override():
    doc = setp(fx("FX-SINGLE"), "$.settings.bands", {"transient": {"label": "Peak"}})
    labels = accepted(doc).definition.settings.bands
    assert (labels.transient.label, labels.short_term.label, labels.continuous.label) == (
        "Peak",
        "5 s",
        "Continuous",
    )


@pytest.mark.tc("TC-MOD-006")
def test_duration_s_is_known():
    doc = setp(
        fx("FX-SINGLE"), "$.settings.bands", {"short_term": {"label": "5 s", "duration_s": 5}}
    )
    result = accepted(doc)
    assert unknown_key_warnings(result, "duration_s") == []
    assert result.definition.settings.bands.short_term.duration_s == 5


@pytest.mark.tc("TC-MOD-007")
@pytest.mark.parametrize("element", ["G1", "AC1", "TRU1", "C_G1", "LA"])
@pytest.mark.parametrize("key", ["id", "name"])
def test_every_element_needs_id_and_name(element, key):
    doc = fx("FX-SINGLE")
    path = path_of(doc, element)
    del find(doc, element)[key]
    assert has_error(rejected(doc), path, key)


@pytest.mark.tc("TC-MOD-008")
def test_all_four_source_kinds_accepted():
    kinds = {s["kind"] for s in fx("FX-ALLKINDS")["sources"]}
    assert kinds == {"engine_generator", "apu_generator", "emergency_generator", "battery"}
    accepted(fx("FX-ALLKINDS"))


@pytest.mark.tc("TC-MOD-008")
def test_unknown_source_kind_rejected():
    doc = setp(fx("FX-ALLKINDS"), "$.sources[0].kind", "fuel_cell")
    assert has_error(rejected(doc), "$.sources[0].kind")


@pytest.mark.tc("TC-MOD-009")
@pytest.mark.parametrize("key", ["output", "voltage", "capacity"])
def test_source_attributes_required(key):
    rejected(delp(fx("FX-SINGLE"), f"$.sources[0].{key}"))


@pytest.mark.tc("TC-MOD-009")
def test_rat_outputs_are_separate_sources():
    doc = fx("FX-RAT")
    find(doc, "RAT_DC")["default_state"] = "available"
    ac_out, dc_out = accepted(doc).definition.sources
    assert (ac_out.output, dc_out.output) == ("AC", "DC")
    assert (ac_out.capacity.continuous, dc_out.capacity.continuous) == (5000, 3000)
    assert (ac_out.default_state, dc_out.default_state) == ("unavailable", "available")


@pytest.mark.tc("TC-MOD-010")
def test_engine_number_rules():
    rejected(delp(fx("FX-APU"), "$.sources[0].engine"))
    rejected(setp(fx("FX-APU"), "$.sources[0].engine", 1.5))
    apu = pick(accepted(fx("FX-APU")).definition.sources, "APU")
    assert apu.engine is None


@pytest.mark.tc("TC-MOD-011")
def test_default_state_on_generators_and_batteries():
    doc = fx("FX-ALLKINDS")
    del find(doc, "G1")["default_state"]
    rejected(doc)

    doc = fx("FX-ALLKINDS")
    find(doc, "BAT")["default_state"] = "failed"
    accepted(doc)

    doc = fx("FX-ALLKINDS")
    find(doc, "APU")["default_state"] = "available"
    rejected(doc)


@pytest.mark.tc("TC-MOD-012")
def test_emergency_generator_default_state():
    doc = fx("FX-RAT")
    del find(doc, "RAT_AC")["default_state"]
    assert pick(accepted(doc).definition.sources, "RAT_AC").default_state == "unavailable"

    doc = fx("FX-RAT")
    find(doc, "RAT_AC")["default_state"] = "operative"
    rejected(doc)

    doc = fx("FX-RAT")
    find(doc, "RAT_AC")["default_state"] = "available"
    assert pick(accepted(doc).definition.sources, "RAT_AC").default_state == "available"


@pytest.mark.tc("TC-MOD-013")
def test_phases_default_and_dc_phases_unknown():
    doc = fx("FX-SINGLE")
    del find(doc, "AC1")["phases"]
    assert pick(accepted(doc).definition.buses, "AC1").phases == 3

    find(doc, "AC1")["phases"] = 1
    assert pick(accepted(doc).definition.buses, "AC1").phases == 1

    doc = fx("FX-SINGLE")
    del find(doc, "G1")["phases"]
    assert pick(accepted(doc).definition.sources, "G1").phases == 3

    doc = fx("FX-SINGLE")
    find(doc, "DC1")["phases"] = 3
    assert len(unknown_key_warnings(accepted(doc), "phases")) == 1


@pytest.mark.tc("TC-MOD-014")
def test_bus_type_and_role_accepted():
    doc = fx("FX-ROLES")
    roles = {(b["type"], b["role"]) for b in doc["buses"]}
    assert roles == {
        (t, r) for t in ("AC", "DC") for r in ("main", "essential", "emergency", "other")
    } | {("DC", "battery")}
    accepted(doc)


@pytest.mark.tc("TC-MOD-014")
@pytest.mark.parametrize("key", ["type", "role", "voltage"])
def test_bus_keys_required(key):
    doc = fx("FX-ROLES")
    del find(doc, "AC1")[key]
    rejected(doc)


@pytest.mark.tc("TC-MOD-014")
@pytest.mark.parametrize(
    "bus, key, value",
    [
        ("AC1", "type", "HVDC"),
        ("AC1", "role", "battery"),
        ("AC1", "role", "spare"),
        ("DC1", "role", "spare"),
    ],
)
def test_bus_values_rejected(bus, key, value):
    doc = fx("FX-ROLES")
    find(doc, bus)[key] = value
    rejected(doc)


@pytest.mark.tc("TC-MOD-015")
def test_capacity_optional_on_buses_and_contactors():
    defn = accepted(fx("FX-SINGLE")).definition
    assert pick(defn.buses, "AC1").capacity is None
    assert pick(defn.contactors, "C_G1").capacity is None

    doc = fx("FX-SINGLE")
    full = dict.fromkeys(BANDS, 500)
    find(doc, "AC1")["capacity"] = dict(full)
    find(doc, "C_G1")["capacity"] = dict(full)
    defn = accepted(doc).definition
    assert pick(defn.buses, "AC1").capacity.short_term == 500
    assert pick(defn.contactors, "C_G1").capacity.continuous == 500


@pytest.mark.tc("TC-MOD-016")
def test_optional_booleans():
    defn = accepted(fx("FX-ESS")).definition
    assert pick(defn.buses, "AC1").crew_switch is False
    assert pick(defn.buses, "DCS").crew_switch is True
    assert pick(defn.loads, "LN").essential is False
    assert pick(defn.loads, "LE1").essential is True


@pytest.mark.tc("TC-MOD-017")
@pytest.mark.parametrize(
    "key", ["input_bus", "output_bus", "efficiency", "capacity", "default_state"]
)
def test_tru_keys_required(key):
    rejected(delp(fx("FX-SINGLE"), f"$.trus[0].{key}"))


@pytest.mark.tc("TC-MOD-017")
def test_tru_default_state_value():
    rejected(setp(fx("FX-SINGLE"), "$.trus[0].default_state", "closed"))


@pytest.mark.tc("TC-MOD-018")
@pytest.mark.parametrize("key", ["kind", "from", "to", "default_state"])
def test_contactor_keys_required(key):
    doc = fx("FX-SINGLE")
    del find(doc, "C_G1")[key]
    rejected(doc)


@pytest.mark.tc("TC-MOD-018")
def test_contactor_values():
    doc = fx("FX-SINGLE")
    find(doc, "C_G1")["to"] = ["AC1", "DC1"]
    rejected(doc)

    doc = fx("FX-SINGLE")
    find(doc, "C_G1")["default_state"] = "on"
    rejected(doc)

    doc = fx("FX-SINGLE")
    swap(find(doc, "TRU1_IN"))
    accepted(doc)


@pytest.mark.tc("TC-MOD-019")
def test_source_bus_key_is_only_a_warning():
    doc = fx("FX-EMPTY")
    find(doc, "G2")["bus"] = "AC2"
    result = accepted(doc)
    assert len(warnings_at(result, f"{path_of(doc, 'G2')}.bus")) == 1


@pytest.mark.tc("TC-MOD-020")
def test_safety_margin_on_each_element_kind():
    doc = fx("FX-SINGLE")
    for element in ("G1", "TRU1", "AC1", "C_G1"):
        find(doc, element)["safety_margin"] = 0.25
    result = accepted(doc)
    assert unknown_key_warnings(result, "safety_margin") == []
    defn = result.definition
    for items, element in (
        (defn.sources, "G1"),
        (defn.trus, "TRU1"),
        (defn.buses, "AC1"),
        (defn.contactors, "C_G1"),
    ):
        assert pick(items, element).safety_margin == 0.25


@pytest.mark.tc("TC-MOD-021")
@pytest.mark.parametrize("key", ["bus", "power"])
def test_load_keys_required(key):
    doc = fx("FX-SINGLE")
    del find(doc, "LA")[key]
    rejected(doc)


@pytest.mark.tc("TC-MOD-021")
def test_load_on_one_bus_only():
    doc = fx("FX-SINGLE")
    find(doc, "LA")["bus"] = ["AC1", "DC1"]
    rejected(doc)


def _with_scenario():
    return setp(fx("FX-SINGLE"), "$.scenarios", [{"id": "S1", "name": "n", "states": {}}])


@pytest.mark.tc("TC-MOD-022")
@pytest.mark.parametrize("key", ["id", "name", "states"])
def test_scenario_keys_required(key):
    rejected(delp(_with_scenario(), f"$.scenarios[0].{key}"))


@pytest.mark.tc("TC-MOD-022")
def test_scenario_description_optional():
    with_it = accepted(setp(_with_scenario(), "$.scenarios[0].description", "d"))
    without = accepted(_with_scenario())
    assert unknown_key_warnings(with_it, "description") == []
    assert unknown_key_warnings(without, "description") == []


def _schema_names(node, found):
    """Every property name and definition name in a JSON schema."""
    if isinstance(node, dict):
        for section in ("properties", "$defs"):
            found.update(node.get(section, {}))
        for value in node.values():
            _schema_names(value, found)
    elif isinstance(node, list):
        for value in node:
            _schema_names(value, found)
    return found


@pytest.mark.tc("TC-MOD-023")
def test_schema_has_no_coordinate_or_breaker_keys():
    names = _schema_names(ela.model.Definition.model_json_schema(), set())
    assert "voltage" in names  # the walk reached the element definitions
    assert not names & {"x", "y", "position", "coordinates"}
    assert not [n for n in names if "breaker" in n.lower()]


@pytest.mark.tc("TC-MOD-023")
def test_coordinate_key_is_unknown():
    doc = fx("FX-SINGLE")
    find(doc, "AC1")["x"] = 10
    assert len(unknown_key_warnings(accepted(doc), "x")) == 1


@pytest.mark.tc("TC-MOD-024")
def test_endurance_and_flight_phase_keys_are_unknown():
    doc = fx("FX-BAT")
    find(doc, "BAT")["amp_hours"] = 40
    assert len(unknown_key_warnings(accepted(doc), "amp_hours")) == 1

    doc = fx("FX-SINGLE")
    find(doc, "LA")["flight_phase"] = "cruise"
    assert len(unknown_key_warnings(accepted(doc), "flight_phase")) == 1


@pytest.mark.tc("TC-MOD-025")
def test_pydantic_schema_module():
    assert Path(ela.model.__file__).name == "model.py"
    assert issubclass(ela.model.Definition, BaseModel)
