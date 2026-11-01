"""L0 acceptance cases from docs/test-cases.md ("L0 acceptance tests").

Each case takes the point of view of the aircraft electrical engineer and uses the delivered sample
definition and README. The tool is driven only through the command line, the HTTP API and a browser.
Expected figures are the hand calculation in tests/data/generic_twin_expected.json.
"""

import json
import re

import pytest
import readme_tools as rt
from conftest import REPO, fx, put_def
from playwright.sync_api import expect
from test_system import (
    BANDS,
    EXPECTED,
    SAMPLE,
    SAMPLE_FILE,
    analyse,
    cli,
    fmt_power,
    fmt_two,
    fmt_volts,
    sample_generator,
    sample_scenarios,
    stdout_cells,
)
from test_web_batch import run_batch_on_page, table_cells

HAND = EXPECTED["scenarios"]
TOLERANCE_W = 1e-6


def sample_batch(tmp_path):
    """`ela batch --json out.json` on the sample: the exit code and the parsed results."""
    out = tmp_path / "out.json"
    done = cli(SAMPLE_FILE, "--json", out)
    assert done.returncode == 1, done.stderr  # the sample fails some scenarios by design
    return done, json.loads(out.read_text("utf-8"))


def designed_to_fail():
    return {sid for sid, s in sample_scenarios().items() if "designed to fail" in s["description"]}


@pytest.mark.tc("TC-ACC-001")
def test_every_planned_configuration_gets_a_verdict(tmp_path):
    _, results = sample_batch(tmp_path)
    assert [r["scenario_id"] for r in results] == [s["id"] for s in SAMPLE["scenarios"]]
    assert set(HAND) == {r["scenario_id"] for r in results}
    for r in results:
        assert r["result"] in ("PASS", "FAIL")
        assert r["result"] == HAND[r["scenario_id"]]["result"], r["scenario_id"]
    names = " ".join(r["name"].lower() for r in results)
    for wanted in ("normal", "generator 1 loss", "generator 2 loss", "apu only", "rat only", "battery only"):
        assert wanted in names, wanted


@pytest.mark.tc("TC-ACC-002")
def test_same_tool_different_aircraft(client, defs_dir, tmp_path):
    put_def(defs_dir, fx("FX-4ENG"), "fx_4eng.json")
    four = tmp_path / "fx_4eng.json"
    four.write_text(json.dumps(fx("FX-4ENG")), encoding="utf-8")
    for name, path, scenarios, exit_code in (
        ("generic_twin", SAMPLE_FILE, len(SAMPLE["scenarios"]), 1),
        ("fx_4eng", four, 2, 0),
    ):
        listing = client.get(f"/api/definitions/{name}")
        assert listing.status_code == 200, name
        generators = [
            s for s in listing.json()["definition"]["sources"] if s["kind"] == "engine_generator"
        ]
        assert len(generators) == (2 if name == "generic_twin" else 4)
        api = client.post(f"/api/definitions/{name}/batch")
        assert api.status_code == 200
        assert len(api.json()["results"]) == scenarios
        done = cli(path)
        assert done.returncode == exit_code, done.stderr
        assert len(stdout_cells(done)) == scenarios
    assert [r["result"] for r in client.post("/api/definitions/fx_4eng/batch").json()["results"]] == [
        "PASS", "PASS",
    ]


def close(actual, expected):
    if expected is None:
        return actual is None
    return actual is not None and abs(actual - expected) <= TOLERANCE_W


@pytest.mark.tc("TC-ACC-003")
def test_results_follow_the_summation_method(client):
    checked_balance = 0
    for scenario_id, scenario in sample_scenarios().items():
        hand = HAND[scenario_id]
        result = analyse(client, "generic_twin", scenario["states"])
        el = result["el"]
        paralleled = bool(hand["paralleled_sources"]) or any(
            "paralleled" in e for e in result["config_errors"]
        )
        if not paralleled:
            checked_balance += 1
            for band in BANDS:
                supplied = sum(
                    el[s["id"]]["demand"][band] or 0 for s in SAMPLE["sources"]
                    if el[s["id"]]["energised"]
                )
                own = sum((el[b["id"]].get("own") or {}).get(band) or 0 for b in SAMPLE["buses"])
                losses = sum(
                    el[t["id"]]["input"][band] - el[t["id"]]["output"][band]
                    for t in SAMPLE["trus"]
                    if el[t["id"]]["input"][band] is not None
                )
                assert supplied == pytest.approx(own + losses, abs=TOLERANCE_W), (scenario_id, band)

        overloaded = {(o["element"], o["band"]) for o in result["overloads"]}
        for id_ in result["checked"]:
            for band in BANDS:
                over = el[id_]["with_margin"][band] > el[id_]["capacity"][band] + 1e-6
                assert over == ((id_, band) in overloaded), (scenario_id, id_, band)

        for group, fields in (
            ("sources", ("demand", "capacity")),
            ("trus", ("output", "input", "capacity")),
            ("buses", ("own", "demand", "capacity")),
            ("ties", ("demand", "capacity")),
        ):
            for id_, record in hand[group].items():
                for field in fields:
                    for band in BANDS:
                        wanted = (record.get(field) or {}).get(band) if record.get(field) else None
                        got = el[id_].get(field)
                        got = got.get(band) if got else None
                        assert close(got, wanted), (scenario_id, id_, field, band, got, wanted)
    assert checked_balance >= 10


def shown_buses(h, band="continuous"):
    return {
        b["id"]: (
            h.group(b["id"]).get_attribute("data-energised"),
            h.label(b["id"]).text_content() if h.label(b["id"]).count() else None,
        )
        for b in SAMPLE["buses"]
    }


