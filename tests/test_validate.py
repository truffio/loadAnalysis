"""C-VALID cases from docs/test-cases.md, except the meta case TC-VAL-007."""

import math
import re
from pathlib import Path

import pytest
from conftest import (
    ac,
    apu,
    c,
    contactor,
    dc,
    delp,
    find,
    fx,
    fx_rat_ac_only,
    has_error,
    load,
    path_of,
    scenario,
    setp,
    swap,
    tie,
    tru,
    tru_contactors,
    warnings_at,
)

import ela.validate
from ela.validate import check_states, validate


def clean(doc):
    result = validate(doc)
    assert result.errors == []
    return result


def errors_at(result, path):
    return [e for e in result.errors if e.path == path]


def rooted(result):
    return [e.path for e in result.errors + result.warnings]


@pytest.mark.tc("TC-VAL-001")
@pytest.mark.parametrize("index", range(20))
def test_malformed_documents(index):
    result = validate(fx("FX-MALFORMED")[index])
    assert result.errors
    assert result.definition is None
    assert all(path.startswith("$") for path in rooted(result))


@pytest.mark.tc("TC-VAL-002")
def test_five_seeded_faults_in_one_call():
    doc = fx("FX-FIVE")
    result = validate(doc)
    assert has_error(result, "$.meta", "revision")
    assert errors_at(result, "$.loads[1].id")
    assert errors_at(result, "$.loads[0].bus")
    assert errors_at(result, "$.trus[0].input_bus")
    assert errors_at(result, "$.trus[0].output_bus")
    assert errors_at(result, path_of(doc, "TBAD"))


@pytest.mark.tc("TC-VAL-003")
def test_ten_errors_reported_together():
    doc = fx("FX-MANY")
    result = validate(doc)
    assert len(result.errors) >= 10
    for path in (
        "$.settings",
        "$.loads[0].power.transient",
        "$.loads[0].power",
        "$.buses[0].voltage",
        "$.scenarios[0].states.GHOST",
        "$.scenarios[0].states.G1",
        "$.trus[0].efficiency",
        "$.loads[1].bus",
        "$.loads[2].id",
        path_of(doc, "TBAD"),
    ):
        assert errors_at(result, path), path
    assert result.definition is None


@pytest.mark.tc("TC-VAL-004")
def test_rooted_paths_and_messages():
    doc = fx("FX-SINGLE")
    doc["loads"] += [load("L3", "AC1", 1), load("L4", "AC1", 1)]
    setp(doc, "$.loads[3].bus", "NOBUS")
    result = validate(doc)
    assert has_error(result, "$.loads[3].bus", "NOBUS")

    warned = warnings_at(validate(fx("FX-WARN")), "$.zzz")
    assert len(warned) == 1
    assert warned[0].message


@pytest.mark.tc("TC-VAL-005")
def test_definition_only_without_errors():
    assert validate(fx("FX-THREEERR")).definition is None
    result = validate(fx("FX-WARN"))
    assert result.definition is not None
    assert result.errors == []
    assert warnings_at(result, "$.zzz")


@pytest.mark.tc("TC-VAL-006")
def test_validator_module():
    assert Path(ela.validate.__file__).name == "validate.py"
    assert callable(ela.validate.validate)


