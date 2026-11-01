"""C-ENGINE cases from docs/test-cases.md, except the meta case TC-ENG-072.

Expected figures are the hand-worked values in the case text.
"""

import copy
import dataclasses
import inspect
import itertools
import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import (
    BANDS,
    D,
    ac,
    bat,
    c,
    dc,
    definition,
    find,
    fx,
    fx_rat_ac_only,
    gen,
    load,
    near,
    pick,
    run,
    setp,
    swap,
    tie,
    tri,
    triple,
    tru,
    tru_contactors,
)

import ela.engine
from ela.batch import run_batch
from ela.engine import analyse
from ela.validate import validate

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "definitions" / "generic_twin.json"


def configurations():
    """(document, states) over several scenarios, for the cases written against FX-SAMPLE.

    The sample is read unconditionally, so these cases fail rather than shrink if it goes missing.
    The other fixtures add configurations the sample does not have.
    """
    docs = [
        fx("FX-BATCH"),
        fx("FX-ALLKINDS"),
        fx("FX-BAT"),
        fx("FX-CREW"),
        json.loads(SAMPLE.read_text("utf-8")),
    ]
    for doc in docs:
        yield doc, {}
        for s in doc["scenarios"]:
            yield doc, s["states"]


def energised(result, *ids):
    return [result.el[i].energised for i in ids]


def overloads(result):
    return {(o.element, o.band) for o in result.overloads}


def meshed(result):
    return [w for w in result.warnings if w.code == "meshed_island"]


def island_of(result, bus):
    return next(i for i in result.islands if bus in i.buses)


def add_source(doc, source, bus):
    doc["sources"].append(source)
    doc["contactors"].append(c(source["id"], bus))
    return doc


# --- Energisation ---


@pytest.mark.tc("TC-ENG-001")
def test_state_map_over_defaults():
    doc = fx("FX-ALLKINDS")
    result = run(doc, {"G1": "failed"})
    assert result.el["G1"].state == "failed"
    for item in doc["sources"] + doc["trus"] + doc["contactors"]:
        if item["id"] != "G1":
            assert result.el[item["id"]].state == item["default_state"]
    assert result.el["C_APU"].state == "open"
    assert result.el["RAT_AC"].state == "unavailable"


@pytest.mark.tc("TC-ENG-002")
def test_crew_switch_default():
    assert run(fx("FX-CREW")).el["DCS"].state == "on"
    assert run(fx("FX-CREW"), {"DCS": "off"}).el["DCS"].state == "off"


@pytest.mark.tc("TC-ENG-003")
def test_only_live_sources_are_energised():
    assert energised(run(fx("FX-SINGLE"), {"G1": "failed"}), "G1", "AC1") == [False, False]
    assert energised(run(fx("FX-RAT")), "RAT_AC", "ACE") == [False, False]
    result = run(fx("FX-RAT"), {"RAT_AC": "available"})
    assert energised(result, "RAT_AC", "ACE") == [True, True]
    assert energised(result, "RAT_DC", "DCE") == [False, False]


@pytest.mark.tc("TC-ENG-073")
def test_live_source_energised_with_contactors_open():
    result = run(fx("FX-APU"))
    assert result.el["APU"].energised is True
    assert result.el["C_APU"].state == "open"
    assert run(fx("FX-APU"), {"APU": "failed"}).el["APU"].energised is False
    result = run(fx("FX-APU"), {"G1": "failed"})
    assert energised(result, "APU", "AC1") == [True, False]
    result = run(fx("FX-RAT"), {"RAT_AC": "available", "C_RAT_AC": "open"})
    assert energised(result, "RAT_AC", "ACE") == [True, False]


@pytest.mark.tc("TC-ENG-004")
@pytest.mark.parametrize(
    "states, expected",
    [
        ({}, [True, True, True]),
        ({"T23": "open"}, [True, True, False]),
        ({"T12": "open"}, [True, False, False]),
        ({"C_G1": "open"}, [False, False, False]),
    ],
)
def test_bus_energised_by_a_closed_path(states, expected):
    assert energised(run(fx("FX-CHAIN"), states), "AC1", "AC2", "AC3") == expected


@pytest.mark.tc("TC-ENG-005")
@pytest.mark.parametrize("swapped", [False, True])
def test_contactors_are_bidirectional(swapped):
    doc = fx("FX-CHAIN")
    if swapped:
        swap(find(doc, "T12"))
    assert energised(run(doc), "AC1", "AC2", "AC3") == [True, True, True]
    assert energised(run(doc, {"T12": "open"}), "AC1", "AC2", "AC3") == [True, False, False]

    find(doc, "C_G1")["to"] = "AC3"
    assert energised(run(doc), "AC1", "AC2", "AC3") == [True, True, True]
    assert energised(run(doc, {"T12": "open"}), "AC1", "AC2", "AC3") == [False, True, True]


@pytest.mark.tc("TC-ENG-005")
def test_swapped_tru_input_stays_the_input():
    doc = fx("FX-SINGLE")
    swap(find(doc, "TRU1_IN"))
    result = run(doc)
    assert D(result, "TRU1_IN") == near((2000, 1600, 1000))
    assert result.el["TRU1"].energised is True


@pytest.mark.tc("TC-ENG-006")
@pytest.mark.parametrize(
    "tru_state, gen_state, contactor_state",
    list(itertools.product(("operative", "failed"), ("operative", "failed"), ("closed", "open"))),
)
def test_tru_energisation_truth_table(tru_state, gen_state, contactor_state):
    states = {"TRU1": tru_state, "G1": gen_state, "TRU1_IN": contactor_state}
    expected = (tru_state, gen_state, contactor_state) == ("operative", "operative", "closed")
    assert run(fx("FX-SINGLE"), states).el["TRU1"].energised is expected


@pytest.mark.tc("TC-ENG-006")
def test_tru_stays_energised_with_output_open():
    assert run(fx("FX-SINGLE"), {"TRU1_OUT": "open"}).el["TRU1"].energised is True


@pytest.mark.tc("TC-ENG-007")
def test_energisation_does_not_pass_from_dc_to_ac():
    result = run(fx("FX-BAT"), {"G1": "failed"})
    assert energised(result, "DC1", "DCB") == [True, True]
    assert energised(result, "TRU1", "AC1") == [False, False]
    assert (result.el["TRU1_IN"].state, result.el["TRU1_OUT"].state) == ("closed", "closed")


@pytest.mark.tc("TC-ENG-008")
def test_failed_source_does_not_bridge_buses():
    result = run(fx("FX-SRCBRIDGE"), {"G1": "failed", "G2": "operative"})
    assert energised(result, "AC1", "AC2") == [True, False]


@pytest.mark.tc("TC-ENG-009")
def test_closed_contactor_to_a_failed_generator_on_a_live_bus_is_energised():
    result = run(fx("FX-SRCBRIDGE"))
    assert energised(result, "G2", "AC1", "C_G2") == [False, True, True]
    assert D(result, "C_G2") == near(0)
    assert energised(run(fx("FX-SRCBRIDGE"), {"G1": "failed"}), "AC1", "C_G2") == [False, False]


