"""C-WEBBAT cases from docs/test-cases.md, in a real Chromium page (H-PAGE) on a uvicorn server
(H-SERVER). The browser harness is in tests/conftest.py, and the page helpers are shared with
tests/test_web_interactive.py.
"""

import json
import re
from pathlib import Path

import httpx
import pytest
from conftest import REPO, fx, put_def
from playwright.sync_api import expect
from test_web_interactive import opened, store

from ela.batch import run_batch
from ela.format import format_pct
from ela.validate import validate

pytestmark = pytest.mark.e2e

WEB = REPO / "web"
ROWS = "#batch-table tbody tr.result"
COLUMNS = (
    "scenario_id", "name", "result", "worst_element", "worst_band", "smallest_margin_pct",
    "overloads", "configuration_errors", "unpowered_essential",
)

# The FX-BATCH table in docs/test-cases.md, as displayed.
FX_BATCH_ROWS = [
    ["S1", "Normal", "PASS", "G1", "continuous", "56", "0", "0", "0"],
    ["S2", "G1 lost", "PASS", "G2", "continuous", "12", "0", "0", "0"],
    ["S3", "Paralleled", "FAIL", "—", "—", "—", "0", "1", "0"],
    ["S4", "Dark", "FAIL", "—", "—", "—", "0", "0", "1"],
    ["S5", 'Overload, tie to "AC3" — T13', "FAIL", "T13", "transient", "-46.67", "3", "0", "0"],
]


def run_batch_on_page(h):
    h.page.click("#run-batch")
    expect(h.page.locator(ROWS).first).to_be_visible()


def table_cells(h):
    """Each result row as its nine summary cells."""
    return h.page.locator(ROWS).evaluate_all(
        """(rows, columns) => rows.map(r => columns.map(c => r.querySelector(`td[data-col="${c}"]`).textContent))""",
        list(COLUMNS),
    )


def row(h, scenario):
    return h.page.locator(f'{ROWS}[data-scenario="{scenario}"]')


def detail(h, scenario):
    return h.page.locator(f'#batch-table tr.detail[data-for="{scenario}"]')


def expand(h, scenario):
    row(h, scenario).locator("button.expand").click()
    expect(detail(h, scenario)).to_be_visible()
    return detail(h, scenario)


@pytest.mark.tc("TC-WBT-001")
def test_run_all_scenarios(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    posts = []
    h.page.on(
        "request",
        lambda r: posts.append(r.url) if r.method == "POST" and r.url.endswith("/batch") else None,
    )
    with h.page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/api/definitions/fx_batch/batch")
    ):
        h.page.click("#run-batch")
    expect(h.page.locator(ROWS)).to_have_count(5)
    h.page.wait_for_load_state("networkidle")
    assert len(posts) == 1