def _required_keys():
    """(path of parent, key, old id) for every required key of FX-ALLKINDS."""
    doc = fx("FX-ALLKINDS")
    cases = [("$.meta", "aircraft"), ("$.meta", "revision"), ("$.settings", "safety_margin")]
    by_kind = {
        "engine_generator": ["engine", "default_state"],
        "apu_generator": ["default_state"],
        "emergency_generator": [],
        "battery": ["default_state"],
    }
    for i, s in enumerate(doc["sources"]):
        keys = ["id", "name", "kind", "output", "voltage", "capacity"] + by_kind[s["kind"]]
        cases += [(f"$.sources[{i}]", k) for k in keys]
    for i in range(len(doc["buses"])):
        cases += [(f"$.buses[{i}]", k) for k in ("id", "name", "type", "role", "voltage")]
    for i in range(len(doc["trus"])):
        keys = ("id", "name", "input_bus", "output_bus", "efficiency", "capacity", "default_state")
        cases += [(f"$.trus[{i}]", k) for k in keys]
    for i in range(len(doc["contactors"])):
        keys = ("id", "name", "kind", "from", "to", "default_state")
        cases += [(f"$.contactors[{i}]", k) for k in keys]
    for i in range(len(doc["loads"])):
        cases += [(f"$.loads[{i}]", k) for k in ("id", "name", "bus", "power")]
    return cases


@pytest.mark.tc("TC-VAL-008")
@pytest.mark.parametrize("parent, key", _required_keys())
def test_one_missing_key_one_error_at_parent(parent, key):
    doc = fx("FX-ALLKINDS")
    old_id = None
    if key == "id":
        collection, index = re.fullmatch(r"\$\.(\w+)\[(\d+)\]", parent).groups()
        old_id = doc[collection][int(index)]["id"]
    result = validate(delp(doc, f"{parent}.{key}"))
    named = [e for e in result.errors if e.path == parent and key in e.message]
    assert named
    if key == "id":
        others = [e for e in result.errors if e not in named]
        assert all(old_id in e.message for e in others)
    else:
        assert len(result.errors) == 1, result.errors


@pytest.mark.tc("TC-VAL-009")
@pytest.mark.parametrize(
    "path, value",
    [
        ("$.trus[0].efficiency", "0.85"),
        ("$.sources[0].kind", "fuel_cell"),
        ("$.settings.safety_margin", True),
        ("$.buses[0].crew_switch", "yes"),
        ("$.loads[0].power.transient", math.nan),
        ("$.loads[0].power.transient", math.inf),
    ],
)
def test_wrong_type_or_value_gives_one_error(path, value):
    result = validate(setp(fx("FX-SINGLE"), path, value))
    assert [e.path for e in result.errors] == [path]


@pytest.mark.tc("TC-VAL-010")
def test_bus_and_tru_sharing_an_id():
    doc = fx("FX-SINGLE")
    find(doc, "TRU1_IN")["to"] = "AC1"
    find(doc, "TRU1_OUT")["from"] = "AC1"
    find(doc, "TRU1")["id"] = "AC1"
    result = validate(doc)
    assert len(result.errors) == 1
    assert "AC1" in result.errors[0].message


@pytest.mark.tc("TC-VAL-010")
def test_repeated_scenario_id():
    doc = fx("FX-SINGLE")
    doc["scenarios"] = [scenario("S1", {}), scenario("S1", {})]
    result = validate(doc)
    assert len(result.errors) == 1
    assert errors_at(result, "$.scenarios[1].id")


@pytest.mark.tc("TC-VAL-010")
def test_scenario_may_share_a_bus_id():
    doc = fx("FX-SINGLE")
    doc["scenarios"] = [scenario("AC1", {})]
    clean(doc)


@pytest.mark.tc("TC-VAL-011")
def test_missing_band():
    result = validate(delp(fx("FX-SINGLE"), "$.loads[0].power.short_term"))
    assert len(result.errors) == 1
    assert has_error(result, "$.loads[0].power", "short_term")


@pytest.mark.tc("TC-VAL-011")
def test_missing_capacity():
    doc = delp(fx("FX-SINGLE"), "$.sources[0].capacity")
    delp(doc, "$.trus[0].capacity")
    assert len(validate(doc).errors) == 2


@pytest.mark.tc("TC-VAL-011")
def test_capacity_optional_on_bus_and_contactor():
    doc = fx("FX-SINGLE")
    for element in ("AC1", "C_G1"):
        find(doc, element)["capacity"] = {"transient": 1, "short_term": 1, "continuous": 1}
    clean(doc)
    for element in ("AC1", "C_G1"):
        del find(doc, element)["capacity"]
    clean(doc)