@pytest.mark.tc("TC-ENG-009")
def test_contactor_energisation():
    assert run(fx("FX-CHAIN"), {"T23": "open"}).el["T12"].energised is True
    assert run(fx("FX-CHAIN"), {"C_G1": "open"}).el["T12"].energised is False

    doc = add_source(fx("FX-CHAIN"), gen(2, 20000), "AC3")
    result = run(doc, {"T23": "open"})
    assert energised(result, "AC2", "AC3") == [True, True]
    assert result.el["T23"].energised is False


# --- Demand ---


@pytest.mark.tc("TC-ENG-010")
def test_own_load_is_a_lossless_sum():
    doc = definition(
        [gen(1, 2000)],
        [ac("AC1")],
        [],
        [c("G1", "AC1")],
        [load("L1", "AC1", 100), load("L2", "AC1", 250)],
    )
    assert triple(run(doc).el["AC1"].own) == near(350)
    assert triple(run(fx("FX-MARGIN")).el["AC1"].own) == (1000, 1000, 1000)


@pytest.mark.tc("TC-ENG-011")
def test_dead_bus_counts_no_load():
    record = run(fx("FX-MARGIN"), {"C_G1": "open"}).el["AC1"]
    assert triple(record.own) == (0, 0, 0)
    assert triple(record.demand) == (None, None, None)


@pytest.mark.tc("TC-ENG-012")
def test_crew_switch_off_zeroes_own_loads_only():
    on = run(fx("FX-CREW"))
    assert triple(on.el["DCS"].own) == near((200, 150, 100))
    assert D(on, "DCS") == near((500, 400, 300))
    assert D(on, "BAT") == near((500, 400, 300))

    off = run(fx("FX-CREW"), {"DCS": "off"})
    assert off.el["DCS"].energised is True
    assert triple(off.el["DCS"].own) == (0, 0, 0)
    assert D(off, "DCS") == near((300, 250, 200))
    assert D(off, "BAT") == near((300, 250, 200))
    assert triple(off.el["DCX"].own) == near((300, 250, 200))


@pytest.mark.tc("TC-ENG-013")
def test_load_power_unchanged_across_scenarios():
    for doc, states in configurations():
        result = run(doc, states)
        for bus in doc["buses"]:
            record = result.el[bus["id"]]
            if record.energised and record.state != "off":
                loads = [x for x in doc["loads"] if x["bus"] == bus["id"]]
                total = tuple(sum(x["power"][b] for x in loads) for b in BANDS)
                assert triple(record.own) == near(total)


@pytest.mark.tc("TC-ENG-014")
def test_tru_loss_chain():
    result = run(fx("FX-SINGLE"))
    assert triple(result.el["TRU1"].output) == near((1700, 1360, 850))
    assert triple(result.el["TRU1"].input) == near((2000, 1600, 1000))
    assert D(result, "G1") == near((4000, 3100, 2000))


@pytest.mark.tc("TC-ENG-015")
def test_efficiency_of_one():
    result = run(setp(fx("FX-SINGLE"), "$.trus[0].efficiency", 1.0))
    assert triple(result.el["TRU1"].input) == near((1700, 1360, 850))
    assert triple(result.el["TRU1"].output) == near((1700, 1360, 850))
    assert D(result, "G1") == near((3700, 2860, 1850))


@pytest.mark.tc("TC-ENG-016")
def test_throughput_with_own_load_separate():
    result = run(fx("FX-THROUGH"))
    assert D(result, "AC1") == near((3900, 3300, 2500))
    assert triple(result.el["AC1"].own) == near((1200, 1100, 1000))
    assert D(result, "AC2") == near((700, 600, 500))
    assert triple(result.el["AC2"].own) == near((700, 600, 500))


@pytest.mark.tc("TC-ENG-017")
def test_feeding_bus_overloads_on_throughput():
    doc = fx("FX-THROUGH")
    find(doc, "AC1")["capacity"] = tri(4000)
    result = run(doc)
    assert triple(result.el["AC1"].with_margin) == near((4290, 3630, 2750))
    assert overloads(result) == {("AC1", "transient")}
    assert triple(result.el["AC1"].margin_w) == near((-290, 370, 1250))
    assert triple(result.el["AC1"].margin_pct) == near((-7.25, 9.25, 31.25))


# --- Flow ---


@pytest.mark.tc("TC-ENG-018")
def test_islands_split_at_trus():
    doc = fx("FX-SINGLE")
    doc["buses"].append(ac("AC2"))
    add_source(doc, gen(2, 5000), "AC2")

    result = run(doc)
    assert len(result.islands) == 3
    assert (island_of(result, "AC1").buses, island_of(result, "AC1").sources) == (["AC1"], ["G1"])
    assert (island_of(result, "AC2").buses, island_of(result, "AC2").sources) == (["AC2"], ["G2"])
    assert island_of(result, "DC1").buses == ["DC1"]

    result = run(doc, {"G2": "failed"})
    assert island_of(result, "AC2").sources == []


@pytest.mark.tc("TC-ENG-019")
def test_tie_flow_on_a_chain():
    result = run(fx("FX-CHAIN"))
    assert D(result, "T12") == near(500)
    assert D(result, "T23") == near(300)
    assert D(result, "AC1") == near(600)
    assert D(result, "G1") == near(600)
    assert D(result, "AC2") == near(500)
    assert D(result, "AC3") == near(300)


@pytest.mark.tc("TC-ENG-019")
def test_tie_flow_includes_tru_input_in_the_cut_set():
    result = run(fx("FX-THROUGH"))
    assert D(result, "T12") == near((700, 600, 500))
    assert D(result, "G1") == near((3900, 3300, 2500))

    doc = fx("FX-THROUGH")
    find(doc, "TRU1")["input_bus"] = "AC2"
    find(doc, "TRU1_IN")["from"] = "AC2"
    result = run(doc)
    assert D(result, "T12") == near((2700, 2200, 1500))
    assert D(result, "G1") == near((3900, 3300, 2500))


def _swap_tru_ids(doc):
    """Exchange the ids TRU_A and TRU_B everywhere, so the tree root moves to the other bus."""
    exchange = {"TRU_A": "TRU_B", "TRU_B": "TRU_A"}
    for t in doc["trus"]:
        t["id"] = exchange[t["id"]]
    for x in doc["contactors"]:
        for key in ("id", "from", "to"):
            head = x[key][:5]
            if head in exchange:
                x[key] = exchange[head] + x[key][5:]
    return doc


@pytest.mark.tc("TC-ENG-020")
@pytest.mark.parametrize("swapped", [False, True])
def test_tie_with_equal_trus_at_both_ends(swapped):
    doc = fx("FX-TIE-EQ")
    if swapped:
        _swap_tru_ids(doc)
    result = run(doc)
    assert D(result, "TRU_A") == near(200)
    assert D(result, "TRU_B") == near(200)
    assert triple(result.el["TRU_A"].input) == near(250)
    assert D(result, "T_DC") == near(100)
    assert D(result, "DCA") == near(300)
    assert D(result, "DCB") == near(200)
    assert D(result, "G1") == near(250)
    assert D(result, "G2") == near(250)


@pytest.mark.tc("TC-ENG-021")
def test_tie_with_flow_toward_the_root():
    result = run(fx("FX-TIE-DC"))
    assert D(result, "TRU1") == near(600)
    assert D(result, "TRU2") == near(300)
    assert D(result, "T_DC") == near(200)
    assert D(result, "DC1") == near(800)
    assert D(result, "DC2") == near(300)


