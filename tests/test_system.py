"""L1 system cases from docs/test-cases.md ("L1 system tests").

These are black-box. Each case drives the tool through its command line, its HTTP API or a real
browser, and checks what a user could see. Nothing here imports `ela.engine`. Expected figures are
the hand-worked ones in the case text and in the fixture tables. Fixtures come from
tests/conftest.py. Browser cases use H-PAGE and the page helpers of tests/test_web_interactive.py.
"""

import csv
import hashlib
import io
import itertools
import json
import re
import socket
import subprocess
import sys
import urllib.request
from pathlib import Path

import httpx
import pytest
import readme_tools as rt
from conftest import REPO, find, fx, put_def, scenario, setp, tri
from playwright.sync_api import expect
from test_cli import NO_SOCKET
from test_web_batch import FX_BATCH_ROWS, expand, row, run_batch_on_page, table_cells
from test_web_interactive import (
    SAMPLE,
    hue_sat,
    label_text,
    opened,
    sample_generator,
    store,
    switch_of,
    tooltip_of,
    tooltip_rows,
    watts,
)

BANDS = ("transient", "short_term", "continuous")
SAMPLE_FILE = REPO / "definitions" / "generic_twin.json"
EXPECTED = json.loads((REPO / "tests" / "data" / "generic_twin_expected.json").read_text("utf-8"))
HIDDEN = "—"


# --- Helpers ------------------------------------------------------------------------------------


