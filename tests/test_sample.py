"""C-SAMPLE cases from docs/test-cases.md, run on definitions/generic_twin.json.

FX-SAMPLE rules apply: engine generators are found by `kind` and `engine`, buses by name, and never
by an assumed id. Expected figures come from tools/hand_calc_sample.py, which shares no code with
`ela`, through tests/data/generic_twin_expected.json.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

from ela.engine import analyse
from ela.model import BAND_NAMES
from ela.validate import validate

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "definitions" / "generic_twin.json"
EXPECTED = ROOT / "tests" / "data" / "generic_twin_expected.json"
HAND_CALC = ROOT / "tools" / "hand_calc_sample.py"

BUS_TYPES = {
    "AC BUS 1": "AC",
    "AC BUS 2": "AC",
    "AC ESS": "AC",
    "DC BUS 1": "DC",
    "DC BUS 2": "DC",
    "DC ESS": "DC",
    "DC BAT": "DC",
}
LIVE = ("operative", "available")

DOC = json.loads(SAMPLE.read_text("utf-8"))
DEFN = validate(DOC).definition
HAND = json.loads(EXPECTED.read_text("utf-8"))["scenarios"]


def sources(kind):
    return [s for s in DOC["sources"] if s["kind"] == kind]


def generator(engine):
    return next(s for s in sources("engine_generator") if s["engine"] == engine)


def bus(name):
    return next(b for b in DOC["buses"] if name in b["name"])


def ac_buses():
    return [b for b in DOC["buses"] if b["type"] == "AC"]


def state(scenario, element):
    """A component's state in a scenario: its entry, otherwise its default."""
    return scenario["states"].get(element["id"], element["default_state"])


def is_live(scenario, source):
    return state(scenario, source) in LIVE


def engines_failed(scenario):
    return [not is_live(scenario, s) for s in sources("engine_generator")]


def no_emergency_live(scenario):
    return not any(is_live(scenario, s) for s in sources("emergency_generator"))


def run(scenario):
    return analyse(DEFN, scenario["states"])


def rat_only():
    return next(
        s
        for s in DOC["scenarios"]
        if all(engines_failed(s))
        and not is_live(s, sources("apu_generator")[0])
        and not no_emergency_live(s)
    )


def battery_only():
    return next(
        s
        for s in DOC["scenarios"]
        if all(engines_failed(s))
        and not is_live(s, sources("apu_generator")[0])
        and no_emergency_live(s)
    )


def designed_to_fail():
    return [s for s in DOC["scenarios"] if "designed to fail" in s.get("description", "")]


def assert_bands(actual, expected):
    """A per-band record against the hand figure. None means the element carries no figure."""
    if expected is None:
        assert all(actual[band] is None for band in BAND_NAMES)
        return
    for band in BAND_NAMES:
        assert actual[band] == pytest.approx(expected[band], abs=1e-6), band


@pytest.mark.tc("TC-SMP-001")
def test_sample_is_valid():
    assert SAMPLE.exists()
    result = validate(DOC)
    assert result.errors == []
    assert result.warnings == []
    assert "twin" in DOC["meta"]["aircraft"].lower()


@pytest.mark.tc("TC-SMP-002")
def test_sample_sources():
    assert len(sources("engine_generator")) == 2
    assert len(sources("apu_generator")) == 1
    assert len([s for s in sources("emergency_generator") if s["output"] == "AC"]) >= 1
    assert len(sources("battery")) == 1


@pytest.mark.tc("TC-SMP-003")
def test_sample_buses_and_crew_switch():
    for name, bus_type in BUS_TYPES.items():
        matches = [b for b in DOC["buses"] if name in b["name"]]
        assert len(matches) == 1, name
        assert matches[0]["type"] == bus_type
    assert bus("DC BAT")["crew_switch"] is True


@pytest.mark.tc("TC-SMP-004")
def test_sample_trus():
    assert len(DOC["trus"]) == 3
    assert len([t for t in DOC["trus"] if t["output_bus"] == bus("DC ESS")["id"]]) == 1


@pytest.mark.tc("TC-SMP-005")
def test_sample_contactors():
    contactors = DOC["contactors"]
    fed = [c["from"] for c in contactors if c["kind"] == "source"]
    assert all(s["id"] in fed for s in DOC["sources"])

    tru_ends = [{c["from"], c["to"]} for c in contactors if c["kind"] == "tru"]
    for tru in DOC["trus"]:
        assert tru_ends.count({tru["input_bus"], tru["id"]}) == 1
        assert tru_ends.count({tru["id"], tru["output_bus"]}) == 1

    ties = [{c["from"], c["to"]} for c in contactors if c["kind"] == "bus_tie"]
    assert {bus("AC BUS 1")["id"], bus("AC BUS 2")["id"]} in ties
    ess = bus("AC ESS")["id"]
    assert {bus("AC BUS 1")["id"], ess} in ties or {bus("AC BUS 2")["id"], ess} in ties
    assert any(bus("DC ESS")["id"] in tie for tie in ties)
    assert any(bus("DC BAT")["id"] in tie for tie in ties)