@pytest.mark.tc("TC-ENG-021")
def test_tie_with_flow_away_from_the_root():
    doc = fx("FX-TIE-DC")
    find(doc, "LD1")["power"] = tri(300)
    find(doc, "LD2")["power"] = tri(600)
    result = run(doc)
    assert D(result, "T_DC") == near(300)
    assert D(result, "DC1") == near(600)
    assert D(result, "DC2") == near(600)


@pytest.mark.tc("TC-ENG-083")
def test_exact_flows_on_a_multi_source_meshed_island():
    doc = definition(
        [bat("BAT1", 2000), bat("BAT2", 1000)],
        [dc("D1"), dc("D2"), dc("D3")],
        [],
        [
            c("BAT1", "D1"),
            c("BAT2", "D2"),
            tie("T12", "D1", "D2"),
            tie("T13", "D1", "D3"),
            tie("T23", "D2", "D3"),
        ],
        [load("L", "D3", 900)],
    )
    result = run(doc)
    assert D(result, "BAT1") == near(600)
    assert D(result, "BAT2") == near(300)
    assert D(result, "C_BAT1") == near(600)
    assert D(result, "C_BAT2") == near(300)
    assert D(result, "T12") == near(300)
    assert D(result, "T13") == near(900)
    assert D(result, "T23") == near(0)
    assert D(result, "D1") == near(900)
    assert D(result, "D2") == near(300)
    assert [w.element for w in meshed(result)] == ["T23"]


@pytest.mark.tc("TC-ENG-022")
def test_ring_spanning_tree():
    first = run(fx("FX-RING"))
    assert D(first, "T12") == near(200)
    assert D(first, "T13") == near(300)
    assert D(first, "T23") == near(0)
    assert D(first, "G1") == near(600)

    doc = fx("FX-RING")
    find(doc, "C_G1")["to"] = "AC2"
    second = run(doc)
    assert D(second, "T12") == near(100)
    assert D(second, "T23") == near(300)
    assert D(second, "T13") == near(0)
    assert D(second, "AC2") == near(600)

    doc = fx("FX-RING")
    for key in ("sources", "buses", "trus", "contactors", "loads", "scenarios"):
        doc[key].reverse()
    assert run(doc) == first


@pytest.mark.tc("TC-ENG-023")
@pytest.mark.parametrize("swapped", [False, True])
def test_parallel_ties(swapped):
    ties = [tie("TA", "AC1", "AC2"), tie("TB", "AC1", "AC2")]
    if swapped:
        ties.reverse()
    doc = definition(
        [gen(1, 20000)],
        [ac("AC1"), ac("AC2")],
        [],
        [c("G1", "AC1"), *ties],
        [load("L2", "AC2", 200)],
    )
    result = run(doc)
    assert D(result, "TA") == near(200)
    assert D(result, "TB") == near(0)
    assert [w.element for w in meshed(result)] == ["TB"]


@pytest.mark.tc("TC-ENG-074")
def test_neighbours_ordered_by_code_point():
    doc = definition(
        [gen(1, 20000)],
        [ac("B1"), ac("B10"), ac("B2"), ac("BX")],
        [],
        [
            c("G1", "B1"),
            tie("TA", "B1", "B10"),
            tie("TB", "B1", "B2"),
            tie("TC", "B10", "BX"),
            tie("TD", "B2", "BX"),
        ],
        [load("L", "BX", 100)],
    )
    result = run(doc)
    assert D(result, "TA") == near(100)
    assert D(result, "TC") == near(100)
    assert D(result, "TB") == near(0)
    assert D(result, "TD") == near(0)
    assert [w.element for w in meshed(result)] == ["TD"]


@pytest.mark.tc("TC-ENG-024")
def test_meshed_island_warning():
    result = run(fx("FX-RING"))
    assert [w.element for w in meshed(result)] == ["T23"]
    assert "T23" in meshed(result)[0].message
    assert result.verdict == "PASS"
    assert result.overloads == []
    assert meshed(run(fx("FX-CHAIN"))) == []


@pytest.mark.tc("TC-ENG-075")
@pytest.mark.parametrize("states", [{"G1": "failed"}, {"C_G1": "open"}])
def test_no_mesh_warning_on_a_dead_ring(states):
    result = run(fx("FX-RING"), states)
    assert meshed(result) == []
    island = island_of(result, "AC1")
    assert (island.buses, island.sources) == (["AC1", "AC2", "AC3"], [])


@pytest.mark.tc("TC-ENG-075")
def test_mesh_warning_on_a_paralleled_ring():
    doc = add_source(fx("FX-RING"), gen(2, 20000), "AC3")
    find(doc, "T12")["capacity"] = tri(1)  # no flow is attributed, so DD-026 has nothing to check
    find(doc, "AC2")["capacity"] = tri(100000)
    result = run(doc)
    assert [w.element for w in meshed(result)] == ["T23"]
    assert "T23" in meshed(result)[0].message
    assert D(result, "T12") == (None, None, None)
    assert D(result, "T23") == (None, None, None)
    assert D(result, "AC2") == near(200)  # DD-005: own loads alone, not the island total
    assert result.overloads == []
    assert len(result.config_errors) == 1
    message = result.config_errors[0]
    assert "AC sources paralleled" in message
    assert "G1" in message
    assert "G2" in message


@pytest.mark.tc("TC-ENG-025")
def test_loop_through_a_source_with_two_contactors():
    doc = fx("FX-SRCBRIDGE")
    doc["contactors"].append(tie("T_AB", "AC1", "AC2"))
    result = run(doc)
    assert [w.element for w in meshed(result)] == ["T_AB"]
    assert D(result, "C1A") == near(300)
    assert D(result, "C1B") == near(500)
    assert D(result, "T_AB") == near(0)


def ring_with_two_routes(rated, other, tie_capacity=None):
    """GEN feeds A. Ties A-r, r-C, C-o, o-A. 2000 W on C, margin 0, bus r capped at 1000 W."""
    generator = {**gen(1, 5000), "id": "GEN", "name": "GEN"}
    ties = [
        tie(f"T_A_{rated}", "A", rated),
        tie(f"T_{rated}_C", rated, "C"),
        tie(f"T_C_{other}", "C", other),
        tie(f"T_{other}_A", other, "A"),
    ]
    if tie_capacity is not None:
        ties[0]["capacity"] = tri(tie_capacity)
    return definition(
        [generator],
        [ac("A"), ac("C"), ac(rated, capacity=1000), ac(other)],
        [],
        [c("GEN", "A"), *ties],
        [load("L", "C", 2000)],
        margin=0,
    )


@pytest.mark.tc("TC-ENG-078")
@pytest.mark.parametrize("rated, other", [("B", "Z"), ("Z", "B")])
def test_rated_bus_on_a_loop_is_checked_against_the_island_total(rated, other):
    result = run(ring_with_two_routes(rated, other))
    assert result.verdict == "FAIL"
    assert overloads(result) == {(rated, band) for band in BANDS}
    assert D(result, rated) == near(2000)
    assert triple(result.el[rated].current) == near(2000 / 345)
    assert triple(result.el[rated].margin_pct) == near(-100)


@pytest.mark.tc("TC-ENG-078")
def test_swapping_ids_gives_identical_verdicts():
    first = run(ring_with_two_routes("B", "Z"))
    second = run(ring_with_two_routes("Z", "B"))
    assert first.verdict == second.verdict == "FAIL"
    assert [(o.band, o.demand_with_margin) for o in first.overloads] == [
        (o.band, o.demand_with_margin) for o in second.overloads
    ]
    assert first.worst.margin_pct == second.worst.margin_pct == -100