def cli(*args, cwd=None):
    """`ela batch ...` in a subprocess, as a user would run it."""
    return subprocess.run(
        [sys.executable, "-m", "ela", "batch", *map(str, args)],
        cwd=cwd or REPO,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def write_doc(folder, doc, name="defn.json"):
    path = folder / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def stdout_cells(done):
    """The CLI's scenario lines as lists of the nine cells."""
    return [line.split("\t") for line in done.stdout.splitlines()]


def analyse(client, def_id_, states=None):
    reply = client.post(f"/api/definitions/{def_id_}/analyse", json={"states": states or {}})
    assert reply.status_code == 200, reply.text
    return reply.json()


def triple(field):
    return tuple(field[b] for b in BANDS)


def demand(result, id_):
    return triple(result["el"][id_]["demand"])


def stored(defs_dir, doc, name):
    """Store a document in H-DEFS as `<name>.json` and return its definition id."""
    put_def(defs_dir, doc, f"{name}.json")
    return name


def with_scenarios(doc, *states):
    doc["scenarios"] = [scenario(f"S{i}", s) for i, s in enumerate(states, 1)]
    return doc


def sample_scenarios():
    return {s["id"]: s for s in SAMPLE["scenarios"]}


def fmt_power(watts_):
    """The bus label's power text: whole watts below 1000 W, kW with two decimals above."""
    rounded = int(watts_ + 0.5)
    if rounded < 1000:
        return f"{rounded} W"
    hundredths = (rounded + 5) // 10
    return f"{hundredths // 100}.{hundredths % 100:02d} kW"


def fmt_two(value):
    from decimal import ROUND_HALF_UP, Decimal

    return str(Decimal(repr(float(value))).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def fmt_volts(value):
    return f"{value:g}"


def walk(node):
    """Every key and every string value in parsed JSON."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield str(key)
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)
    elif isinstance(node, str):
        yield node


def upload(client, doc, name="up.json"):
    body = doc if isinstance(doc, str) else json.dumps(doc)
    return client.post("/api/definitions", files={"file": (name, body, "application/json")})


def single_without_load_la():
    doc = fx("FX-SINGLE")
    doc["loads"] = [item for item in doc["loads"] if item["id"] != "LA"]
    find(doc, "LD")["power"] = tri(850)
    return doc


# --- Definition file and validation -------------------------------------------------------------


@pytest.mark.tc("TC-SYS-001")
def test_one_file_is_the_only_input(client, defs_dir, start_server, tmp_path):
    assert [p.name for p in defs_dir.iterdir()] == ["generic_twin.json"]
    server = start_server()
    reply = httpx.post(f"{server.url}/api/definitions/generic_twin/batch")
    assert reply.status_code == 200
    api_results = reply.json()["results"]

    alone = tmp_path / "alone"
    alone.mkdir()
    copy = alone / "generic_twin.json"
    copy.write_bytes(SAMPLE_FILE.read_bytes())
    done = cli(copy.name, cwd=alone)
    assert done.returncode == 1, done.stderr  # the sample fails some scenarios by design
    cli_cells = stdout_cells(done)
    assert [r["scenario_id"] for r in api_results] == [c[0] for c in cli_cells]
    assert len(api_results) == len(SAMPLE["scenarios"]) == 15
    assert [r["result"] for r in api_results] == [c[2] for c in cli_cells]
    assert sorted(p.name for p in alone.iterdir()) == ["generic_twin.json"]


@pytest.mark.tc("TC-SYS-002")
def test_units_through_the_api(client, defs_dir):
    doc = fx("FX-MARGIN")
    find(doc, "G1")["capacity"] = tri(2000)
    name = stored(defs_dir, doc, "fx_margin")
    result = analyse(client, name)
    assert demand(result, "AC1") == pytest.approx((1000, 1000, 1000))
    assert triple(result["el"]["G1"]["with_margin"]) == pytest.approx((1100, 1100, 1100))
    assert triple(result["el"]["G1"]["margin_w"]) == pytest.approx((900, 900, 900))


@pytest.mark.tc("TC-SYS-003")
def test_engine_count_has_no_limit_and_the_apu_is_optional(client, defs_dir, tmp_path):
    cases = {
        "fx_eng2": fx("FX-ENG", 2),
        "fx_eng4": fx("FX-ENG", 4),
        "fx_eng8": fx("FX-ENG", 8),
        "fx_eng12": fx("FX-ENG", 12),
        "fx_single": fx("FX-SINGLE"),
        "fx_apu": fx("FX-APU"),
    }
    for name, doc in cases.items():
        doc["scenarios"] = [scenario("S", {})]
        path = write_doc(tmp_path, doc, f"{name}.json")
        put_def(defs_dir, doc, f"{name}.json")
        done = cli(path)
        assert done.returncode == 0, (name, done.stdout, done.stderr)
        assert len(stdout_cells(done)) == 1
        assert client.get(f"/api/definitions/{name}").status_code == 200, name
        assert client.post(f"/api/definitions/{name}/analyse", json={"states": {}}).status_code == 200


@pytest.mark.tc("TC-SYS-004")
def test_every_component_kind_and_state(client, defs_dir):
    doc = fx("FX-ALLKINDS")
    name = stored(defs_dir, doc, "fx_allkinds")
    choices = {}
    for s in doc["sources"]:
        rat = s["kind"] == "emergency_generator"
        choices[s["id"]] = ("available", "unavailable") if rat else ("operative", "failed")
    choices.update({t["id"]: ("operative", "failed") for t in doc["trus"]})
    choices.update({c["id"]: ("closed", "open") for c in doc["contactors"]})
    choices.update({b["id"]: ("on", "off") for b in doc["buses"] if b.get("crew_switch")})
    kinds = {s["kind"] for s in doc["sources"]}
    assert kinds == {"engine_generator", "apu_generator", "emergency_generator", "battery"}
    assert {c["kind"] for c in doc["contactors"]} == {"source", "bus_tie", "tru"}
    assert "DCB" in choices
    for id_, values in choices.items():
        for value in values:
            result = analyse(client, name, {id_: value})
            assert result["el"][id_]["state"] == value, (id_, value)


@pytest.mark.tc("TC-SYS-005")
@pytest.mark.e2e
def test_invalid_definitions_are_not_analysed_or_opened(client, defs_dir, h_page, tmp_path):
    doc = fx("FX-SINGLE")
    setp(doc, "$.loads[0].bus", "NOBUS")
    put_def(defs_dir, doc, "fx_bad.json")
    done = cli(write_doc(tmp_path, doc))
    assert done.returncode == 2
    assert done.stdout == ""
    assert "$.loads[0].bus" in done.stderr

    reply = client.post("/api/definitions/fx_bad/analyse", json={"states": {}})
    assert reply.status_code == 422
    assert "verdict" not in reply.json() and "el" not in reply.json()
    assert reply.json()["errors"]

    h = h_page()
    h.page.select_option("#definition-select", "fx_bad")
    expect(h.page.locator("#message li")).not_to_have_count(0)
    assert "$.loads[0].bus" in h.page.locator("#message").text_content()
    expect(h.page.locator("#schematic [data-id]")).to_have_count(0)


@pytest.mark.tc("TC-SYS-006")
def test_all_errors_in_one_response(client, defs_dir):
    wanted = {
        "FX-FIVE": [
            "$.meta",
            "$.loads[1].id",
            "$.loads[0].bus",
            "$.trus[0]",
            "$.contactors[",
        ],
        "FX-MANY": [
            "$.settings",
            "$.loads[0].power",
            "$.loads[0].power.transient",
            "$.trus[0].efficiency",
            "$.loads[1].bus",
            "$.buses[0].voltage",
            "$.loads[2].id",
            "$.contactors[",
            "$.scenarios[0].states.GHOST",
            "$.scenarios[0].states.G1",
        ],
    }
    for name, paths in wanted.items():
        before = sorted(p.name for p in defs_dir.iterdir())
        reply = upload(client, fx(name), f"{name.lower().replace('-', '_')}.json")
        assert reply.status_code == 422, name
        errors = reply.json()["errors"]
        assert len(errors) >= len(paths), (name, errors)
        for error in errors:
            assert error["path"].startswith("$"), error
            assert error["message"].strip(), error
        for path in paths:
            assert any(e["path"].startswith(path) for e in errors), (name, path, errors)
        assert sorted(p.name for p in defs_dir.iterdir()) == before


@pytest.mark.tc("TC-SYS-007")
@pytest.mark.e2e
def test_warnings_do_not_block(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-WARN")
    expect(h.group("G1")).to_have_count(1)
    entry = h.page.locator("#warnings li").filter(has_text="zzz")
    expect(entry).to_have_count(1)


@pytest.mark.tc("TC-SYS-008")
def test_bad_state_in_scenario_and_in_request(client, defs_dir):
    doc = fx("FX-SINGLE")
    doc["scenarios"] = [scenario("S1", {"GHOST": "failed"})]
    reply = upload(client, doc, "ghost.json")
    assert reply.status_code == 422
    assert "$.scenarios[0].states.GHOST" in [e["path"] for e in reply.json()["errors"]]
    name = stored(defs_dir, fx("FX-SINGLE"), "fx_single")
    for states in ({"GHOST": "failed"}, {"G1": "closed"}):
        reply = client.post(f"/api/definitions/{name}/analyse", json={"states": states})
        assert reply.status_code == 422, states
        assert "el" not in reply.json()


# --- Method -------------------------------------------------------------------------------------


@pytest.mark.tc("TC-SYS-009")
def test_bands_are_separate_and_need_no_ordering(client, defs_dir):
    doc = fx("FX-SINGLE-E")
    find(doc, "LA")["power"] = {"transient": 100, "short_term": 200, "continuous": 300}
    name = stored(defs_dir, doc, "fx_single_e")
    listing = client.get(f"/api/definitions/{name}")
    assert listing.status_code == 200
    assert listing.json()["warnings"] == []
    result = analyse(client, name)
    assert result["warnings"] == []
    assert demand(result, "AC1") == pytest.approx((2100, 1800, 1300))


@pytest.mark.tc("TC-SYS-010")
def test_energisation_by_path_through_ties_and_trus(client, defs_dir):
    name = stored(defs_dir, fx("FX-CHAIN"), "fx_chain")

    def live(result):
        return [result["el"][b]["energised"] for b in ("AC1", "AC2", "AC3")]

    assert live(analyse(client, name, {"G1": "failed"})) == [False, False, False]
    assert live(analyse(client, name)) == [True, True, True]
    assert live(analyse(client, name, {"T12": "open"})) == [True, False, False]

    far = fx("FX-CHAIN")
    find(far, "C_G1")["to"] = "AC3"
    name = stored(defs_dir, far, "fx_chain_far")
    assert live(analyse(client, name, {"G1": "failed"})) == [False, False, False]
    assert live(analyse(client, name)) == [True, True, True]
    assert live(analyse(client, name, {"T12": "open"})) == [False, True, True]

    bat = stored(defs_dir, fx("FX-BAT"), "fx_bat")
    result = analyse(client, bat, {"G1": "failed"})
    assert result["el"]["DC1"]["energised"] is True
    assert result["el"]["AC1"]["energised"] is False


@pytest.mark.tc("TC-SYS-011")
def test_load_counting_and_crew_switch_start_state(client, defs_dir):
    doc = fx("FX-CREW")
    doc["scenarios"] = [scenario("SA", {}, "switch default"), scenario("SB", {"DCS": "off"})]
    name = stored(defs_dir, doc, "fx_crew")
    default = analyse(client, name)
    assert default["el"]["DCS"]["state"] == "on"
    assert triple(default["el"]["DCS"]["own"]) == pytest.approx((200, 150, 100))
    off = analyse(client, name, {"DCS": "off"})
    assert off["el"]["DCS"]["state"] == "off"
    assert triple(off["el"]["DCS"]["own"]) == (0, 0, 0)
    assert off["el"]["DCS"]["energised"] is True
    dead = analyse(client, name, {"BAT": "failed"})
    assert triple(dead["el"]["DCS"]["own"]) == (0, 0, 0)
    assert dead["el"]["DCS"]["energised"] is False

    # The batch shows the two scenarios apart: BAT carries 500/400/300 W with the switch on and
    # 300/250/200 W with it off, so the worst margin (continuous, on BAT) is 89 % and 92.67 %.
    results = {r["scenario_id"]: r for r in client.post(f"/api/definitions/{name}/batch").json()["results"]}
    assert results["SA"]["worst_element"] == results["SB"]["worst_element"] == "BAT"
    assert results["SA"]["smallest_margin_pct"] == pytest.approx(89.0)
    assert results["SB"]["smallest_margin_pct"] == pytest.approx(92.666667, abs=1e-5)
    assert analyse(client, name, doc["scenarios"][0]["states"])["el"]["DCS"]["state"] == "on"
    assert analyse(client, name, doc["scenarios"][1]["states"])["el"]["DCS"]["state"] == "off"


@pytest.mark.tc("TC-SYS-012")
def test_throughput_and_upstream_propagation(client, defs_dir):
    chain = fx("FX-CHAIN")
    chain["buses"] = [b for b in chain["buses"] if b["id"] != "AC3"]
    chain["contactors"] = [c for c in chain["contactors"] if c["id"] != "T23"]
    chain["loads"] = [item for item in chain["loads"] if item["id"] != "L3"]
    find(chain, "L1")["power"] = tri(1000)
    find(chain, "L2")["power"] = tri(500)
    result = analyse(client, stored(defs_dir, chain, "fx_chain"))
    assert demand(result, "AC1") == pytest.approx((1500, 1500, 1500))
    assert triple(result["el"]["AC1"]["own"]) == pytest.approx((1000, 1000, 1000))

    result = analyse(client, stored(defs_dir, single_without_load_la(), "fx_single"))
    assert demand(result, "G1") == pytest.approx((1000, 1000, 1000))
    assert triple(result["el"]["TRU1"]["input"]) == pytest.approx((1000, 1000, 1000))


@pytest.mark.tc("TC-SYS-013")
def test_dc_sharing_through_the_api(client, defs_dir):
    doc = fx("FX-TWO-TRU")
    find(doc, "LD")["power"] = tri(900)
    result = analyse(client, stored(defs_dir, doc, "fx_two_tru"))
    assert demand(result, "TRU1") == pytest.approx((600, 600, 600))
    assert demand(result, "TRU2") == pytest.approx((300, 300, 300))


@pytest.mark.tc("TC-SYS-014")
def test_battery_priority_through_the_api(client, defs_dir):
    name = stored(defs_dir, fx("FX-BAT"), "fx_bat")
    assert demand(analyse(client, name), "BAT") == (0, 0, 0)
    assert demand(analyse(client, name, {"TRU1": "failed"}), "BAT") == pytest.approx((850, 850, 850))


@pytest.mark.tc("TC-SYS-015")
def test_paralleling_fails_the_configuration(client, defs_dir):
    name = stored(defs_dir, fx("FX-BATCH"), "fx_batch")
    result = analyse(client, name, {"T12": "closed"})
    assert result["verdict"] == "FAIL"
    assert any("AC sources paralleled" in message for message in result["config_errors"])


@pytest.mark.tc("TC-SYS-016")
def test_mesh_warning_through_the_api(client, defs_dir, tmp_path):
    name = stored(defs_dir, fx("FX-RING"), "fx_ring")
    result = analyse(client, name)
    assert [w["element"] for w in result["warnings"]] == ["T23"]
    assert "meshed_island" in result["warnings"][0]["code"]
    done = cli(write_doc(tmp_path, fx("FX-RING")))
    lines = [line for line in done.stderr.splitlines() if "meshed_island" in line]
    assert len(lines) == 1 and "T23" in lines[0]


@pytest.mark.tc("TC-SYS-017")
def test_capacity_check_through_the_api(client, defs_dir):
    def margin_case(cap, load=None, name="fx_margin"):
        doc = fx("FX-MARGIN")
        find(doc, "G1")["capacity"] = tri(cap)
        if load is not None:
            find(doc, "L1")["power"] = tri(load)
        return analyse(client, stored(defs_dir, doc, name))

    assert margin_case(1100)["overloads"] == []
    over = margin_case(1099)
    assert over["verdict"] == "FAIL"
    assert {o["element"] for o in over["overloads"]} == {"G1"}
    assert margin_case(3300, load=3000)["overloads"] == []

    first = analyse(client, stored(defs_dir, fx("FX-OVERRIDE"), "fx_override"))
    assert triple(first["el"]["G1"]["with_margin"]) == pytest.approx((1250, 1250, 1250))
    assert triple(first["el"]["AC1"]["with_margin"]) == pytest.approx((1100, 1100, 1100))
    assert first["overloads"] == []
    plain = fx("FX-OVERRIDE")
    plain["buses"][0].pop("capacity")
    second = analyse(client, stored(defs_dir, plain, "fx_override_plain"))
    assert triple(second["el"]["AC1"]["with_margin"]) == pytest.approx((1100, 1100, 1100))
    assert second["overloads"] == [] and "AC1" not in second["checked"]


@pytest.mark.tc("TC-SYS-018")
def test_verdict_conditions_and_essential_loads(client, defs_dir):
    batch = stored(defs_dir, fx("FX-BATCH"), "fx_batch")
    results = {r["scenario_id"]: r for r in client.post(f"/api/definitions/{batch}/batch").json()["results"]}
    assert results["S1"]["result"] == "PASS"
    s5 = results["S5"]
    assert (s5["result"], s5["overloads"], s5["configuration_errors"], s5["unpowered_essential"]) == (
        "FAIL", 3, 0, 0,
    )
    s3 = results["S3"]
    assert (s3["result"], s3["overloads"], s3["configuration_errors"], s3["unpowered_essential"]) == (
        "FAIL", 0, 1, 0,
    )
    s4 = results["S4"]
    assert (s4["result"], s4["overloads"], s4["configuration_errors"], s4["unpowered_essential"]) == (
        "FAIL", 0, 0, 1,
    )
    ess = stored(defs_dir, fx("FX-ESS"), "fx_ess")
    result = analyse(client, ess, {"G1": "failed", "DCS": "off"})
    assert result["verdict"] == "FAIL"
    assert [u["name"] for u in result["unpowered"]] == ["LE1", "LE2", "LE3"]
    assert result["overloads"] == []


@pytest.mark.tc("TC-SYS-019")
def test_remaining_margin_and_worst_element(client, defs_dir):
    doc = fx("FX-MARGIN")
    find(doc, "G1")["capacity"] = tri(2000)
    result = analyse(client, stored(defs_dir, doc, "fx_margin"))
    assert triple(result["el"]["G1"]["margin_w"]) == pytest.approx((900, 900, 900))
    assert triple(result["el"]["G1"]["margin_pct"]) == pytest.approx((45, 45, 45))
    assert result["worst"]["element"] == "G1"

    batch = stored(defs_dir, fx("FX-BATCH"), "fx_batch")
    results = {r["scenario_id"]: r for r in client.post(f"/api/definitions/{batch}/batch").json()["results"]}
    assert (results["S2"]["worst_element"], results["S2"]["worst_band"]) == ("G2", "continuous")
    assert results["S2"]["smallest_margin_pct"] == pytest.approx(12.0)
    assert (results["S5"]["worst_element"], results["S5"]["worst_band"]) == ("T13", "transient")
    exported = client.get(f"/api/definitions/{batch}/batch/export", params={"format": "csv"}).text
    rows = {r["scenario_id"]: r for r in csv.DictReader(io.StringIO(exported))}
    assert rows["S5"]["smallest_margin_pct"] == "-46.67"


@pytest.mark.tc("TC-SYS-020")
def test_voltage_power_and_current(client, defs_dir):
    from conftest import ac, bat, c, dc, definition, gen, load

    battery = definition([bat("BAT", 5000)], [dc("DC1")], [], [c("BAT", "DC1")], [load("L", "DC1", 2800)])
    result = analyse(client, stored(defs_dir, battery, "fx_dc_only"))
    bus = result["el"]["DC1"]
    assert triple(bus["voltage"]) == (28, 28, 28)
    assert demand(result, "DC1") == pytest.approx((2800, 2800, 2800))
    assert triple(bus["current"]) == pytest.approx((100, 100, 100))

    generator = definition([gen(1, 5000)], [ac("AC1")], [], [c("G1", "AC1")], [load("L", "AC1", 3450)])
    result = analyse(client, stored(defs_dir, generator, "fx_ac_only"))
    bus = result["el"]["AC1"]
    assert triple(bus["voltage"]) == (115, 115, 115)
    assert demand(result, "AC1") == pytest.approx((3450, 3450, 3450))
    assert triple(bus["current"]) == pytest.approx((10, 10, 10))

    single_phase = definition(
        [gen(1, 5000)], [ac("AC1", phases=1)], [], [c("G1", "AC1")], [load("L", "AC1", 3450)]
    )
    result = analyse(client, stored(defs_dir, single_phase, "fx_one_phase"))
    assert triple(result["el"]["AC1"]["current"]) == pytest.approx((30, 30, 30))


@pytest.mark.tc("TC-SYS-021")
def test_static_results_with_no_time_or_endurance_quantity(client, defs_dir):
    batch = stored(defs_dir, fx("FX-BATCH"), "fx_batch")
    bodies = [analyse(client, batch, {"T13": "closed"}) for _ in range(3)]
    assert bodies[0] == bodies[1] == bodies[2]

    spec = client.get("/openapi.json").json()
    operation = spec["paths"]["/api/definitions/{id}/analyse"]["post"]
    request = json.dumps(operation.get("requestBody", {}))
    for word in ("time", "duration", "step", "dt"):
        assert not re.search(rf"\b{word}\b", request, re.IGNORECASE), word

    result = analyse(client, stored(defs_dir, fx("FX-BAT2"), "fx_bat2"))
    for text in walk(result):
        lowered = text.lower()
        for word in ("amp-hour", "amp_hour", "ampere", "endurance", "depletion", "depleted"):
            assert word not in lowered, (word, text)


@pytest.mark.tc("TC-SYS-022")
def test_no_reconfiguration_or_shedding_and_fixed_load_power(client, defs_dir):
    doc = fx("FX-BATCH")
    batch = stored(defs_dir, doc, "fx_batch")
    assert analyse(client, batch, {"G1": "failed"})["el"]["AC1"]["energised"] is False
    s5 = analyse(client, batch, {"T13": "closed"})
    assert triple(s5["el"]["AC1"]["own"]) == pytest.approx((1000, 900, 800))
    assert triple(s5["el"]["AC3"]["own"]) == pytest.approx((2000, 1000, 1200))
    assert triple(s5["el"]["AC2"]["own"]) == pytest.approx((1000, 900, 800))
    results = client.post(f"/api/definitions/{batch}/batch").json()["results"]
    assert len(results) == 5
    seen = 0
    for item in doc["scenarios"]:
        result = analyse(client, batch, item["states"])
        if result["el"]["AC2"]["energised"]:
            seen += 1
            assert triple(result["el"]["AC2"]["own"]) == pytest.approx((1000, 900, 800)), item["id"]
    assert seen >= 3


# --- Sample, definition list and schematic ------------------------------------------------------


@pytest.mark.tc("TC-SYS-023")
def test_sample_has_passing_and_failing_scenarios(tmp_path):
    out = tmp_path / "out.json"
    done = cli(SAMPLE_FILE, "--json", out)
    assert done.returncode == 1, done.stderr
    assert "$." not in done.stderr
    results = json.loads(out.read_text("utf-8"))
    verdicts = {r["result"] for r in results}
    assert verdicts == {"PASS", "FAIL"}


@pytest.mark.tc("TC-SYS-024")
@pytest.mark.e2e
def test_definition_list_and_browser_upload(h_page, defs_dir):
    h = h_page()
    put_def(defs_dir, fx("FX-SINGLE"), "fx_single.json")
    put_def(defs_dir, "not a definition", "notes.txt")
    h.reload()
    options = h.options()
    assert "fx_single" in options and "generic_twin" in options
    assert "notes" not in options and "notes.txt" not in options
    body = json.dumps(fx("FX-WARN")).encode()
    h.page.set_input_files(
        "#definition-upload", {"name": "up.json", "mimeType": "application/json", "buffer": body}
    )
    expect(h.page.locator('#definition-select option[value="up"]')).to_have_count(1)
    h.open("up")
    expect(h.group("G1")).to_have_count(1)


@pytest.mark.tc("TC-SYS-025")
@pytest.mark.e2e
def test_definition_switch_resets_state(h_page, defs_dir):
    store(defs_dir, "FX-BATCH")
    h = h_page()
    h.open("generic_twin")
    defaults = h.states()
    h.open("fx_batch")
    h.group("G1").click()
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    h.open("generic_twin")
    assert h.states() == defaults
    expected = {}
    for kind in ("sources", "trus", "contactors"):
        for item in SAMPLE[kind]:
            expected[item["id"]] = item.get("default_state", "unavailable")
    for bus in SAMPLE["buses"]:
        if bus.get("crew_switch"):
            expected[switch_of(bus["id"])] = "on"
    states = h.states()
    assert {k: states[k] for k in expected} == expected
    expect(h.page.locator("#status-verdict")).to_have_text("PASS")


@pytest.mark.tc("TC-SYS-026")
@pytest.mark.e2e
def test_automatic_layered_schematic(h_page):
    h = h_page()
    h.open("generic_twin")
    keys = set(walk(json.loads(SAMPLE_FILE.read_text("utf-8"))))
    assert not keys & {"x", "y", "position", "coordinates", "layout", "width", "height"}

    def box(ids):
        rects = [h.rect(i) for i in ids]
        return min(r[1] for r in rects), max(r[1] + r[3] for r in rects)

    sources = box([s["id"] for s in SAMPLE["sources"]])
    ac = box([b["id"] for b in SAMPLE["buses"] if b["type"] == "AC"])
    trus = box([t["id"] for t in SAMPLE["trus"]])
    dc = box([b["id"] for b in SAMPLE["buses"] if b["type"] == "DC"])
    assert sources[1] <= ac[0]
    assert ac[1] <= trus[0]
    assert trus[1] <= dc[0]

    drawn = h.page.evaluate(
        """() => [...document.querySelectorAll('#schematic *')].flatMap(e =>
            [e.id, e.dataset.id, e.dataset.label, e.textContent.trim()]).filter(Boolean)"""
    )
    for item in SAMPLE["loads"]:
        assert item["id"] not in drawn and item["name"] not in drawn
    assert all("breaker" not in text.lower() for text in drawn)


@pytest.mark.tc("TC-SYS-027")
@pytest.mark.e2e
def test_fifty_items_on_a_laptop_screen(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-50")
    ids = h.page.locator("#schematic [data-id]").evaluate_all("els => els.map(e => e.dataset.id)")
    assert len(ids) == 50
    svg = h.svg_box()
    rects = {i: h.rect(i) for i in ids}
    for i, (x, y, w, hgt) in rects.items():
        assert svg["x"] - 0.5 <= x and x + w <= svg["x"] + svg["width"] + 0.5, i
        assert svg["y"] - 0.5 <= y and y + hgt <= svg["y"] + svg["height"] + 0.5, i
        assert 0 <= x and x + w <= 1366 and 0 <= y and y + hgt <= 768, i
    for (a, ra), (b, rb) in itertools.combinations(rects.items(), 2):
        across = min(ra[0] + ra[2], rb[0] + rb[2]) - max(ra[0], rb[0])
        down = min(ra[1] + ra[3], rb[1] + rb[3]) - max(ra[1], rb[1])
        assert not (across > 0.5 and down > 0.5), (a, b)
    start_view = h.view()
    start = h.empty_point()
    h.drag(start, (start[0] + 60, start[1] - 30))
    panned = h.view()
    assert panned != start_view
    h.page.mouse.move(*h.center(ids[0]))
    h.page.mouse.wheel(0, -300)
    h.settle()
    assert h.view()[2] > panned[2]


@pytest.mark.tc("TC-SYS-028")
@pytest.mark.e2e
def test_colours_on_one_configuration(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-COLOURS")
    hue, sat = hue_sat(h.colour("AC1"))
    assert 90 <= hue <= 150 and sat > 20
    grey = h.colour("AC3")
    assert hue_sat(grey)[1] <= 15 and max(grey) <= 140
    hue, _ = hue_sat(h.colour("AC2"))
    assert 30 <= hue <= 50
    failed = h.colour("G3")
    assert hue_sat(failed)[1] <= 15 and max(failed) <= 140
    expect(h.group("G3").locator(".fail-mark")).to_have_count(1)


@pytest.mark.tc("TC-SYS-029")
@pytest.mark.e2e
def test_labels_by_band_and_failed_band_note(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-TRAN")
    assert h.page.input_value("#band-select") == "continuous"
    ac1 = label_text(h, "AC1")
    assert "115 V" in ac1 and "A" in ac1 and "100 W" in ac1
    assert "Transient" in ac1  # overloaded in a band other than the one shown
    expect(h.group("AC1")).to_have_attribute("data-status", "overloaded")
    h.page.select_option("#band-select", "transient")
    expect(h.label("AC1")).to_contain_text("1.00 kW")
    assert "100 W" not in label_text(h, "AC1")
    h.page.select_option("#band-select", "continuous")
    expect(h.label("AC1")).to_contain_text("100 W")
    expect(h.group("AC1")).to_have_attribute("data-status", "overloaded")
    h.group("G2").click()
    expect(h.group("G2")).to_have_attribute("data-state", "failed")
    expect(h.label("AC2")).to_have_count(0)


@pytest.mark.tc("TC-SYS-030")
@pytest.mark.e2e
def test_tooltip_and_supply_load(h_page, defs_dir):
    store(defs_dir, "FX-DISPLAY")
    h = opened(h_page, defs_dir, "FX-TRAN")
    result = httpx.post(f"{h.server.url}/api/definitions/fx_tran/analyse", json={"states": {}}).json()
    record = result["el"]["AC1"]
    rows = tooltip_rows(tooltip_of(h, "AC1"))
    checked = 0
    for band in BANDS:
        assert rows[band]["demand"] == watts(record["demand"][band])
        assert rows[band]["with_margin"] == watts(record["with_margin"][band])
        assert rows[band]["capacity"] == watts(record["capacity"][band])
        assert rows[band]["margin"].startswith(watts(record["margin_w"][band]))
        checked += 4
    assert checked == 12
    h.open("fx_display")
    g4 = label_text(h, "G4")
    assert "45.00 kW" in g4 and "50 %" in g4


# --- Interaction --------------------------------------------------------------------------------


@pytest.mark.tc("TC-SYS-031")
@pytest.mark.e2e
def test_every_clickable_kind_toggles(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-ALLKINDS")
    ids = ["G1", "APU", "BAT", "TRU1", "RAT_AC", "C_G1", "T1E", "DCB_switch"]
    for id_ in ids:
        before = h.group(id_).get_attribute("data-state")
        assert before
        h.group(id_).click()
        expect(h.group(id_)).not_to_have_attribute("data-state", before)
        changed = h.group(id_).get_attribute("data-state")
        h.group(id_).click()
        expect(h.group(id_)).to_have_attribute("data-state", before)
        assert changed != before


@pytest.mark.tc("TC-SYS-032")
@pytest.mark.e2e
def test_recompute_on_click_within_a_second(h_page):
    h = h_page()
    h.open("generic_twin")
    h.page.evaluate(
        """() => {
            window.__timing = [];
            let t0 = null;
            const svg = document.getElementById('schematic');
            svg.addEventListener('pointerup', () => { t0 = performance.now(); }, true);
            new MutationObserver(() => {
                if (t0 !== null) { window.__timing.push(performance.now() - t0); t0 = null; }
            }).observe(svg, {subtree: true, attributes: true, attributeFilter: ['data-state']});
        }"""
    )
    targets = [
        sample_generator(1), sample_generator(2), SAMPLE["trus"][0]["id"],
        SAMPLE["contactors"][0]["id"], SAMPLE["contactors"][1]["id"],
    ]
    for i in range(20):
        id_ = targets[i % len(targets)]
        before = h.group(id_).get_attribute("data-state")
        h.group(id_).click()
        expect(h.group(id_)).not_to_have_attribute("data-state", before)
    timing = h.page.evaluate("window.__timing")
    assert len(timing) >= 20
    assert max(timing) <= 1000


@pytest.mark.tc("TC-SYS-033")
@pytest.mark.e2e
def test_load_scenario_matches_the_batch(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    doc = fx("FX-BATCH")
    batch = httpx.post(f"{h.server.url}/api/definitions/fx_batch/batch").json()["results"]
    verdicts = {r["scenario_id"]: r["result"] for r in batch}
    for item in doc["scenarios"]:
        h.page.select_option("#scenario-select", item["id"])
        expect(h.page.locator("#status-verdict")).to_have_text(verdicts[item["id"]])
        reply = httpx.post(
            f"{h.server.url}/api/definitions/fx_batch/analyse", json={"states": item["states"]}
        ).json()
        assert reply["verdict"] == verdicts[item["id"]]
        for bus in ("AC1", "AC2", "AC3"):
            record = reply["el"][bus]
            if not record["energised"]:
                expect(h.label(bus)).to_have_count(0)
                continue
            expect(h.label(bus)).not_to_have_count(0)
            text = label_text(h, bus)
            assert fmt_power(record["demand"]["continuous"]) in text, (item["id"], bus, text)
            assert f"{fmt_two(record['current']['continuous'])} A" in text, (item["id"], bus, text)
            assert f"{fmt_volts(record['voltage']['continuous'])} V" in text


@pytest.mark.tc("TC-SYS-045")
@pytest.mark.e2e
def test_reset_restores_defaults_keeps_the_band_and_clears_the_scenario(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    states = h.states()
    verdict = h.page.locator("#status-verdict").text_content()
    h.group("G1").click()
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    h.page.select_option("#band-select", "short_term")
    h.page.click("#reset")
    expect(h.group("G1")).to_have_attribute("data-state", "operative")
    assert h.states() == states
    expect(h.page.locator("#status-verdict")).to_have_text(verdict)
    assert h.page.input_value("#band-select") == "short_term"
    assert h.page.input_value("#scenario-select") == ""

    h.page.select_option("#scenario-select", "S5")
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    h.page.click("#reset")
    expect(h.group("T13")).to_have_attribute("data-state", "open")
    assert h.states() == states
    expect(h.page.locator("#status-verdict")).to_have_text(verdict)
    assert h.page.input_value("#band-select") == "short_term"
    assert h.page.input_value("#scenario-select") == ""


@pytest.mark.tc("TC-SYS-034")
@pytest.mark.e2e
def test_status_panel_overall(h_page, defs_dir):
    doc = fx("FX-BATCH")
    find(doc, "LA2")["essential"] = True
    put_def(defs_dir, doc, "fx_batch.json")
    h = h_page()
    h.open("fx_batch")
    expect(h.page.locator("#status-verdict")).to_have_text("PASS")
    expect(h.page.locator("#status-list li:not(.none)")).to_have_count(0)  # "Nothing to report."
    h.group("G2").click()
    expect(h.group("G2")).to_have_attribute("data-state", "failed")
    h.group("T13").click()
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    elements = h.page.locator("#status-list li.overload .element").all_text_contents()
    assert set(elements) == {"G1", "T13"}
    expect(h.page.locator("#status-list li.unpowered .load-name")).to_have_text(["LA2"])


@pytest.mark.tc("TC-SYS-035")
@pytest.mark.e2e
def test_no_editing_in_the_ui(h_page):
    h = h_page()
    h.open("generic_twin")
    assert h.page.locator("input").evaluate_all("els => els.map(e => e.type)") == ["file"]
    assert h.page.locator("textarea, [contenteditable], input[type=text]").count() == 0
    digest = hashlib.sha256((h.defs / "generic_twin.json").read_bytes()).hexdigest()
    for id_ in (sample_generator(1), sample_generator(2), SAMPLE["trus"][0]["id"]):
        before = h.group(id_).get_attribute("data-state")
        h.group(id_).click()
        expect(h.group(id_)).not_to_have_attribute("data-state", before)
    h.page.select_option("#scenario-select", SAMPLE["scenarios"][2]["id"])
    run_batch_on_page(h)
    assert hashlib.sha256((h.defs / "generic_twin.json").read_bytes()).hexdigest() == digest
    assert (h.defs / "generic_twin.json").read_bytes() == SAMPLE_FILE.read_bytes()


# --- Batch --------------------------------------------------------------------------------------


@pytest.mark.tc("TC-SYS-036")
@pytest.mark.e2e
def test_browser_and_cli_runs_agree(h_page, defs_dir, tmp_path):
    store(defs_dir, "FX-BATCH")
    h = h_page()
    for name, path in (("fx_batch", defs_dir / "fx_batch.json"), ("generic_twin", SAMPLE_FILE)):
        h.open(name)
        run_batch_on_page(h)
        shown = table_cells(h)
        out = tmp_path / f"{name}.json"
        done = cli(path, "--json", out)
        assert done.returncode == 1, done.stderr  # both fail some scenarios by design
        assert stdout_cells(done) == shown
        results = json.loads(out.read_text("utf-8"))
        assert [r["scenario_id"] for r in results] == [cells[0] for cells in shown]
        if name == "fx_batch":
            assert shown == FX_BATCH_ROWS
            assert [r["overloads"] for r in results] == [0, 0, 0, 0, 3]
            assert all(
                r["overloads"] == len(r["overload_details"]) for r in results
            )
        else:
            for r in results:
                hand = EXPECTED["scenarios"][r["scenario_id"]]
                for field in (
                    "result", "worst_element", "worst_band", "overloads", "configuration_errors",
                    "unpowered_essential",
                ):
                    assert r[field] == hand[field], (r["scenario_id"], field)
                if hand["smallest_margin_pct"] is None:
                    assert r["smallest_margin_pct"] is None
                else:
                    assert r["smallest_margin_pct"] == pytest.approx(
                        hand["smallest_margin_pct"], abs=1e-4
                    )


@pytest.mark.tc("TC-SYS-037")
@pytest.mark.e2e
def test_drill_down_and_open_from_a_batch_row(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    detail_row = expand(h, "S5")
    entries = detail_row.locator("li.overload")
    expect(entries).to_have_count(3)
    row(h, "S5").locator('td[data-col="name"]').click()
    expect(h.page.locator("#workspace")).to_have_attribute("data-view", "schematic")
    assert h.page.input_value("#scenario-select") == "S5"
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    expect(h.group("T13")).to_have_attribute("data-state", "closed")


@pytest.mark.tc("TC-SYS-038")
@pytest.mark.e2e
def test_exports_parse_and_match(h_page):
    h = h_page()
    h.open("generic_twin")
    run_batch_on_page(h)
    shown = table_cells(h)
    downloads = {}
    for kind, control in (("csv", "#export-csv"), ("json", "#export-json")):
        with h.page.expect_download() as download:
            h.page.click(control)
        downloads[kind] = Path(download.value.path()).read_text("utf-8")
    rows = list(csv.reader(io.StringIO(downloads["csv"])))
    assert rows[0][:3] == ["scenario_id", "name", "result"]
    assert [[cell or HIDDEN for cell in r] for r in rows[1:]] == shown
    results = json.loads(downloads["json"])
    assert len(results) == len(shown) == 15
    for result, cells in zip(results, shown, strict=True):
        assert [
            result["scenario_id"], result["name"], result["result"],
            result["worst_element"] or HIDDEN, result["worst_band"] or HIDDEN,
        ] == cells[:5]
        if result["smallest_margin_pct"] is None:
            assert cells[5] == HIDDEN
        else:
            assert float(cells[5]) == pytest.approx(result["smallest_margin_pct"], abs=0.005)
        assert [str(result[k]) for k in ("overloads", "configuration_errors", "unpowered_essential")] == cells[6:]


# --- Command line and delivery ------------------------------------------------------------------


@pytest.mark.tc("TC-SYS-039")
def test_exit_codes_through_the_command_line(tmp_path):
    assert cli(write_doc(tmp_path, fx("FX-ALLPASS"), "pass.json")).returncode == 0
    assert cli(SAMPLE_FILE).returncode == 1
    done = cli(write_doc(tmp_path, fx("FX-THREEERR"), "bad.json"))
    assert done.returncode == 2
    assert done.stdout == ""


def non_loopback_addresses():
    found = set()
    try:
        for info in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET):
            found.add(info[4][0])
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # a UDP "connection" sends nothing, it picks a route
            found.add(s.getsockname()[0])
    except OSError:
        pass
    return sorted(a for a in found if not a.startswith("127.") and a != "0.0.0.0")


@pytest.mark.tc("TC-SYS-040")
@pytest.mark.e2e
def test_one_command_local_no_login(browser, tmp_path):
    server = rt.DocumentedServer(REPO, tmp_path / "server.log")
    try:
        page = browser.new_page()
        try:
            page.goto(server.url + "/")
            page.locator("#definition-select option").first.wait_for(state="attached")
            page.select_option("#definition-select", "generic_twin")
            expect(page.locator("#status-verdict")).not_to_be_empty()
            expect(page.locator("#schematic [data-id]").first).to_be_attached()
        finally:
            page.close()
        for path in ("/", "/api/definitions", "/api/definitions/generic_twin"):
            with urllib.request.urlopen(server.url + path, timeout=10) as reply:
                assert reply.status == 200
                assert "www-authenticate" not in {k.lower() for k in reply.headers}
        assert "127.0.0.1" in server.output()
        for address in non_loopback_addresses():
            with pytest.raises(OSError), socket.create_connection((address, server.port), timeout=3):
                pass
    finally:
        server.stop()


@pytest.mark.tc("TC-SYS-041")
def test_no_front_end_build_step(start_server):
    web = REPO / "web"
    banned = (
        "package.json", "webpack", "vite.config", "rollup", "esbuild", "tsconfig", ".babelrc",
        "babel.config", "gulpfile", "gruntfile", "parcel",
    )
    skip = {".venv", ".git", "node_modules", ".pytest_cache", ".ruff_cache", "__pycache__", ".claude"}
    found = [
        str(p.relative_to(REPO))
        for p in REPO.rglob("*")
        if p.is_file()
        and not skip & set(p.relative_to(REPO).parts)
        and any(word in p.name.lower() for word in banned)
    ]
    assert found == []
    server = start_server()
    files = sorted(p for p in web.iterdir() if p.is_file())
    assert {p.name for p in files} >= {"index.html", "app.js", "schematic.js", "batch.js", "styles.css"}
    for path in files:
        url = server.url + ("/" if path.name == "index.html" else f"/{path.name}")
        with urllib.request.urlopen(url, timeout=10) as reply:
            assert reply.read() == path.read_bytes(), path.name


@pytest.mark.tc("TC-SYS-042")
def test_analysis_with_no_server_or_network(tmp_path):
    path = write_doc(tmp_path, fx("FX-BATCH"))
    done = subprocess.run(
        [sys.executable, "-c", NO_SOCKET, "batch", str(path)],
        cwd=REPO,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )
    assert done.returncode == 1, done.stderr
    assert len(stdout_cells(done)) == 5
    assert "attempted" not in done.stderr


@pytest.mark.tc("TC-SYS-043")
def test_readme_topics():
    text = rt.readme_text()
    headings = [h.lower() for h in re.findall(r"^## (.+)$", text, re.MULTILINE)]
    for words in (("installation",), ("running",), ("json format",), ("adding", "aircraft")):
        matching = [h for h in headings if all(w in h for w in words)]
        assert matching, (words, headings)


@pytest.mark.tc("TC-SYS-044")
@pytest.mark.meta
def test_delivered_test_suite_covers_the_named_topics(not_meta_run):
    from test_traceability import covered_by, requirement_ids

    assert not_meta_run.returncode == 0, not_meta_run.stdout[-3000:]
    assert [c for c in not_meta_run.cases if c[2] != "passed"] == []
    passed = set()
    for classname, name, _ in not_meta_run.cases:
        module = re.search(r"(test_\w+)", classname)
        if module:
            passed.add((module.group(1) + ".py", name.split("[")[0]))
    covered = covered_by(passed)

    def rng(prefix, nums):
        return {f"L2-{prefix}-{n:03d}" for n in nums}

    topics = {
        "energisation": rng("ENG", range(3, 11)),
        "TRU efficiency": {"L2-ENG-016"},
        "bus ties": {"L2-ENG-017", "L2-ENG-021"},
        "source failures": {"L2-ENG-003", "L2-ENG-009"},
        "AC paralleling detection": {"L2-ENG-028"},
        "DC sharing": {"L2-ENG-033", "L2-ENG-034", "L2-ENG-038"},
        "battery priority": {"L2-ENG-035", "L2-ENG-036", "L2-ENG-037"},
        "safety margin": {"L2-ENG-041", "L2-ENG-043"},
        "crew switch": {"L2-ENG-002", "L2-ENG-013"},
        "validation errors": rng("VAL", [*range(7, 31), 32, 33]),
    }
    assert [t for t, reqs in topics.items() if not reqs <= covered] == []
    assert requirement_ids() >= set().union(*topics.values())
    names = [name for _, name, _ in not_meta_run.cases]
    for scenario_id in sample_scenarios():
        assert any(f"[{scenario_id}]" in name for name in names), scenario_id
    browser_tests = [c for c in not_meta_run.cases if re.search(r"test_web_\w+$", c[0] or "")]
    assert len(browser_tests) >= 50
    assert all(outcome == "passed" for _, _, outcome in browser_tests)