@pytest.mark.tc("TC-VAL-012")
def test_negative_power_and_capacity():
    doc = setp(fx("FX-SINGLE"), "$.loads[0].power.transient", -1)
    assert len(validate(doc).errors) == 1
    clean(setp(fx("FX-SINGLE"), "$.loads[0].power.transient", 0))
    doc = setp(fx("FX-SINGLE"), "$.sources[0].capacity.continuous", -1)
    assert len(validate(doc).errors) == 1


@pytest.mark.tc("TC-VAL-013")
def test_band_ordering_not_enforced():
    doc = fx("FX-SINGLE-E")
    setp(doc, "$.loads[0].power", {"transient": 10, "short_term": 20, "continuous": 30})
    setp(doc, "$.sources[0].capacity", {"transient": 5000, "short_term": 20000, "continuous": 30000})
    result = clean(doc)
    assert result.warnings == []


@pytest.mark.tc("TC-VAL-014")
@pytest.mark.parametrize("eta", [0, -0.1, 1.01])
def test_efficiency_out_of_range(eta):
    assert len(validate(setp(fx("FX-SINGLE"), "$.trus[0].efficiency", eta)).errors) == 1


@pytest.mark.tc("TC-VAL-014")
@pytest.mark.parametrize("eta", [1.0, 0.01])
def test_efficiency_in_range(eta):
    clean(setp(fx("FX-SINGLE"), "$.trus[0].efficiency", eta))


@pytest.mark.tc("TC-VAL-015")
@pytest.mark.parametrize(
    "path, value",
    [
        ("$.buses[0].voltage", 0),
        ("$.sources[0].voltage", 0),
        ("$.buses[0].phases", 0),
        ("$.settings.safety_margin", -0.1),
        ("$.sources[0].safety_margin", -0.1),
    ],
)
def test_values_out_of_range(path, value):
    result = validate(setp(fx("FX-SINGLE"), path, value))
    assert [e.path for e in result.errors] == [path]


@pytest.mark.tc("TC-VAL-015")
def test_zero_margin_allowed():
    clean(setp(fx("FX-SINGLE"), "$.settings.safety_margin", 0))


@pytest.mark.tc("TC-VAL-016")
def test_one_apu():
    clean(fx("FX-SINGLE"))
    clean(fx("FX-APU"))
    doc = fx("FX-APU")
    doc["sources"].append(apu(id="APU2"))
    doc["contactors"].append(c("APU2", "AC1", "open"))
    assert len(validate(doc).errors) == 1


@pytest.mark.tc("TC-VAL-016")
def test_one_generator_per_engine():
    clean(fx("FX-ENG", 8))
    doc = setp(fx("FX-ENG", 8), "$.sources[1].engine", 1)
    assert [e.path for e in validate(doc).errors] == ["$.sources[1].engine"]


DANGLING = [
    "$.loads[0].bus",
    "$.trus[0].input_bus",
    "$.trus[0].output_bus",
    "$.contactors[0].from",
    "$.contactors[0].to",
]


@pytest.mark.tc("TC-VAL-017")
@pytest.mark.parametrize("path", DANGLING)
def test_one_dangling_reference(path):
    assert has_error(validate(setp(fx("FX-SINGLE"), path, "NOBUS")), path, "NOBUS")


@pytest.mark.tc("TC-VAL-017")
def test_all_dangling_references_at_once():
    doc = fx("FX-SINGLE")
    for path in DANGLING:
        setp(doc, path, "NOBUS")
    result = validate(doc)
    for path in DANGLING:
        assert has_error(result, path, "NOBUS")


@pytest.mark.tc("TC-VAL-017")
def test_contactor_end_naming_a_load():
    result = validate(setp(fx("FX-SINGLE"), "$.contactors[0].to", "LA"))
    assert has_error(result, "$.contactors[0].to", "LA")