@pytest.mark.tc("TC-ENG-078")
@pytest.mark.parametrize("rated, other", [("B", "Z"), ("Z", "B")])
def test_rated_contactor_on_a_loop_is_checked_against_the_island_total(rated, other):
    doc = ring_with_two_routes(rated, other, tie_capacity=1500)
    find(doc, rated).pop("capacity")
    result = run(doc)
    assert overloads(result) == {(f"T_A_{rated}", band) for band in BANDS}
    assert D(result, f"T_A_{rated}") == near(2000)


@pytest.mark.tc("TC-ENG-078")
def test_island_total_holds_own_loads_and_tru_input_per_band():
    doc = fx("FX-RING")
    trus = [tru("TRU1", "AC2", "DC1", 0.80, 5000)]
    doc["buses"].append(dc("DC1"))
    doc["trus"] += trus
    doc["contactors"] += tru_contactors(trus[0])
    doc["loads"].append(load("LD", "DC1", (800, 400, 200)))
    find(doc, "AC1")["capacity"] = tri(100000)
    find(doc, "T23")["capacity"] = tri(100000)
    result = run(doc)
    # Own 100 + 200 + 300, plus TRU input 800 / 0.8, 400 / 0.8 and 200 / 0.8.
    assert D(result, "AC1") == near((1600, 1100, 850))
    assert D(result, "T23") == near((1600, 1100, 850))
    assert triple(result.el["AC1"].own) == near(100)


@pytest.mark.tc("TC-ENG-078")
def test_island_total_on_a_dc_loop_with_two_feeders():
    doc = definition(
        [bat("BAT1", 2000), bat("BAT2", 1000)],
        [dc("D1"), dc("D2"), dc("D3", capacity=500)],
        [],
        [
            c("BAT1", "D1"),
            c("BAT2", "D2"),
            tie("T12", "D1", "D2"),
            tie("T13", "D1", "D3"),
            tie("T23", "D2", "D3"),
        ],
        [load("L", "D3", 900)],
        margin=0,
    )
    result = run(doc)
    assert D(result, "D3") == near(900)
    assert overloads(result) == {("D3", band) for band in BANDS}


@pytest.mark.tc("TC-ENG-079")
def test_unrated_elements_keep_the_tree_flow():
    doc = fx("FX-RING")
    find(doc, "AC1")["capacity"] = tri(100000)
    result = run(doc)
    assert D(result, "AC1") == near(600)
    assert D(result, "AC2") == near(200)
    assert D(result, "AC3") == near(300)
    assert D(result, "T12") == near(200)
    assert D(result, "T13") == near(300)
    assert D(result, "T23") == near(0)


@pytest.mark.tc("TC-ENG-079")
def test_rated_elements_off_the_loop_keep_their_flow():
    doc = fx("FX-RING")
    doc["buses"].append(ac("AC4", capacity=100000))
    doc["contactors"].append(tie("T34", "AC3", "AC4", capacity=100000))
    doc["loads"].append(load("L4", "AC4", 400))
    find(doc, "C_G1")["capacity"] = tri(100000)
    result = run(doc)
    assert D(result, "T34") == near(400)
    assert D(result, "AC4") == near(400)
    assert D(result, "C_G1") == near(1000)
    assert [w.element for w in meshed(result)] == ["T23"]


@pytest.mark.tc("TC-ENG-079")
def test_a_rated_bus_is_not_on_a_loop_through_a_failed_source():
    doc = fx("FX-SRCBRIDGE")
    doc["contactors"].append(tie("T_AB", "AC1", "AC2", "open"))
    find(doc, "AC1")["capacity"] = tri(100000)
    assert D(run(doc), "AC1") == near(300)  # G1 alone joins the buses, so there is no loop
    assert meshed(run(doc, {"G1": "failed", "G2": "operative"})) == []


@pytest.mark.tc("TC-ENG-080")
def test_warning_names_each_rated_element_on_a_loop():
    doc = fx("FX-RING")
    find(doc, "AC2")["capacity"] = tri(100000)
    find(doc, "T12")["capacity"] = tri(100000)
    find(doc, "T23")["capacity"] = tri(100000)
    result = run(doc)
    assert [w.element for w in meshed(result)] == ["AC2", "T12", "T23"]
    for warning in meshed(result):
        assert warning.element in warning.message
    assert D(result, "T23") == near(600)
    assert result.verdict == "PASS"


@pytest.mark.tc("TC-ENG-080")
def test_parallel_rated_ties_are_both_on_a_loop():
    doc = definition(
        [gen(1, 20000)],
        [ac("AC1"), ac("AC2")],
        [],
        [c("G1", "AC1"), tie("TA", "AC1", "AC2", capacity=500), tie("TB", "AC1", "AC2", capacity=500)],
        [load("L2", "AC2", 200)],
    )
    result = run(doc)
    assert D(result, "TA") == near(200)
    assert D(result, "TB") == near(200)
    assert [w.element for w in meshed(result)] == ["TA", "TB"]


@pytest.mark.tc("TC-ENG-026")
def test_contactor_demand_on_tru_feeds():
    doc = fx("FX-SINGLE")
    doc["loads"] = [load("LD", "DC1", 850)]
    result = run(doc)
    assert D(result, "TRU1_OUT") == near(850)
    assert D(result, "TRU1_IN") == near(1000)
    assert D(result, "C_G1") == near(1000)


@pytest.mark.tc("TC-ENG-026")
def test_contactor_demand_on_a_split_source():
    result = run(fx("FX-SRCBRIDGE"))
    assert D(result, "C1A") == near(300)
    assert D(result, "C1B") == near(500)
    assert D(result, "G1") == near(800)


@pytest.mark.tc("TC-ENG-027")
def test_energised_tru_with_open_output_feeds_nothing():
    result = run(fx("FX-SINGLE"), {"TRU1_OUT": "open"})
    assert result.el["TRU1"].energised is True
    assert triple(result.el["TRU1"].input) == near(0)
    assert triple(result.el["TRU1"].output) == near(0)
    assert result.el["DC1"].energised is False
    assert D(result, "G1") == near((2000, 1500, 1000))
    assert D(result, "TRU1_IN") == near(0)


# --- Paralleling ---


@pytest.mark.tc("TC-ENG-028")
def test_paralleled_generators_give_one_named_error():
    result = run(fx("FX-PAR"))
    assert len(result.config_errors) == 1
    message = result.config_errors[0]
    assert "AC sources paralleled" in message
    assert "G1" in message
    assert "G2" in message
    assert result.verdict == "FAIL"


@pytest.mark.tc("TC-ENG-029")
def test_available_rat_closed_onto_a_live_bus():
    doc = add_source(fx_rat_ac_only(), gen(1, 5000), "ACE")
    result = run(doc, {"RAT_AC": "available"})
    assert len(result.config_errors) == 1
    message = result.config_errors[0]
    assert "AC sources paralleled" in message
    assert "RAT_AC" in message
    assert "G1" in message
    assert run(doc).config_errors == []


@pytest.mark.tc("TC-ENG-030")
def test_not_paralleled_when_isolated_or_failed():
    assert run(fx("FX-APU")).config_errors == []
    assert run(fx("FX-PAR"), {"G2": "failed"}).config_errors == []
    assert run(fx("FX-PAR"), {"C_G2": "open"}).config_errors == []