@pytest.mark.tc("TC-WBT-002")
def test_results_table(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    cells = table_cells(h)
    assert cells == FX_BATCH_ROWS
    assert "−" not in "".join("".join(r) for r in cells)  # a hyphen-minus, never a minus sign
    assert re.fullmatch(r"-46\.67", cells[4][5])
    headers = h.page.locator("#batch-table thead th").all_text_contents()
    assert len(headers) == 10


@pytest.mark.tc("TC-WBT-002")
def test_sample_table_equals_the_batch_result(h_page):
    h = h_page()
    h.open("generic_twin")
    run_batch_on_page(h)
    sample = validate(json.loads((REPO / "definitions" / "generic_twin.json").read_text("utf-8")))
    expected = []
    for r in run_batch(sample.definition):
        none = "—"
        expected.append([
            r["scenario_id"], r["name"], r["result"], r["worst_element"] or none,
            r["worst_band"] or none, format_pct(r["smallest_margin_pct"]),
            str(r["overloads"]), str(r["configuration_errors"]), str(r["unpowered_essential"]),
        ])
    assert table_cells(h) == expected
    assert len(expected) >= 10


@pytest.mark.tc("TC-WBT-002")
def test_number_formats(h_page):
    h = h_page()
    shown = h.page.evaluate(
        """async () => {
            const m = await import('/batch.js');
            return [['smallest_margin_pct', 56.0], ['smallest_margin_pct', 12], ['smallest_margin_pct', -46.666667],
                    ['smallest_margin_pct', 76.625], ['smallest_margin_pct', null], ['overloads', 3],
                    ['worst_element', null]].map(([c, v]) => m.cellText(c, v));
        }"""
    )
    assert shown == ["56", "12", "-46.67", "76.63", "—", "3", "—"]


@pytest.mark.tc("TC-WBT-002")
def test_definition_text_in_the_table_is_text(h_page, defs_dir):
    markup = '<img src=x onerror="window.__pwned = 1">'
    doc = fx("FX-BATCH")
    doc["scenarios"][0]["name"] = markup
    put_def(defs_dir, doc, "fx_markup.json")
    h = h_page()
    h.open("fx_markup")
    run_batch_on_page(h)
    assert table_cells(h)[0][1] == markup
    assert h.page.locator("img").count() == 0
    assert h.page.evaluate("window.__pwned") is None


@pytest.mark.tc("TC-WBT-003")
def test_empty_marker_for_null_worst_values(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    for scenario in ("S3", "S4"):
        for column in ("worst_element", "worst_band", "smallest_margin_pct"):
            expect(row(h, scenario).locator(f'td[data-col="{column}"]')).to_have_text("—")
        text = row(h, scenario).text_content()
        assert "null" not in text and "undefined" not in text


@pytest.mark.tc("TC-WBT-004")
def test_table_cleared_on_definition_switch(h_page, defs_dir):
    store(defs_dir, "FX-BATCH", "FX-SINGLE")
    h = h_page()
    h.open("fx_batch")
    run_batch_on_page(h)
    h.open("fx_single")
    expect(h.page.locator("#batch-table tbody tr")).to_have_count(0)
    expect(h.page.locator("#workspace")).to_have_attribute("data-view", "schematic")


@pytest.mark.tc("TC-WBT-004")
def test_a_late_batch_result_is_dropped_after_a_switch(h_page, defs_dir):
    store(defs_dir, "FX-BATCH", "FX-SINGLE")
    h = h_page()
    held = []
    h.page.route("**/fx_batch/batch", lambda route: held.append(route))
    h.open("fx_batch")
    h.page.click("#run-batch")
    expect(h.page.locator("#run-batch")).to_be_disabled()
    h.open("fx_single")
    assert len(held) == 1
    with h.page.expect_response(lambda r: r.url.endswith("/fx_batch/batch")):
        held[0].continue_()
    h.settle()
    expect(h.page.locator("#batch-table tbody tr")).to_have_count(0)
    expect(h.page.locator("#export-csv")).to_be_disabled()
    expect(h.page.locator("#workspace")).to_have_attribute("data-view", "schematic")
    expect(h.page.locator("#run-batch")).to_be_enabled()


@pytest.mark.tc("TC-WBT-005")
def test_batch_js_is_an_es_module(h_page):
    h = h_page()
    loaded = []
    h.page.on(
        "response",
        lambda r: loaded.append(r) if r.url.endswith("/batch.js") else None,
    )
    h.reload()
    assert len(loaded) == 1
    response = loaded[0]
    assert response.status == 200
    request = response.request
    assert request.resource_type == "script"
    # It is requested by app.js, in the CORS mode of a module import. A script tag sends neither.
    headers = request.all_headers()
    assert headers["referer"].endswith("/app.js")
    assert "origin" in headers
    assert response.body() == (WEB / "batch.js").read_bytes()
    assert "batch.js" not in (WEB / "index.html").read_text("utf-8")
    assert re.search(r"import\s*\{[^}]*\}\s*from\s*[\"']./batch.js[\"']", (WEB / "app.js").read_text("utf-8"))
    assert not re.search(r"react|vue|angular|svelte", (WEB / "batch.js").read_text("utf-8"), re.IGNORECASE)


@pytest.mark.tc("TC-WBT-007")
def test_expanded_detail(h_page, defs_dir):
    store(defs_dir, "FX-BATCH", "FX-RING")
    h = h_page()
    h.open("fx_batch")
    run_batch_on_page(h)
    s5 = expand(h, "S5")
    entries = s5.locator("li.overload")
    expect(entries).to_have_count(3)
    texts = entries.all_text_contents()
    assert sorted(texts) == [
        "G1 Continuous 2200 W / 2000 W",
        "G1 Transient 3300 W / 3000 W",
        "T13 Transient 2200 W / 1500 W",
    ]
    assert "AC sources paralleled" in expand(h, "S3").text_content()
    s4 = expand(h, "S4")
    expect(s4.locator("li.unpowered .load-name")).to_have_text(["LA1"])

    h.open("fx_ring")
    run_batch_on_page(h)
    warning = expand(h, "M1").locator("li.warning")
    expect(warning).to_have_count(1)
    assert "meshed_island" in warning.text_content()
    assert "T23" in warning.text_content()


@pytest.mark.tc("TC-WBT-008")
def test_expand_control_is_separate(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    before = len(h.log)
    expand(h, "S5")
    h.settle()
    assert len(h.log) == before
    assert h.page.input_value("#scenario-select") == ""
    expect(h.page.locator("#workspace")).to_have_attribute("data-view", "batch")
    row(h, "S5").locator("button.expand").click()
    expect(detail(h, "S5")).to_be_hidden()
    assert len(h.log) == before


@pytest.mark.tc("TC-WBT-009")
def test_row_opens_the_scenario(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    expected = row(h, "S5").locator('td[data-col="result"]').text_content()
    row(h, "S5").locator('td[data-col="name"]').click()
    expect(h.page.locator("#workspace")).to_have_attribute("data-view", "schematic")
    expect(h.page.locator("#schematic")).to_be_visible()
    assert h.page.input_value("#scenario-select") == "S5"
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    expect(h.page.locator("#status-verdict")).to_have_text(expected)
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    # Back in the schematic, the batch table is still there for the next row.
    h.page.click("#show-batch")
    expect(h.page.locator(ROWS)).to_have_count(5)


@pytest.mark.tc("TC-WBT-009")
def test_row_opens_the_scenario_from_the_keyboard(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    row(h, "S2").focus()
    h.page.keyboard.press("Enter")
    expect(h.page.locator("#workspace")).to_have_attribute("data-view", "schematic")
    assert h.page.input_value("#scenario-select") == "S2"
    expect(h.group("G1")).to_have_attribute("data-state", "failed")


@pytest.mark.tc("TC-WBT-010")
def test_export_downloads(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    run_batch_on_page(h)
    for kind, control in (("csv", "#export-csv"), ("json", "#export-json")):
        with h.page.expect_download() as download:
            h.page.click(control)
        saved = Path(download.value.path()).read_bytes()
        reply = httpx.get(f"{h.server.url}/api/definitions/fx_batch/batch/export", params={"format": kind})
        assert reply.status_code == 200
        assert saved == reply.content
        assert download.value.suggested_filename.endswith(f".{kind}")
        assert b"\xe2\x88\x92" not in saved


@pytest.mark.tc("TC-WBT-011")
def test_export_disabled_before_a_run(h_page, defs_dir):
    store(defs_dir, "FX-BATCH", "FX-SINGLE")
    h = h_page()
    h.open("fx_batch")
    controls = [h.page.locator("#export-csv"), h.page.locator("#export-json")]

    def check(disabled):
        for control in controls:
            if disabled:
                expect(control).to_be_disabled()
            else:
                expect(control).to_be_enabled()

    check(True)
    run_batch_on_page(h)
    check(False)
    h.open("fx_single")
    check(True)
    h.open("fx_batch")
    check(True)
    expect(h.page.locator("#batch-table tbody tr")).to_have_count(0)


@pytest.mark.tc("TC-WBT-012")
def test_published_batch_dom_hooks(h_page):
    h = h_page()
    h.open("generic_twin")
    for id_ in ("run-batch", "batch-table", "export-csv", "export-json"):
        assert h.page.locator(f"[id='{id_}']").count() == 1, id_
    assert h.page.locator("#batch-table").evaluate("e => e.tagName") == "TABLE"


@pytest.mark.tc("TC-WBT-006")
@pytest.mark.meta
def test_batch_front_end_has_browser_tests(e2e_run):
    from test_traceability import (
        DEFERRED_CASES,
        collected_marked,
        covered_by,
        matrix,
        requirement_ids,
    )

    waiting = {r for case in DEFERRED_CASES for r in matrix()[case]}
    section = {
        r for r in requirement_ids() - waiting
        if r.startswith("L2-WBT-") and r not in ("L2-WBT-005", "L2-WBT-006")
    }
    assert len(section) == 11
    covered = covered_by(collected_marked("e2e and not meta"))
    assert sorted(section - covered) == []
    assert e2e_run.returncode == 0, e2e_run.stdout[-3000:]