@pytest.mark.tc("TC-VAL-018")
def test_reversed_tru():
    doc = fx("FX-SINGLE")
    swap(doc["trus"][0], "input_bus", "output_bus")
    result = validate(doc)
    assert errors_at(result, "$.trus[0].input_bus")
    assert errors_at(result, "$.trus[0].output_bus")
    clean(fx("FX-SINGLE"))


@pytest.mark.tc("TC-VAL-019")
def test_ac_to_dc_contactors():
    doc = fx("FX-BAT")
    doc["contactors"].append(tie("TBAD", "AC1", "DC1"))
    result = validate(doc)
    assert len(result.errors) == 1
    assert errors_at(result, path_of(doc, "TBAD"))

    doc = fx("FX-BAT")
    find(doc, "C_BAT")["to"] = "AC1"
    result = validate(doc)
    assert len(result.errors) == 1
    assert errors_at(result, path_of(doc, "C_BAT"))

    clean(fx("FX-BAT"))


@pytest.mark.tc("TC-VAL-020")
@pytest.mark.parametrize(
    "extra",
    [
        tie("X1", "G1", "AC1"),
        contactor("X2", "tru", "AC1", "AC1b"),
        contactor("X3", "source", "AC1", "AC1b"),
        tie("X4", "AC1", "AC1"),
    ],
    ids=lambda x: x["id"],
)
def test_contactor_endpoints_suit_kind_and_differ(extra):
    doc = fx("FX-SINGLE")
    doc["buses"].append(ac("AC1b"))
    doc["contactors"].append(dict(extra))
    result = validate(doc)
    assert [e.path for e in result.errors] == [path_of(doc, extra["id"])]


def _tru_count_cases():
    def remove_input(doc):
        doc["contactors"].remove(find(doc, "TRU1_IN"))

    def second_output(doc):
        doc["contactors"].append(contactor("X", "tru", "TRU1", "DC1"))

    def output_to_other_bus(doc):
        doc["buses"].append(dc("DC2"))
        doc["contactors"].append(contactor("X", "tru", "TRU1", "DC2"))

    def second_input(doc):
        doc["contactors"].append(contactor("X", "tru", "AC1", "TRU1"))

    return [remove_input, second_output, output_to_other_bus, second_input]


@pytest.mark.tc("TC-VAL-021")
@pytest.mark.parametrize("mutate", _tru_count_cases(), ids=lambda f: f.__name__)
def test_tru_contactor_count(mutate):
    doc = fx("FX-SINGLE")
    mutate(doc)
    assert any("TRU1" in e.message for e in validate(doc).errors)


def _rat_with_tru2():
    doc = fx_rat_ac_only()
    t = tru("TRU2", "ACE", "DCE")
    doc["trus"].append(t)
    doc["contactors"] += tru_contactors(t)
    return doc


@pytest.mark.tc("TC-VAL-022")
def test_rat_feeds_tru_through_dedicated_bus():
    clean(_rat_with_tru2())


@pytest.mark.tc("TC-VAL-022")
def test_rat_feeding_tru_directly_is_one_error():
    doc = _rat_with_tru2()
    find(doc, "TRU2_IN")["from"] = "RAT_AC"
    result = validate(doc)
    assert [e.path for e in result.errors] == [path_of(doc, "TRU2_IN")]


@pytest.mark.tc("TC-VAL-023")
def test_unknown_states_keys():
    doc = fx("FX-ESS")
    doc["scenarios"] = [scenario("S", {"GHOST": "failed", "LE1": "failed", "AC1": "off"})]
    assert sorted(e.path for e in validate(doc).errors) == [
        "$.scenarios[0].states.AC1",
        "$.scenarios[0].states.GHOST",
        "$.scenarios[0].states.LE1",
    ]