@pytest.mark.tc("TC-ENG-031")
def test_paralleled_island_figures():
    result = run(fx("FX-PAR"))
    assert energised(result, "AC1", "AC2") == [True, True]
    assert triple(result.el["AC1"].own) == near(1000)
    assert triple(result.el["AC2"].own) == near(3000)
    assert D(result, "AC1") == near(1500)
    assert D(result, "AC2") == near(3000)


@pytest.mark.tc("TC-ENG-032")
def test_paralleled_sources_and_contactors_carry_no_demand():
    result = run(fx("FX-PAR"))
    for element in ("G1", "G2", "C_G1", "C_G2", "T12", "TRU1_IN"):
        assert D(result, element) == (None, None, None)
        assert element not in result.checked
    assert result.overloads == []


@pytest.mark.tc("TC-ENG-033")
@pytest.mark.parametrize("states", [{}, {"T12": "open"}])
def test_dc_downstream_of_a_paralleled_island(states):
    result = run(fx("FX-PAR"), states)
    assert D(result, "DC1") == near(400)
    assert triple(result.el["TRU1"].output) == near(400)
    assert "TRU1" in result.checked
    assert D(result, "TRU1_OUT") == near(400)
    assert triple(result.el["TRU1"].input) == near(500)


# --- DC sources ---


@pytest.mark.tc("TC-ENG-034")
def test_two_trus_share_by_continuous_capacity():
    result = run(fx("FX-TWO-TRU"))
    assert triple(result.el["TRU1"].output) == near((1200, 900, 600))
    assert triple(result.el["TRU2"].output) == near((600, 450, 300))
    assert triple(result.el["TRU1"].input) == near((1500, 1125, 750))
    assert triple(result.el["TRU2"].input) == near((800, 600, 400))
    assert D(result, "G1") == near((1500, 1125, 750))
    assert D(result, "G2") == near((800, 600, 400))


@pytest.mark.tc("TC-ENG-035")
def test_tru_and_dc_rat_share_with_the_battery_silent():
    result = run(fx("FX-TRU-RAT"))
    assert D(result, "TRU1") == near(600)
    assert D(result, "RAT_DC") == near(300)
    assert D(result, "BAT") == near(0)
    assert D(result, "G1") == near(750)


@pytest.mark.tc("TC-ENG-036")
def test_empty_island_and_zero_demand():
    result = run(fx("FX-EMPTY"))
    for element in ("G1", "AC1", "TRU1", "DC1"):
        assert D(result, element) == near(0)
    assert triple(result.el["DC1"].current) == near(0)
    assert triple(result.el["G1"].margin_pct) == near(100)
    assert result.el["AC2"].energised is False
    assert result.verdict == "PASS"

    doc = fx("FX-TWO-TRU")
    find(doc, "LD")["power"] = tri(0)
    result = run(doc)
    assert D(result, "TRU1") == near(0)
    assert D(result, "TRU2") == near(0)


@pytest.mark.tc("TC-ENG-037")
def test_zero_total_capacity_splits_equally():
    doc = fx("FX-TWO-TRU")
    find(doc, "TRU1")["capacity"] = tri(0)
    find(doc, "TRU2")["capacity"] = tri(0)
    find(doc, "LD")["power"] = tri(900)
    result = run(doc)
    assert D(result, "TRU1") == near(450)
    assert D(result, "TRU2") == near(450)
    assert {element for element, _ in overloads(result)} == {"TRU1", "TRU2"}


@pytest.mark.tc("TC-ENG-038")
def test_battery_silent_while_a_tru_feeds():
    result = run(fx("FX-BAT"))
    assert D(result, "BAT") == near(0)
    assert triple(result.el["TRU1"].output) == near(850)
    assert triple(result.el["TRU1"].input) == near(1000)
    assert D(result, "G1") == near(1000)
    assert D(result, "T_B") == near(510)
    assert D(result, "DC1") == near(850)
    assert D(result, "DCB") == near(510)


@pytest.mark.tc("TC-ENG-038")
def test_battery_supplies_when_the_tru_is_lost():
    result = run(fx("FX-BAT"), {"TRU1": "failed"})
    assert D(result, "BAT") == near(850)
    assert D(result, "C_BAT") == near(850)
    assert D(result, "T_B") == near(340)
    assert D(result, "DCB") == near(850)
    assert D(result, "DC1") == near(340)
    assert D(result, "G1") == near(0)


@pytest.mark.tc("TC-ENG-038")
def test_battery_alone_on_a_bus():
    doc = definition(
        [bat("BAT", (6000, 4500, 3000))],
        [dc("DC1")],
        [],
        [c("BAT", "DC1")],
        [load("L", "DC1", 500)],
    )
    assert D(run(doc), "BAT") == near(500)


@pytest.mark.tc("TC-ENG-039")
@pytest.mark.parametrize(
    "states",
    [{"TRU1": "failed"}, {"G1": "failed"}, {"TRU1_IN": "open"}, {"TRU1_OUT": "open"}],
)
def test_what_counts_as_feeding_the_island(states):
    assert D(run(fx("FX-BAT"), states), "BAT") == near(850)


@pytest.mark.tc("TC-ENG-039")
def test_tru_with_open_output_is_energised_and_battery_carries_all():
    result = run(fx("FX-BAT"), {"TRU1_OUT": "open"})
    assert result.el["TRU1"].energised is True
    assert D(result, "BAT") == near(850)


@pytest.mark.tc("TC-ENG-040")
def test_two_sole_batteries_share_by_continuous_capacity():
    result = run(fx("FX-BAT2"))
    assert D(result, "BAT1") == near(600)
    assert D(result, "BAT2") == near(200)

    assert D(run(fx("FX-BAT2"), {"BAT2": "failed"}), "BAT1") == near(800)

    doc = add_source(fx("FX-BAT2"), gen(1, 5000), "AC1")
    t = tru("TRU1", "AC1", "DC1", 0.85, 3000)
    doc["buses"].append(ac("AC1"))
    doc["trus"].append(t)
    doc["contactors"] += tru_contactors(t)
    result = run(doc)
    assert D(result, "BAT1") == near(0)
    assert D(result, "BAT2") == near(0)


@pytest.mark.tc("TC-ENG-041")
def test_no_negative_battery_demand():
    for doc, states in configurations():
        result = run(doc, states)
        for source in doc["sources"]:
            if source["kind"] == "battery":
                assert all(d is None or d >= 0 for d in D(result, source["id"]))


@pytest.mark.tc("TC-ENG-042")
def test_rat_outputs_have_no_combined_limit():
    result = run(fx("FX-RAT"), {"RAT_AC": "available", "RAT_DC": "available"})
    assert triple(result.el["RAT_AC"].with_margin) == near(4950)
    assert triple(result.el["RAT_DC"].with_margin) == near(2970)
    assert result.overloads == []


# --- Capacity check ---


@pytest.mark.tc("TC-ENG-043")
def test_margin_exactly_at_the_limit():
    result = run(fx("FX-MARGIN"))
    assert result.overloads == []
    assert triple(result.el["G1"].margin_w) == near(0)
    assert triple(result.el["G1"].margin_pct) == near(0)