@pytest.mark.tc("TC-SMP-006")
def test_sample_counts_and_band_pattern():
    assert 40 <= len(DOC["loads"]) <= 60
    assert 10 <= len(DOC["scenarios"]) <= 15
    for load in DOC["loads"]:
        power = load["power"]
        assert power["transient"] >= power["short_term"] >= power["continuous"] > 0, load["id"]


@pytest.mark.tc("TC-SMP-007")
def test_a_load_on_every_named_bus():
    loaded = {load["bus"] for load in DOC["loads"]}
    for name in BUS_TYPES:
        assert bus(name)["id"] in loaded, name


@pytest.mark.tc("TC-SMP-008")
def test_essential_loads_reachable_on_battery_only():
    essential = [load for load in DOC["loads"] if load.get("essential")]
    assert essential
    assert any(load["bus"] == bus("DC BAT")["id"] for load in essential)
    result = run(battery_only())
    assert all(result.el[load["bus"]].energised for load in essential)
    assert not any(result.el[b["id"]].energised for b in ac_buses())


@pytest.mark.tc("TC-SMP-009")
def test_normal_scenario():
    normal = [s for s in DOC["scenarios"] if not any(engines_failed(s)) and no_emergency_live(s)]
    assert any(run(s).verdict == "PASS" for s in normal)


@pytest.mark.tc("TC-SMP-010")
def test_each_single_generator_loss():
    for lost, kept in ((1, 2), (2, 1)):
        assert any(
            not is_live(s, generator(lost)) and is_live(s, generator(kept))
            for s in DOC["scenarios"]
        )


@pytest.mark.tc("TC-SMP-011")
def test_apu_only_scenario():
    apu = sources("apu_generator")[0]
    scenario = next(s for s in DOC["scenarios"] if all(engines_failed(s)) and is_live(s, apu))
    demand = run(scenario).el[apu["id"]].demand
    assert all(demand[band] > 0 for band in BAND_NAMES)
    assert no_emergency_live(scenario)


@pytest.mark.tc("TC-SMP-012")
def test_one_generator_plus_apu_loss():
    apu = sources("apu_generator")[0]
    assert any(
        state(s, apu) == "failed"
        and sum(state(s, g) == "failed" for g in sources("engine_generator")) == 1
        for s in DOC["scenarios"]
    )


@pytest.mark.tc("TC-SMP-013")
def test_each_tru_fails_somewhere():
    for tru in DOC["trus"]:
        assert any(s["states"].get(tru["id"]) == "failed" for s in DOC["scenarios"]), tru["id"]


@pytest.mark.tc("TC-SMP-014")
def test_rat_only_scenario():
    scenario = rat_only()
    result = run(scenario)
    output = next(s for s in sources("emergency_generator") if is_live(scenario, s))
    assert all(result.el[output["id"]].demand[band] > 0 for band in BAND_NAMES)
    assert any(result.el[b["id"]].energised for b in ac_buses())


@pytest.mark.tc("TC-SMP-015")
def test_battery_only_scenario():
    result = run(battery_only())
    battery = sources("battery")[0]["id"]
    assert all(result.el[battery].demand[band] > 0 for band in BAND_NAMES)
    assert not any(result.el[b["id"]].energised for b in ac_buses())


@pytest.mark.tc("TC-SMP-016")
def test_designed_overload_scenario():
    results = [run(s) for s in designed_to_fail()]
    assert any(r.verdict == "FAIL" and r.overloads and not r.config_errors for r in results)


@pytest.mark.tc("TC-SMP-017")
def test_designed_essential_load_scenario():
    results = [run(s) for s in designed_to_fail()]
    assert any(
        r.verdict == "FAIL" and r.unpowered and not r.overloads and not r.config_errors
        for r in results
    )


@pytest.mark.tc("TC-SMP-018")
def test_failures_are_exactly_the_designed_ones():
    designed = {s["id"] for s in designed_to_fail()}
    for scenario in DOC["scenarios"]:
        wanted = "FAIL" if scenario["id"] in designed else "PASS"
        assert run(scenario).verdict == wanted, scenario["id"]