STATE_VALID = [
    ("G1", "operative"),
    ("G1", "failed"),
    ("TRU1", "operative"),
    ("TRU1", "failed"),
    ("BAT", "operative"),
    ("BAT", "failed"),
    ("APU", "operative"),
    ("APU", "failed"),
    ("RAT_AC", "available"),
    ("RAT_AC", "unavailable"),
    ("T1E", "closed"),
    ("T1E", "open"),
    ("DCB", "on"),
    ("DCB", "off"),
]
STATE_INVALID = [
    ("G1", "closed"),
    ("RAT_AC", "operative"),
    ("T1E", "on"),
    ("DCB", "closed"),
    ("G1", "broken"),
]


@pytest.mark.tc("TC-VAL-024")
@pytest.mark.parametrize("key, value", STATE_VALID)
def test_valid_state_values(key, value):
    doc = fx("FX-ALLKINDS")
    doc["scenarios"] = [scenario("S", {key: value})]
    clean(doc)


@pytest.mark.tc("TC-VAL-024")
@pytest.mark.parametrize("key, value", STATE_INVALID)
def test_invalid_state_values(key, value):
    doc = fx("FX-ALLKINDS")
    doc["scenarios"] = [scenario("S", {key: value})]
    assert [e.path for e in validate(doc).errors] == [f"$.scenarios[0].states.{key}"]


@pytest.mark.tc("TC-VAL-025")
def test_states_check_is_one_shared_callable():
    states = {"GHOST": "failed", "G1": "closed"}
    defn = clean(fx("FX-SINGLE")).definition
    direct = check_states(defn, states)
    assert len(direct) == 2

    doc = fx("FX-SINGLE")
    doc["scenarios"] = [scenario("S", states)]
    via_scenario = validate(doc).errors
    assert sorted(e.message for e in via_scenario) == sorted(e.message for e in direct)
    assert sorted(e.path for e in via_scenario) == [
        "$.scenarios[0].states.G1",
        "$.scenarios[0].states.GHOST",
    ]


@pytest.mark.tc("TC-VAL-026")
def test_unknown_keys_warn():
    doc = fx("FX-WARN")
    find(doc, "AC1")["foo"] = 1
    result = clean(doc)
    unknown = [w for w in result.warnings if "unknown" in w.message.lower()]
    assert len(unknown) == 2
    assert {w.path for w in unknown} == {"$.zzz", f"{path_of(doc, 'AC1')}.foo"}
    assert "zzz" in unknown[0].message + unknown[1].message
    assert "foo" in unknown[0].message + unknown[1].message


def voltage_warnings(result):
    return [w for w in result.warnings if "voltage" in w.message.lower()]


@pytest.mark.tc("TC-VAL-027")
def test_voltage_mismatch_across_ties():
    doc = fx("FX-CHAIN")
    find(doc, "AC2")["voltage"] = 200
    warned = voltage_warnings(clean(doc))
    assert sorted(w.path for w in warned) == sorted(
        [path_of(doc, "T12"), path_of(doc, "T23")]
    )


@pytest.mark.tc("TC-VAL-027")
def test_voltage_mismatch_at_source_contactor():
    doc = fx("FX-SINGLE")
    find(doc, "G1")["voltage"] = 200
    warned = voltage_warnings(clean(doc))
    assert [w.path for w in warned] == [path_of(doc, "C_G1")]


def no_feed_warnings(result):
    return [w for w in result.warnings if "no possible feed" in w.message]


@pytest.mark.tc("TC-VAL-028")
def test_source_with_no_contactor_warns():
    doc = fx("FX-EMPTY")
    result = clean(doc)
    assert len(warnings_at(result, path_of(doc, "G2"))) == 1
    assert no_feed_warnings(result) == []


@pytest.mark.tc("TC-VAL-028")
def test_bus_with_no_contactor_warns():
    doc = fx("FX-SINGLE")
    doc["buses"].append(ac("AC9"))
    warned = no_feed_warnings(clean(doc))
    assert [w.path for w in warned] == [path_of(doc, "AC9")]