@pytest.mark.tc("TC-ENG-043")
def test_just_over_the_limit():
    doc = fx("FX-MARGIN")
    find(doc, "L1")["power"] = tri(1001)
    assert {b for _, b in overloads(run(doc))} == set(BANDS)

    doc = fx("FX-MARGIN")
    find(doc, "G1")["capacity"] = tri(1099)
    assert {b for _, b in overloads(run(doc))} == set(BANDS)


@pytest.mark.tc("TC-ENG-043")
@pytest.mark.parametrize("band", BANDS)
def test_limit_in_one_band_alone(band):
    doc = fx("FX-MARGIN")
    find(doc, "G1")["capacity"][band] = 1099
    assert overloads(run(doc)) == {("G1", band)}


@pytest.mark.tc("TC-ENG-044")
@pytest.mark.parametrize(
    "capacity, overloaded",
    [(3300, False), (3299.9999995, False), (3299.99999, True), (3299, True)],
)
def test_equality_survives_binary_rounding(capacity, overloaded):
    doc = fx("FX-MARGIN")
    find(doc, "L1")["power"] = tri(3000)
    find(doc, "G1")["capacity"] = tri(capacity)
    result = run(doc)
    assert bool(result.overloads) is overloaded
    if capacity == 3300:
        assert triple(result.el["G1"].margin_w) == near(0)


@pytest.mark.tc("TC-ENG-045")
def test_which_elements_are_checked():
    checked = run(fx("FX-BATCH"), {"G1": "failed"}).checked
    assert "G1" not in checked
    assert "G2" in checked
    assert "T12" not in checked
    assert "AC1" not in checked

    result = run(fx("FX-BAT"))
    assert "BAT" in result.checked
    assert D(result, "BAT") == near(0)
    assert triple(result.el["BAT"].margin_pct) == near(100)


@pytest.mark.tc("TC-ENG-046")
def test_per_element_margin_override():
    result = run(fx("FX-OVERRIDE"))
    assert triple(result.el["G1"].with_margin) == near(1250)
    assert triple(result.el["AC1"].with_margin) == near(1100)
    assert result.overloads == []

    doc = fx("FX-OVERRIDE")
    find(doc, "G1")["capacity"] = tri(1249)
    assert {element for element, _ in overloads(run(doc))} == {"G1"}

    doc = fx("FX-OVERRIDE")
    find(doc, "G1")["safety_margin"] = 0
    find(doc, "G1")["capacity"] = tri(1000)
    result = run(doc)
    assert triple(result.el["G1"].with_margin) == near(1000)
    assert result.overloads == []


@pytest.mark.tc("TC-ENG-047")
def test_element_with_no_capacity_is_unchecked():
    doc = fx("FX-MARGIN")
    find(doc, "L1")["power"] = tri(1000000)
    find(doc, "G1")["capacity"] = tri(2000000)
    result = run(doc)
    assert "AC1" not in result.checked
    assert result.overloads == []
    record = result.el["AC1"]
    assert triple(record.capacity) == (None, None, None)
    assert triple(record.margin_w) == (None, None, None)
    assert triple(record.margin_pct) == (None, None, None)


@pytest.mark.tc("TC-ENG-048")
def test_one_failing_band_overloads_the_element():
    doc = fx("FX-TRAN")
    find(doc, "LT1")["power"] = tri((500, 1000, 100))
    result = run(doc)
    assert [o.band for o in result.overloads if o.element == "AC1"] == ["short_term"]


@pytest.mark.tc("TC-ENG-049")
def test_tru_is_checked_on_output_power():
    doc = fx("FX-SINGLE")
    doc["loads"] = [load("LD", "DC1", 850)]
    find(doc, "TRU1")["capacity"] = tri(900)
    setp(doc, "$.settings.safety_margin", 0)
    result = run(doc)
    assert triple(result.el["TRU1"].input) == near(1000)
    assert D(result, "TRU1") == near(850)
    assert result.overloads == []


@pytest.mark.tc("TC-ENG-050")
def test_remaining_margin():
    doc = fx("FX-MARGIN")
    find(doc, "G1")["capacity"] = tri(2000)
    record = run(doc).el["G1"]
    assert triple(record.margin_w) == near(900)
    assert triple(record.margin_pct) == near(45)

    find(doc, "L1")["power"] = tri(2000)
    record = run(doc).el["G1"]
    assert triple(record.margin_w) == near(-200)
    assert triple(record.margin_pct) == near(-10)


@pytest.mark.tc("TC-ENG-050")
def test_remaining_margin_on_the_worked_fixture():
    result = run(fx("FX-SINGLE"))
    assert triple(result.el["G1"].margin_w) == near((15600, 11590, 7800))
    assert triple(result.el["G1"].margin_pct) == near((78, 77.27, 78), 0.006)
    assert triple(result.el["TRU1"].margin_w) == near((4130, 3504, 3065))
    assert triple(result.el["TRU1"].margin_pct) == near((68.83, 70.08, 76.63), 0.006)


@pytest.mark.tc("TC-ENG-051")
def test_zero_capacity():
    result = run(fx("FX-ZERO"))
    assert triple(result.el["AC1"].margin_pct) == near(-100)
    assert {element for element, _ in overloads(result)} == {"AC1"}

    doc = fx("FX-ZERO")
    find(doc, "L1")["power"] = tri(0)
    result = run(doc)
    assert triple(result.el["AC1"].margin_pct) == near(0)
    assert result.overloads == []


@pytest.mark.tc("TC-ENG-052")
def test_worst_element_by_percentage():
    worst = run(fx("FX-WORST")).worst
    assert (worst.element, worst.band) == ("G2", "transient")
    assert worst.margin_pct == pytest.approx(12, abs=1e-6)


def _worst_ties():
    doc = fx("FX-WORST")
    find(doc, "L1")["power"] = tri(880)
    find(doc, "L2")["power"] = tri(880)
    return doc


def _with_g4_g5(g5_load):
    doc = _worst_ties()
    setp(doc, "$.settings.safety_margin", 0.10)
    for n, cap, power in ((4, 1000, 900), (5, 3000, g5_load)):
        doc["buses"].append(ac(f"AC{n}"))
        add_source(doc, gen(n, cap), f"AC{n}")
        doc["loads"].append(load(f"L{n}", f"AC{n}", power))
    return doc


@pytest.mark.tc("TC-ENG-053")
def test_worst_ties_resolve_by_id_then_band():
    worst = run(_worst_ties()).worst
    assert (worst.element, worst.band) == ("G1", "transient")


@pytest.mark.tc("TC-ENG-053")
def test_worst_ties_within_tolerance():
    worst = run(_with_g4_g5(2700)).worst
    assert (worst.element, worst.band) == ("G4", "transient")
    assert worst.margin_pct == pytest.approx(1, abs=1e-6)


@pytest.mark.tc("TC-ENG-053")
def test_worst_real_difference_wins():
    worst = run(_with_g4_g5(2700.1)).worst
    assert worst.element == "G5"
    assert worst.margin_pct == pytest.approx(0.9963, abs=0.0001)


@pytest.mark.tc("TC-ENG-054")
def test_nothing_checked_gives_null():
    result = run(fx("FX-ESS"), {"G1": "failed", "BAT": "failed"})
    assert (result.worst.element, result.worst.band, result.worst.margin_pct) == (None,) * 3
    assert result.checked == []


# --- Results ---