@pytest.mark.tc("TC-SMP-019")
def test_sample_default_configuration():
    result = analyse(DEFN, {})
    assert result.verdict == "PASS"
    assert result.config_errors == []
    assert not any("AC sources paralleled" in e for e in result.config_errors)
    for source in sources("emergency_generator"):
        assert result.el[source["id"]].state == "unavailable"


@pytest.mark.tc("TC-SMP-020")
def test_scenarios_list_the_contactor_changes_they_need():
    scenario = rat_only()
    contactors = {c["id"] for c in DOC["contactors"]}
    assert contactors & set(scenario["states"])
    result = run(scenario)
    assert any(result.el[b["id"]].energised for b in ac_buses())

    without = {k: v for k, v in scenario["states"].items() if k not in contactors}
    assert analyse(DEFN, without).to_dict() != result.to_dict()


@pytest.mark.tc("TC-SMP-021")
def test_scenarios_list_only_differences():
    defaults = {b["id"]: "on" for b in DOC["buses"] if b.get("crew_switch")}
    for group in ("sources", "trus", "contactors"):
        defaults |= {e["id"]: e["default_state"] for e in DOC[group]}
    for scenario in DOC["scenarios"]:
        for element, value in scenario["states"].items():
            assert value != defaults[element], (scenario["id"], element)


@pytest.mark.tc("TC-SMP-022")
def test_expected_file_covers_exactly_the_scenarios():
    assert set(HAND) == {s["id"] for s in DOC["scenarios"]}
    for scenario_id, hand in HAND.items():
        assert hand["result"] in ("PASS", "FAIL"), scenario_id
        assert set(hand["sources"]) == {s["id"] for s in DOC["sources"]}


@pytest.mark.tc("TC-SMP-022")
def test_hand_calculation_is_independent_and_current():
    tree = ast.parse(HAND_CALC.read_text("utf-8"))
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert "ela" not in imported

    check = subprocess.run(
        [sys.executable, str(HAND_CALC), "--check"], capture_output=True, text=True, check=False
    )
    assert check.returncode == 0, check.stdout + check.stderr


@pytest.mark.tc("TC-SMP-022")
@pytest.mark.parametrize("scenario", DOC["scenarios"], ids=lambda s: s["id"])
def test_matches_hand_calculation(scenario):
    hand = HAND[scenario["id"]]
    result = run(scenario)

    assert result.verdict == hand["result"]
    assert result.worst.element == hand["worst_element"]
    assert result.worst.band == hand["worst_band"]
    assert result.worst.margin_pct == pytest.approx(hand["smallest_margin_pct"], abs=1e-6)
    assert len(result.overloads) == hand["overloads"]
    assert len(result.config_errors) == hand["configuration_errors"]
    assert len(result.unpowered) == hand["unpowered_essential"]
    assert result.warnings == []
    assert result.checked == hand["checked"]

    details = {(o.element, o.band): o for o in result.overloads}
    assert set(details) == {(d["element"], d["band"]) for d in hand["overload_details"]}
    for detail in hand["overload_details"]:
        overload = details[detail["element"], detail["band"]]
        assert overload.demand_with_margin == pytest.approx(detail["demand_with_margin"], abs=1e-6)
        assert overload.capacity == detail["capacity"]
    assert [u.id for u in result.unpowered] == hand["unpowered_details"]
    for source in hand["paralleled_sources"]:
        assert "AC sources paralleled" in result.config_errors[0]
        assert source in result.config_errors[0]

    for id_, figures in hand["sources"].items():
        assert_bands(result.el[id_].demand, figures["demand"])
        assert_bands(result.el[id_].capacity, figures["capacity"])
    for id_, figures in hand["trus"].items():
        assert_bands(result.el[id_].output, figures["output"])
        assert_bands(result.el[id_].input, figures["input"])
        assert_bands(result.el[id_].capacity, figures["capacity"])
    for id_, figures in hand["buses"].items():
        record = result.el[id_]
        assert record.energised == figures["energised"], id_
        assert_bands(record.own, figures["own"])
        assert_bands(record.demand, figures["demand"])
        assert_bands(record.current, figures["current"])
        assert_bands(record.capacity, figures["capacity"])
    for id_, figures in hand["ties"].items():
        assert_bands(result.el[id_].demand, figures["demand"])
        assert_bands(result.el[id_].capacity, figures["capacity"])


@pytest.mark.meta
@pytest.mark.tc("TC-SMP-022")
def test_every_scenario_has_a_passing_test():
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-m", "not meta", "-v", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert out.returncode == 0, out.stdout[-2000:]
    for scenario in DOC["scenarios"]:
        pattern = rf"test_matches_hand_calculation\[{scenario['id']}\] PASSED"
        assert re.search(pattern, out.stdout), scenario["id"]