@pytest.mark.tc("TC-ACC-004")
@pytest.mark.e2e
def test_exploring_a_failure_on_the_schematic(h_page):
    h = h_page()
    h.open("generic_twin")
    before = shown_buses(h)
    gen1 = sample_generator(1)
    expect(h.group(gen1)).to_have_attribute("data-state", "operative")
    h.group(gen1).click()
    expect(h.group(gen1)).to_have_attribute("data-state", "failed")
    after = shown_buses(h)
    assert after != before
    (match,) = [sid for sid, s in sample_scenarios().items() if s["states"] == {gen1: "failed"}]
    hand = HAND[match]["buses"]
    for bus in SAMPLE["buses"]:
        record = hand[bus["id"]]
        energised, text = after[bus["id"]]
        assert energised == ("true" if record["energised"] else "false"), bus["id"]
        if not record["energised"]:
            assert text is None, bus["id"]
            continue
        assert fmt_power(record["demand"]["continuous"]) in text, (bus["id"], text)
        assert f"{fmt_two(record['current']['continuous'])} A" in text, (bus["id"], text)
        assert f"{fmt_volts(bus['voltage'])} V" in text
    assert any(not hand[b]["energised"] for b in hand)
    assert before[sample_bus_id("AC BUS 1")][0] == "true"
    assert after[sample_bus_id("AC BUS 1")][0] == "false"


def sample_bus_id(name):
    (bus,) = [b for b in SAMPLE["buses"] if name in b["name"]]
    return bus["id"]


@pytest.mark.tc("TC-ACC-005")
@pytest.mark.e2e
def test_batch_reports_exactly_the_failing_scenarios(h_page):
    h = h_page()
    h.open("generic_twin")
    run_batch_on_page(h)
    cells = table_cells(h)
    assert [c[0] for c in cells] == [s["id"] for s in SAMPLE["scenarios"]]
    failing = {c[0] for c in cells if c[2] == "FAIL"}
    assert failing == {sid for sid, hand in HAND.items() if hand["result"] == "FAIL"}
    assert failing == designed_to_fail()
    assert any(int(c[6]) > 0 for c in cells if c[2] == "FAIL")


@pytest.mark.tc("TC-ACC-006")
def test_loss_of_essential_loads_is_reported(client):
    essential_by_bus = {}
    for item in SAMPLE["loads"]:
        if item.get("essential"):
            essential_by_bus.setdefault(item["bus"], []).append(item["name"])
    reported = 0
    for scenario_id in sorted(designed_to_fail()):
        result = analyse(client, "generic_twin", sample_scenarios()[scenario_id]["states"])
        if result["overloads"]:
            continue
        assert result["verdict"] == "FAIL", scenario_id
        if not result["unpowered"]:
            continue
        reported += 1
        names = [u["name"] for u in result["unpowered"]]
        assert [u["id"] for u in result["unpowered"]] == HAND[scenario_id]["unpowered_details"]
        assert sorted(names) == sorted(
            n for u in {u["bus"] for u in result["unpowered"]} for n in essential_by_bus[u]
        )
        assert len(names) == HAND[scenario_id]["unpowered_essential"] > 0
    assert reported >= 1


@pytest.mark.tc("TC-ACC-007")
@pytest.mark.e2e
def test_readme_alone_gets_an_engineer_running(fresh_clone, browser, tmp_path):
    for command, code, output in fresh_clone.installed:
        assert code == 0, f"{command}:\n{output[-2000:]}"
    _, running = rt.section("Running")
    commands = rt.fenced_commands(running)
    assert any(rt.is_start_command(c) for c in commands)
    server = None
    try:
        for command in commands:
            if rt.is_start_command(command):
                server = rt.DocumentedServer(fresh_clone.path, tmp_path / "server.log")
            else:
                done = rt.run_command(command, fresh_clone.path)
                # The sample fails some scenarios by design, so its batch run exits with 1.
                assert done.returncode == 1, f"{command}:\n{done.stderr[-2000:]}"
        assert server is not None
        assert (fresh_clone.path / "results.csv").is_file()
        assert (fresh_clone.path / "results.json").is_file()
        page = browser.new_page(viewport={"width": 1366, "height": 768})
        try:
            address = re.sub(r":\d+", f":{server.port}", rt.documented_address(), count=1)
            page.goto(address + "/")
            page.locator("#definition-select option").first.wait_for(state="attached")
            page.select_option("#definition-select", "generic_twin")
            expect(page.locator("#status-verdict")).not_to_be_empty()
            assert page.locator("#schematic [data-id]").count() > 20
            page.click("#run-batch")
            expect(page.locator("#batch-table tbody tr.result")).to_have_count(len(SAMPLE["scenarios"]))
        finally:
            page.close()
    finally:
        if server is not None:
            server.stop()


@pytest.mark.tc("TC-ACC-008")
def test_worked_example_passes_and_fails(tmp_path):
    _, results = sample_batch(tmp_path)
    assert any(r["result"] == "PASS" for r in results)
    assert any(r["result"] == "FAIL" and r["overloads"] > 0 for r in results)
    assert any(r["result"] == "FAIL" and r["unpowered_essential"] > 0 for r in results)
    assert REPO.joinpath("definitions", "generic_twin.json").is_file()


@pytest.mark.tc("TC-ACC-009")
@pytest.mark.meta
def test_automated_evidence_runs_clean(not_meta_run, second_not_meta_run):
    for run in (not_meta_run, second_not_meta_run):
        assert run.returncode == 0, run.stdout[-3000:]
        assert [c for c in run.cases if c[2] != "passed"] == []
        assert run.cases
    assert not_meta_run.ids == second_not_meta_run.ids