@pytest.mark.tc("TC-ENG-055")
@pytest.mark.parametrize(
    "scenario_id, verdict",
    [("S1", "PASS"), ("S5", "FAIL"), ("S3", "FAIL"), ("S4", "FAIL")],
)
def test_verdict_truth_table(scenario_id, verdict):
    doc = fx("FX-BATCH")
    assert run(doc, pick(doc["scenarios"], scenario_id)["states"]).verdict == verdict


@pytest.mark.tc("TC-ENG-056")
@pytest.mark.parametrize(
    "states, unpowered, verdict",
    [
        ({}, [], "PASS"),
        ({"G1": "failed"}, ["LE1", "LE2"], "FAIL"),
        ({"G1": "failed", "DCS": "off"}, ["LE1", "LE2", "LE3"], "FAIL"),
        ({"G1": "failed", "BAT": "failed", "DCS": "off"}, ["LE1", "LE2", "LE3"], "FAIL"),
    ],
)
def test_essential_load_failure(states, unpowered, verdict):
    result = run(fx("FX-ESS"), states)
    assert [u.id for u in result.unpowered] == unpowered
    assert all(u.name == u.id and u.bus in ("AC1", "DCS") for u in result.unpowered)
    assert result.verdict == verdict
    assert result.overloads == []


@pytest.mark.tc("TC-ENG-057")
def test_total_loss_fails_only_through_essential_loads():
    states = {"G1": "failed", "BAT": "failed"}
    result = run(fx("FX-ESS"), states)
    assert result.verdict == "FAIL"
    assert len(result.unpowered) == 3

    doc = fx("FX-ESS")
    for item in doc["loads"]:
        item.pop("essential", None)
    result = run(doc, states)
    assert result.verdict == "PASS"
    assert result.checked == []


@pytest.mark.tc("TC-ENG-058")
def test_overload_entries():
    entries = {
        (o.element, o.band): (o.demand_with_margin, o.capacity) for o in run(fx("FX-TRAN")).overloads
    }
    expected = {
        ("AC2", "transient"): (1100, 1000),
        ("AC2", "short_term"): (1045, 1000),
        ("G4", "transient"): (1100, 1000),
        ("G4", "short_term"): (1100, 1000),
        ("C_G3", "transient"): (550, 100),
        ("AC1", "transient"): (1100, 1000),
    }
    assert entries.keys() == expected.keys()
    for key, figures in expected.items():
        assert entries[key] == pytest.approx(figures, abs=1e-6)


@pytest.mark.tc("TC-ENG-059")
def test_result_record_for_every_element():
    for doc, states in configurations():
        result = run(doc, states)
        ids = [x["id"] for k in ("sources", "buses", "trus", "contactors") for x in doc[k]]
        assert set(ids) == set(result.el)
        for id_ in ids:
            record = result.el[id_]
            assert isinstance(record.energised, bool)
            for field in ("demand", "with_margin", "capacity", "margin_w", "margin_pct"):
                assert set(getattr(record, field)) == set(BANDS)
            for band in BANDS:
                if record.capacity[band] is None:
                    assert record.margin_w[band] is None
                    assert record.margin_pct[band] is None
                if record.energised and record.demand[band] is not None:
                    assert isinstance(record.with_margin[band], float)
                if not record.energised:
                    assert record.demand[band] is None
        for bus in doc["buses"]:
            assert all(isinstance(v, (int, float)) for v in triple(result.el[bus["id"]].own))


@pytest.mark.tc("TC-ENG-060")
def test_load_percentage_of_capacity():
    result = run(fx("FX-SINGLE"))
    assert triple(result.el["G1"].load_pct) == near((20, 20.67, 20), 0.006)
    assert triple(result.el["TRU1"].load_pct) == near((28.33, 27.2, 21.25), 0.006)
    assert triple(run(fx("FX-DISPLAY")).el["G4"].load_pct) == (50, 50, 50)

    doc = fx("FX-EMPTY")
    find(doc, "G1")["capacity"] = tri(0)
    assert triple(run(doc).el["G1"].load_pct) == (None, None, None)

    result = run(fx("FX-SINGLE"), {"G1": "failed"})
    assert triple(result.el["G1"].load_pct) == (None, None, None)


@pytest.mark.tc("TC-ENG-061")
@pytest.mark.parametrize("power", [0, 5000])
def test_bus_voltage_is_nominal(power):
    doc = fx("FX-CREW")
    find(doc, "LX")["power"] = tri(power)
    assert triple(run(doc, {"DCS": "off"}).el["DCS"].voltage) == (28, 28, 28)


@pytest.mark.tc("TC-ENG-062")
def test_dc_current_uses_throughput():
    doc = definition(
        [bat("BAT", 5000)], [dc("DC1")], [], [c("BAT", "DC1")], [load("L", "DC1", 2800)]
    )
    assert triple(run(doc).el["DC1"].current) == near(100)
    assert run(fx("FX-CREW")).el["DCS"].current["continuous"] == pytest.approx(300 / 28, abs=1e-6)


@pytest.mark.tc("TC-ENG-063")
def test_ac_current_uses_throughput_per_phase():
    doc = definition([gen(1, 5000)], [ac("AC1")], [], [c("G1", "AC1")], [load("L", "AC1", 3450)])
    assert triple(run(doc).el["AC1"].current) == near(10)

    find(doc, "AC1")["phases"] = 1
    find(doc, "L")["power"] = tri(1150)
    assert triple(run(doc).el["AC1"].current) == near(10)

    current = run(fx("FX-THROUGH")).el["AC1"].current["continuous"]
    assert current == pytest.approx(2500 / 345, abs=1e-6)


@pytest.mark.tc("TC-ENG-064")
def test_no_electrical_quantities_on_a_dead_bus():
    record = run(fx("FX-MARGIN"), {"G1": "failed"}).el["AC1"]
    assert triple(record.voltage) == (None, None, None)
    assert triple(record.demand) == (None, None, None)
    assert triple(record.current) == (None, None, None)
    assert triple(record.own) == (0, 0, 0)


COMMON = {"state", "energised", "demand", "with_margin", "capacity", "margin_w", "margin_pct"}


@pytest.mark.tc("TC-ENG-076")
@pytest.mark.parametrize(
    "element, extra",
    [
        ("G1", {"load_pct"}),
        ("AC1", {"own", "voltage", "current", "fed_by"}),
        ("TRU1", {"load_pct", "input", "output"}),
        ("C_G1", set()),
    ],
)
def test_element_record_fields_by_kind(element, extra):
    record = run(fx("FX-SINGLE")).el[element]
    assert {f.name for f in dataclasses.fields(record)} == COMMON | extra


@pytest.mark.tc("TC-ENG-076")
def test_bus_with_no_crew_switch_has_null_state():
    assert run(fx("FX-SINGLE")).el["AC1"].state is None