@pytest.mark.tc("TC-VAL-028")
def test_bus_behind_open_tie_has_a_feed():
    doc = fx("FX-SINGLE")
    doc["buses"].append(ac("AC8"))
    doc["contactors"].append(tie("T8", "AC1", "AC8", "open"))
    assert no_feed_warnings(clean(doc)) == []


@pytest.mark.tc("TC-VAL-028")
def test_tru_passes_nothing_from_dc_to_ac():
    doc = fx("FX-BAT")
    t = tru("TRU7", "AC7", "DCB")
    doc["buses"].append(ac("AC7"))
    doc["trus"].append(t)
    doc["contactors"] += tru_contactors(t)
    warned = no_feed_warnings(clean(doc))
    assert [w.path for w in warned] == [path_of(doc, "AC7")]


@pytest.mark.tc("TC-VAL-029")
@pytest.mark.parametrize(
    "swapped", [["TRU1_IN"], ["TRU1_OUT"], ["TRU1_IN", "TRU1_OUT"]], ids="+".join
)
def test_tru_contactor_role_comes_from_its_bus(swapped):
    doc = fx("FX-SINGLE")
    for element in swapped:
        swap(find(doc, element))
    clean(doc)


@pytest.mark.tc("TC-VAL-030")
@pytest.mark.parametrize("source, value", [("BAT", "AC"), ("G1", "DC"), ("APU", "DC")])
def test_source_output_must_suit_kind(source, value):
    doc = fx("FX-ALLKINDS")
    find(doc, source)["output"] = value
    path = f"{path_of(doc, source)}.output"
    assert len(errors_at(validate(doc), path)) == 1


@pytest.mark.tc("TC-VAL-030")
def test_battery_output_ac_on_a_dc_bus_gives_both_errors():
    doc = fx("FX-ALLKINDS")
    find(doc, "BAT")["output"] = "AC"
    result = validate(doc)
    assert len(result.errors) == 2
    assert errors_at(result, f"{path_of(doc, 'BAT')}.output")
    assert errors_at(result, path_of(doc, "C_BAT"))


@pytest.mark.tc("TC-VAL-030")
@pytest.mark.parametrize("source, bus", [("BAT", "AC"), ("G1", "DC"), ("APU", "DC")])
def test_wrong_output_on_a_matching_bus_is_one_error(source, bus):
    doc = fx("FX-ALLKINDS")
    find(doc, source)["output"] = bus
    find(doc, f"C_{source}")["to"] = "AC1" if bus == "AC" else "DC1"
    result = validate(doc)
    assert [e.path for e in result.errors] == [f"{path_of(doc, source)}.output"]


@pytest.mark.tc("TC-VAL-030")
def test_emergency_generator_takes_either_output():
    clean(fx("FX-RAT"))


@pytest.mark.tc("TC-VAL-031")
@pytest.mark.parametrize("name", ["FX-SINGLE", "FX-EMPTY"])
def test_no_essential_load_warns(name):
    result = clean(fx(name))
    assert len(warnings_at(result, "$.loads")) == 1
    assert result.definition is not None


@pytest.mark.tc("TC-VAL-031")
def test_one_essential_load_silences_the_warning():
    assert clean(fx("FX-SINGLE-E")).warnings == []


@pytest.mark.tc("TC-VAL-032")
def test_entry_point_and_result_fields():
    good = ela.validate.validate(fx("FX-SINGLE-E"))
    assert good.errors == []
    assert good.definition is not None

    bad = ela.validate.validate(fx("FX-THREEERR"))
    assert {e.path for e in bad.errors} == {
        "$.loads[0].power",
        "$.trus[0].efficiency",
        "$.loads[1].bus",
    }
    assert bad.warnings == []
    assert all(e.path and e.message for e in bad.errors)
    assert bad.definition is None