@pytest.mark.tc("TC-ENG-077")
def test_analyse_entry_point_and_result_fields():
    doc = fx("FX-BATCH")
    defn = validate(doc).definition
    names = ("verdict", "overloads", "config_errors", "unpowered", "warnings")
    names += ("worst", "checked", "islands", "el")

    s5, s3, s4 = (
        ela.engine.analyse(defn, pick(doc["scenarios"], s)["states"]) for s in ("S5", "S3", "S4")
    )
    for result in (s5, s3, s4):
        for name in names:
            assert hasattr(result, name)
    entry = s5.overloads[0]
    assert (entry.element, entry.band) == ("G1", "transient")
    assert entry.demand_with_margin == pytest.approx(3300, abs=1e-6)
    assert entry.capacity == 3000
    assert (s5.worst.element, s5.worst.band) == ("T13", "transient")
    assert s5.worst.margin_pct == pytest.approx(-46.67, abs=0.006)
    assert (s4.unpowered[0].id, s4.unpowered[0].name, s4.unpowered[0].bus) == ("LA1", "LA1", "AC1")
    assert s3.config_errors


@pytest.mark.tc("TC-ENG-077")
def test_warning_and_island_entry_fields():
    result = run(fx("FX-RING"))
    warning = result.warnings[0]
    assert (warning.code, warning.element) == ("meshed_island", "T23")
    assert warning.message
    assert (result.islands[0].buses, result.islands[0].sources) == (["AC1", "AC2", "AC3"], ["G1"])


# --- Fed by ---


@pytest.mark.tc("TC-ENG-081")
@pytest.mark.parametrize(
    "name, states, expected",
    [
        ("FX-SINGLE", {}, {"AC1": ["G1"], "DC1": ["TRU1"]}),
        ("FX-SINGLE", {"G1": "failed"}, {"AC1": [], "DC1": []}),
        ("FX-TWO-TRU", {}, {"DC1": ["TRU1", "TRU2"]}),
        ("FX-BAT", {}, {"DC1": ["TRU1"], "DCB": ["TRU1"]}),
        ("FX-BAT", {"G1": "failed"}, {"AC1": [], "DC1": ["BAT"], "DCB": ["BAT"]}),
        ("FX-BAT2", {}, {"DC1": ["BAT1", "BAT2"]}),
        ("FX-TRU-RAT", {}, {"DC1": ["RAT_DC", "TRU1"]}),
        ("FX-PAR", {}, {"AC1": ["G1", "G2"], "AC2": ["G1", "G2"], "DC1": ["TRU1"]}),
        ("FX-CREW", {"DCS": "off"}, {"DCS": ["BAT"], "DCX": ["BAT"]}),
    ],
)
def test_fed_by(name, states, expected):
    result = run(fx(name), states)
    assert {bus: result.el[bus].fed_by for bus in expected} == expected


@pytest.mark.tc("TC-ENG-082")
def test_fed_by_battery_through_ties_below_dead_trus():
    doc = json.loads(SAMPLE.read_text("utf-8"))
    ac_feeds = ["GLC1", "GLC2", "APLC1", "APLC2", "RLC"]
    assert [k["id"] for k in doc["contactors"] if k["kind"] == "source" and k["id"] != "BATC"] == (
        ac_feeds
    )
    states = dict.fromkeys(ac_feeds, "open")
    result = run(doc, states)
    assert result.el["DCESS"].energised is True
    assert result.el["DCESS"].fed_by == ["BAT"]
    assert result.el["DCBAT"].fed_by == ["BAT"]
    for t in doc["trus"]:
        assert result.el[t["id"]].energised is False, t["id"]
    for bus in ("DC1", "DC2", "AC1", "AC2", "ACESS"):
        assert (result.el[bus].energised, result.el[bus].fed_by) == (False, [])

    dead = run(doc, {**states, "BATC": "open"})
    for bus in doc["buses"]:
        assert (dead.el[bus["id"]].energised, dead.el[bus["id"]].fed_by) == (False, [])


# --- Extreme values ---


@pytest.mark.tc("TC-ENG-084")
@pytest.mark.parametrize(
    "path, value",
    [
        ("$.sources[0].capacity", 1e-300),
        ("$.buses[0].capacity", 1e-300),
        ("$.buses[0].voltage", 1e-300),
        ("$.trus[0].efficiency", 1e-300),
        ("$.settings.safety_margin", 1e12),
    ],
)
def test_figures_stay_finite_at_the_limits(path, value):
    doc = fx("FX-SINGLE")
    doc["loads"] = [load("LA", "AC1", 1e12), load("LD", "DC1", 1e12)]
    if path.endswith("capacity"):
        value = tri(value)
    setp(doc, path, value)
    result = run(doc)
    assert result.verdict == "FAIL"
    assert result.worst.element is not None
    json.dumps(result.to_dict(), allow_nan=False)  # raises on an infinity or NaN


# --- Purity ---


@pytest.mark.tc("TC-ENG-066")
def test_no_time_input():
    assert len(inspect.signature(analyse).parameters) == 2
    defn = validate(fx("FX-SINGLE")).definition
    assert analyse(defn, {}) == analyse(defn, {})


@pytest.mark.tc("TC-ENG-067")
def test_inputs_are_not_modified():
    doc = fx("FX-BATCH")
    defn = validate(doc).definition
    states = pick(doc["scenarios"], "S5")["states"]
    defn_before, states_before = copy.deepcopy(defn), copy.deepcopy(states)
    analyse(defn, states)
    assert defn == defn_before
    assert states == states_before


@pytest.mark.tc("TC-ENG-068")
def test_no_automatic_reconfiguration():
    doc = fx("FX-BATCH")
    result = run(doc, {"G1": "failed"})
    for x in doc["contactors"]:
        assert result.el[x["id"]].state == x["default_state"]
    assert result.el["T12"].state == "open"
    assert energised(result, "AC1", "AC2") == [False, True]


@pytest.mark.tc("TC-ENG-069")
def test_no_load_shedding():
    doc = fx("FX-BATCH")
    result = run(doc, pick(doc["scenarios"], "S5")["states"])
    assert triple(result.el["AC1"].own) == near((1000, 900, 800))
    assert triple(result.el["AC2"].own) == near((1000, 900, 800))
    assert triple(result.el["AC3"].own) == near((2000, 1000, 1200))
    assert ("G1", "transient") in overloads(result)


def _keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from _keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from _keys(value)


@pytest.mark.tc("TC-ENG-070")
def test_no_endurance_quantity():
    serialised = json.loads(json.dumps(run(fx("FX-BAT2")).to_dict()))
    keys = list(_keys(serialised))
    assert "verdict" in keys
    assert not [k for k in keys for word in ("endurance", "amp_hour", "depletion") if word in k]


@pytest.mark.tc("TC-ENG-071")
def test_engine_has_no_web_dependency():
    assert Path(ela.engine.__file__).name == "engine.py"
    code = (
        "import sys, ela.engine;"
        "print([m for m in ('fastapi', 'starlette', 'uvicorn') if m in sys.modules])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"


@pytest.mark.tc("TC-ENG-065")
def test_one_analysis_entry_point():
    defn = validate(json.loads(SAMPLE.read_text("utf-8"))).definition
    results = run_batch(defn)
    assert len(results) == len(defn.scenarios) == 15
    for scenario, batch in zip(defn.scenarios, results, strict=True):
        direct = analyse(defn, dict(scenario.states))
        assert batch["scenario_id"] == scenario.id
        assert batch["result"] == direct.verdict
        assert batch["worst_element"] == direct.worst.element
        assert batch["worst_band"] == direct.worst.band
        assert batch["smallest_margin_pct"] == direct.worst.margin_pct
        assert batch["overloads"] == len(direct.overloads)
        assert batch["configuration_errors"] == len(direct.config_errors)
        assert batch["unpowered_essential"] == len(direct.unpowered)
