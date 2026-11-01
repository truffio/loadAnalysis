"""C-WEBINT cases from docs/test-cases.md, in a real Chromium page (H-PAGE) on a uvicorn server
(H-SERVER). The browser harness is in tests/conftest.py.

A page is opened after the fixtures a case names are in H-DEFS, with `h = h_page()`. Cases that use
the sample find its elements by the names in L2-SMP-003 and by `kind`, never by assumed ids.
"""

import hashlib
import json
import re
import urllib.request

import httpx
import pytest
from conftest import REPO, contrast, fx, hue_sat, put_def, setp
from playwright.sync_api import expect

from ela.format import format_pct
from ela.layout import layout
from ela.validate import validate

pytestmark = pytest.mark.e2e

SAMPLE = json.loads((REPO / "definitions" / "generic_twin.json").read_text("utf-8"))
WEB = REPO / "web"


def def_id(name):
    return name.lower().replace("-", "_")


def store(defs_dir, *names):
    """Put the named fixtures in H-DEFS as `<fixture id in lower case>.json`."""
    for name in names:
        put_def(defs_dir, fx(name), f"{def_id(name)}.json")


def opened(h_page, defs_dir, name):
    """A page with fixture `name` stored in H-DEFS and opened."""
    store(defs_dir, name)
    h = h_page()
    h.open(def_id(name))
    return h


def sample_bus(name):
    (bus,) = [b for b in SAMPLE["buses"] if name in b["name"]]
    return bus


def sample_generator(engine):
    (src,) = [
        s for s in SAMPLE["sources"] if s["kind"] == "engine_generator" and s["engine"] == engine
    ]
    return src["id"]


def sample_tie(a, b):
    ids = {sample_bus(a)["id"], sample_bus(b)["id"]}
    (tie,) = [
        c for c in SAMPLE["contactors"] if c["kind"] == "bus_tie" and {c["from"], c["to"]} == ids
    ]
    return tie["id"]


def analyse_api(h, def_name, states=None):
    reply = httpx.post(
        f"{h.server.url}/api/definitions/{def_id(def_name)}/analyse", json={"states": states or {}}
    )
    reply.raise_for_status()
    return reply.json()


def switch_of(bus_id):
    return f"{bus_id}_switch"


def tooltip_of(h, id_):
    """Hover an element and return its open tooltip."""
    h.group(id_).hover()
    tip = h.page.locator("#tooltip")
    expect(tip).to_be_visible()
    expect(tip).to_have_attribute("data-for", id_)
    return tip


def tooltip_rows(tip):
    return tip.evaluate(
        """t => Object.fromEntries([...t.querySelectorAll('tr[data-band]')].map(r => [
            r.dataset.band,
            Object.fromEntries([...r.querySelectorAll('td[data-field]')].map(c => [c.dataset.field, c.textContent]))
        ]))"""
    )


def watts(value):
    return f"{format_pct(value)} W"


def label_text(h, id_):
    return h.label(id_).text_content()


# --- C-WEBINT: definitions ----------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-001")
def test_definition_list(h_page, defs_dir):
    store(defs_dir, "FX-SINGLE")
    h = h_page()
    assert {"generic_twin", "fx_single"} <= set(h.options())
    store(defs_dir, "FX-ALLPASS")
    assert "fx_allpass" not in h.options()
    h.reload()
    assert "fx_allpass" in h.options()
    h.open("generic_twin")
    expect(h.page.locator("#schematic [data-id]")).not_to_have_count(0)


@pytest.mark.tc("TC-WIN-002")
def test_upload_control(h_page, defs_dir):
    h = h_page()
    h.page.evaluate("window.__sentinel = 'same page'")
    navigations = []
    h.page.on("framenavigated", lambda frame: navigations.append(frame.url))
    body = json.dumps(fx("FX-SINGLE")).encode()
    with h.page.expect_request(
        lambda r: r.method == "POST" and r.url.endswith("/api/definitions")
    ) as sent:
        h.page.set_input_files(
            "#definition-upload", {"name": "up1.json", "mimeType": "application/json", "buffer": body}
        )
    assert sent.value.url.endswith("/api/definitions")
    expect(h.page.locator('#definition-select option[value="up1"]')).to_have_count(1)
    expect(h.page.locator("#status-verdict")).not_to_be_empty()
    assert navigations == []
    assert h.page.evaluate("window.__sentinel") == "same page"


@pytest.mark.tc("TC-WIN-003")
def test_upload_conflict_message(h_page):
    h = h_page()
    before = h.options()
    body = json.dumps(fx("FX-SINGLE")).encode()
    h.page.set_input_files(
        "#definition-upload", {"name": "generic_twin.json", "mimeType": "application/json", "buffer": body}
    )
    expect(h.page.locator("#message")).to_contain_text("generic_twin.json")
    assert h.options() == before


@pytest.mark.tc("TC-WIN-004")
def test_validation_errors_are_listed(h_page, defs_dir):
    store(defs_dir, "FX-THREEERR")
    h = h_page()
    paths = ["$.loads[0].power", "$.trus[0].efficiency", "$.loads[1].bus"]

    def check():
        entries = h.page.locator("#message li")
        expect(entries).to_have_count(3)
        for path in paths:
            matching = entries.filter(has_text=path)
            expect(matching).to_have_count(1)
            assert len(matching.first.text_content().replace(path, "").strip()) > 3

    h.page.select_option("#definition-select", "fx_threeerr")
    check()
    body = json.dumps(fx("FX-THREEERR")).encode()
    h.page.set_input_files(
        "#definition-upload", {"name": "bad.json", "mimeType": "application/json", "buffer": body}
    )
    expect(h.page.locator("#message")).to_contain_text("bad.json")
    check()
    assert "bad" not in h.options()


@pytest.mark.tc("TC-WIN-005")
def test_no_schematic_for_a_rejected_definition(h_page, defs_dir):
    store(defs_dir, "FX-THREEERR", "FX-SINGLE")
    h = h_page()
    h.open("fx_single")
    expect(h.group("G1")).to_have_count(1)
    h.page.select_option("#definition-select", "fx_threeerr")
    expect(h.page.locator("#message li")).to_have_count(3)
    expect(h.group("G1")).to_have_count(0)
    expect(h.page.locator("#schematic [data-id]")).to_have_count(0)
    expect(h.page.locator("#status-verdict")).to_be_empty()


@pytest.mark.tc("TC-WIN-006")
def test_warnings_are_displayed(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-WARN")
    expect(h.group("G1")).to_have_count(1)
    entry = h.page.locator("#warnings li").filter(has_text="$.zzz")
    expect(entry).to_have_count(1)
    assert len(entry.text_content().replace("$.zzz", "").strip()) > 3


@pytest.mark.tc("TC-WIN-007")
def test_opens_at_defaults(h_page):
    h = h_page()
    h.open("generic_twin")
    assert [entry["states"] for entry in h.log] == [{}]
    bus = sample_bus("DC BAT")
    assert bus["crew_switch"]
    expect(h.group(switch_of(bus["id"]))).to_have_attribute("data-state", "on")


@pytest.mark.tc("TC-WIN-008")
def test_switching_definition_resets_the_view(h_page, defs_dir):
    store(defs_dir, "FX-BATCH", "FX-SINGLE")
    h = h_page()
    h.open("fx_batch")
    expect(h.page.locator("#viewport")).to_have_attribute("transform", re.compile("scale"))
    initial = h.page.locator("#viewport").get_attribute("transform")
    default_states = h.states()
    h.group("G1").click()
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    h.page.select_option("#band-select", "short_term")
    start = h.empty_point()
    h.drag(start, (start[0] + 80, start[1] - 40))
    assert h.page.locator("#viewport").get_attribute("transform") != initial

    for target in ("fx_single", "fx_batch"):
        h.open(target)
        assert h.page.input_value("#band-select") == "continuous"
        assert h.page.input_value("#scenario-select") == ""
        assert "failed" not in h.states().values()
        if target == "fx_batch":
            assert h.states() == default_states
            expect(h.page.locator("#viewport")).to_have_attribute("transform", initial)


# --- C-WEBINT: schematic ------------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-009")
def test_svg_at_api_coordinates(h_page):
    h = h_page()
    h.open("generic_twin")
    assert h.page.evaluate("document.getElementById('schematic').tagName.toLowerCase()") == "svg"
    reply = httpx.get(f"{h.server.url}/api/definitions/generic_twin").json()
    assert reply["layout"]["items"]
    for item in reply["layout"]["items"]:
        x, y, w, hgt = h.in_layout_units(item["id"])
        assert (x, y) == pytest.approx((item["x"], item["y"]), abs=1), item["id"]
        assert (w, hgt) == pytest.approx((item["width"], item["height"]), abs=1), item["id"]


@pytest.mark.tc("TC-WIN-010")
def test_icons_by_kind(h_page):
    h = h_page()
    h.open("generic_twin")
    gen = h.group(sample_generator(1))
    expect(gen.locator("circle")).to_have_count(1)
    expect(gen.locator("text")).to_have_text("G")
    battery = next(s["id"] for s in SAMPLE["sources"] if s["kind"] == "battery")
    tru = SAMPLE["trus"][0]["id"]
    bus = sample_bus("AC BUS 1")["id"]
    symbols = {
        i: h.group(i).get_attribute("data-symbol") for i in (sample_generator(1), battery, tru, bus)
    }
    assert sorted(symbols.values()) == ["battery", "bus", "generator", "tru"]
    expect(h.group(battery).locator("circle")).to_have_count(0)
    expect(h.group(tru).locator("circle")).to_have_count(0)
    for b in SAMPLE["buses"]:
        _, _, w, hgt = h.rect(b["id"])
        assert w > hgt, b["id"]


@pytest.mark.tc("TC-WIN-011")
def test_crew_switch_symbol(h_page):
    h = h_page()
    h.open("generic_twin")
    bus = sample_bus("DC BAT")["id"]
    symbol = h.group(switch_of(bus)).locator(".symbol")
    on = symbol.get_attribute("d")
    h.group(switch_of(bus)).click()
    expect(h.group(switch_of(bus))).to_have_attribute("data-state", "off")
    assert symbol.get_attribute("d") != on
    switches = h.page.locator('#schematic [data-id$="_switch"]').evaluate_all(
        "els => els.map(e => e.dataset.id)"
    )
    assert switches == [switch_of(bus)]


@pytest.mark.tc("TC-WIN-012")
def test_no_load_or_breaker_drawn(h_page):
    h = h_page()
    h.open("generic_twin")
    drawn = h.page.evaluate(
        """() => {
            const svg = document.getElementById('schematic');
            const names = new Set();
            for (const e of svg.querySelectorAll('*')) {
                for (const v of [e.id, e.dataset.id, e.dataset.label, e.getAttribute('name')]) if (v) names.add(v);
            }
            for (const t of svg.querySelectorAll('text, tspan')) names.add(t.textContent.trim());
            return [...names];
        }"""
    )
    for load in SAMPLE["loads"]:
        assert load["id"] not in drawn
        assert load["name"] not in drawn


@pytest.mark.tc("TC-WIN-013")
def test_pan_and_zoom(h_page):
    h = h_page()
    h.open("generic_twin")
    probe = sample_generator(1)
    x0, y0, w0, _ = h.rect(probe)
    start = h.empty_point()
    h.drag(start, (start[0] + 100, start[1]))
    x1, y1, w1, _ = h.rect(probe)
    assert x1 - x0 == pytest.approx(100, abs=1)
    assert y1 - y0 == pytest.approx(0, abs=1)
    assert w1 == pytest.approx(w0, abs=0.01)

    h.page.mouse.move(*h.center(probe))
    h.page.mouse.wheel(0, -300)
    h.settle()
    w2 = h.rect(probe)[2]
    assert w2 > w1
    h.page.mouse.wheel(0, 300)
    h.settle()
    assert h.rect(probe)[2] < w2


@pytest.mark.tc("TC-WIN-014")
def test_a_drag_is_not_a_click(h_page):
    h = h_page()
    h.open("generic_twin")
    gen = sample_generator(1)
    start = h.center(gen)
    h.drag(start, (start[0] + 100, start[1] + 60))
    assert len(h.log) == 1  # only the request made on opening
    expect(h.group(gen)).to_have_attribute("data-state", "operative")

    # A rigid pan keeps the same thing under the pointer, so a real mouse cannot start on empty
    # canvas and finish over a generator. The events are sent as a browser would: down on the
    # canvas, moves, then up on the generator.
    h.reload()
    h.open("generic_twin")
    start = h.empty_point()
    x, y = h.center(gen)
    h.page.evaluate(
        """([start, end, id]) => {
            const svg = document.getElementById('schematic');
            const hit = document.querySelector(`[data-id="${id}"] .hit`);
            const send = (target, type, [px, py], buttons) => target.dispatchEvent(new PointerEvent(type, {
                bubbles: true, pointerId: 42, pointerType: 'mouse', isPrimary: true, button: 0,
                buttons, clientX: px, clientY: py,
            }));
            send(svg, 'pointerdown', start, 1);
            for (let i = 1; i <= 5; i++) {
                send(svg, 'pointermove', [start[0] + (end[0] - start[0]) * i / 5,
                    start[1] + (end[1] - start[1]) * i / 5], 1);
            }
            send(hit, 'pointerup', end, 0);
        }""",
        [list(start), [x, y], gen],
    )
    h.settle()
    assert len(h.log) == 1
    expect(h.group(gen)).to_have_attribute("data-state", "operative")

    h.reload()
    h.open("generic_twin")
    x, y = h.center(gen)
    h.page.mouse.move(x, y)
    h.page.mouse.down()
    h.page.mouse.move(x + 3, y)
    h.page.mouse.up()
    expect(h.group(gen)).to_have_attribute("data-state", "failed")
    assert len(h.log) == 2
    assert h.log[-1]["states"] == {gen: "failed"}


@pytest.mark.tc("TC-WIN-015")
def test_readable_at_1366_by_768(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-50")
    box = h.svg_box()
    assert box["width"] >= 1000
    assert box["height"] >= 560
    ids = h.page.locator("#schematic [data-id]").evaluate_all("els => els.map(e => e.dataset.id)")
    assert len(ids) == 50
    for id_ in ids:
        x, y, w, hgt = h.rect(id_)
        assert box["x"] - 0.5 <= x and x + w <= box["x"] + box["width"] + 0.5, id_
        assert box["y"] - 0.5 <= y and y + hgt <= box["y"] + box["height"] + 0.5, id_
    heights = h.page.locator("#schematic text").evaluate_all(
        "els => els.map(e => e.getBoundingClientRect().height)"
    )
    assert heights
    assert min(heights) >= 10


@pytest.mark.tc("TC-LAY-017")
def test_drawn_top_edge_equals_layout_y(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-MARGIN")
    drawn = layout(validate(fx("FX-MARGIN")).definition)
    (ac1,) = [i for i in drawn["items"] if i["id"] == "AC1"]
    _, y, _, _ = h.in_layout_units("AC1")
    assert y == pytest.approx(ac1["y"], abs=1)
    assert set(ac1) >= {"id", "kind", "x", "y", "width", "height"}
    assert all(set(c) >= {"from", "to", "points"} for c in drawn["connectors"])


@pytest.mark.tc("TC-LAY-018")
def test_item_size_holds_in_the_real_drawing_area(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-50")
    box = h.svg_box()
    assert box["width"] >= 1000
    assert box["height"] >= 560
    kinds = h.page.locator("#schematic [data-id]").evaluate_all(
        "els => els.map(e => [e.dataset.id, e.dataset.kind])"
    )
    assert len(kinds) == 50
    for id_, kind in kinds:
        if kind == "bus":
            continue
        _, _, w, hgt = h.rect(id_)
        assert w >= 16 and hgt >= 16, id_


# --- C-WEBINT: colours --------------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-016")
def test_green_when_energised(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-COLOURS")
    for id_ in ("AC1", "G1", "TRU1", "C_G1"):
        hue, sat = hue_sat(h.colour(id_))
        assert 90 <= hue <= 150, id_
        assert sat > 20, id_


@pytest.mark.tc("TC-WIN-017")
def test_dark_grey_when_deenergised(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-COLOURS")
    background = h.background()
    for id_ in ("AC3", "T13"):
        colour = h.colour(id_)
        assert hue_sat(colour)[1] <= 15, id_
        assert contrast(colour, background) >= 3, id_
        assert max(colour) <= 140, id_  # dark


@pytest.mark.tc("TC-WIN-018")
def test_amber_in_any_band(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-COLOURS")
    for band in ("transient", "short_term", "continuous"):
        h.page.select_option("#band-select", band)
        hue, _ = hue_sat(h.colour("AC2"))
        assert 30 <= hue <= 50, band
        expect(h.group("AC2")).to_have_attribute("data-status", "overloaded")


@pytest.mark.tc("TC-WIN-019")
def test_failure_mark(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-COLOURS")
    background = h.background()
    for id_ in ("G3", "TRU3"):
        colour = h.colour(id_)
        assert hue_sat(colour)[1] <= 15
        assert contrast(colour, background) >= 3
        mark = h.group(id_).locator(".fail-mark")
        expect(mark).to_have_count(1)
        expect(mark).to_be_visible()
    for id_ in ("TRU2", "RAT_AC"):
        expect(h.group(id_)).to_have_attribute("data-status", "deenergised")
        expect(h.group(id_).locator(".fail-mark")).to_have_count(0)
        assert hue_sat(h.colour(id_))[1] <= 15


@pytest.mark.tc("TC-WIN-020")
def test_contactor_state_by_shape(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-COLOURS")
    shape = h.group("T13").locator(".symbol")
    open_shape = shape.get_attribute("d")
    expect(h.group("T13")).to_have_attribute("data-state", "open")
    h.group("T13").click()
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    closed_shape = shape.get_attribute("d")
    assert closed_shape != open_shape
    h.group("T13").click()
    expect(h.group("T13")).to_have_attribute("data-state", "open")
    assert shape.get_attribute("d") == open_shape


# --- C-WEBINT: labels and tooltips --------------------------------------------------------------


@pytest.mark.tc("TC-WIN-021")
def test_bus_labels_show_throughput_and_only_on_live_buses(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-THROUGH")
    ac1 = label_text(h, "AC1")
    assert "115 V" in ac1 and "7.25 A" in ac1 and "2.50 kW" in ac1
    assert "1.00 kW" not in ac1  # own load is 1000 W
    assert "500 W" in label_text(h, "AC2")
    dc1 = label_text(h, "DC1")
    assert "28 V" in dc1 and "30.36 A" in dc1 and "850 W" in dc1
    h.group("G1").click()
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    for bus in ("AC1", "AC2", "DC1"):
        expect(h.label(bus)).to_have_count(0)


@pytest.mark.tc("TC-WIN-022")
def test_band_selector(h_page, defs_dir):
    store(defs_dir, "FX-SINGLE")
    doc = setp(
        fx("FX-SINGLE"),
        "$.settings.bands",
        {
            "transient": {"label": "Peak"},
            "short_term": {"label": "5 s", "duration_s": 5},
            "continuous": {"label": "Continuous"},
        },
    )
    put_def(defs_dir, doc, "fx_peak.json")
    h = h_page()
    h.open("fx_single")
    assert h.page.locator("#band-select option").all_text_contents() == [
        "Transient", "5 s", "Continuous",
    ]
    assert h.page.input_value("#band-select") == "continuous"
    assert "2.00 kW" in label_text(h, "AC1")
    before = len(h.log)
    h.page.select_option("#band-select", "transient")
    expect(h.label("AC1")).to_contain_text("4.00 kW")
    h.settle()
    assert len(h.log) == before
    h.open("fx_peak")
    assert h.page.locator("#band-select option").all_text_contents() == [
        "Peak", "5 s", "Continuous",
    ]


@pytest.mark.tc("TC-WIN-023")
def test_power_display_threshold(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-DISPLAY")
    expected = {"AC1": "999 W", "AC2": "1.00 kW", "AC3": "12.34 kW", "AC5": "1.00 kW"}
    for bus, text in expected.items():
        assert label_text(h, bus).strip().endswith(text), bus
    shown = h.page.evaluate(
        """async () => {
            const m = await import('/schematic.js');
            return {
                power: [999, 1000, 12340, 999.6, 0, 1005, 999.4].map(m.fmtPower),
                pct: [76.625, 12.0, -46.666667, 0.005, -0.001, 56, 100].map(v => m.fmtNum(v)),
                fixed: [7.2463, 1, 2.005, -1.234].map(v => m.fmtFixed(v, 2)),
                none: [m.fmtNum(null), m.fmtPower(undefined)],
            };
        }"""
    )
    assert shown["power"] == ["999 W", "1.00 kW", "12.34 kW", "1.00 kW", "0 W", "1.01 kW", "999 W"]
    assert shown["pct"] == [format_pct(v) for v in (76.625, 12.0, -46.666667, 0.005, -0.001, 56, 100)]
    assert shown["pct"][:3] == ["76.63", "12", "-46.67"]
    assert shown["fixed"] == ["7.25", "1.00", "2.01", "-1.23"]
    assert shown["none"] == ["—", "—"]
    assert "−" not in "".join(shown["pct"])


@pytest.mark.tc("TC-WIN-024")
def test_failed_bands_are_named_on_the_label(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-TRAN")
    ac2 = label_text(h, "AC2")
    assert "Transient" in ac2 and "5 s" in ac2 and "Continuous" not in ac2
    h.page.select_option("#band-select", "transient")
    expect(h.label("AC2")).not_to_contain_text("Transient")
    ac2 = label_text(h, "AC2")
    assert "5 s" in ac2
    ac1 = label_text(h, "AC1")
    assert "5 s" not in ac1 and "Continuous" not in ac1 and "Transient" not in ac1
    h.page.select_option("#band-select", "continuous")
    expect(h.label("AC1")).to_contain_text("Transient")
    g4 = label_text(h, "G4")
    assert "Transient" in g4 and "5 s" in g4
    assert "Transient" in label_text(h, "C_G3")
    expect(h.label("C_G1")).to_have_count(0)  # not overloaded, and a contactor has no value label


@pytest.mark.tc("TC-WIN-025")
def test_tooltip_values(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-TRAN")
    reply = analyse_api(h, "FX-TRAN")
    tip = tooltip_of(h, "AC1")
    rows = tooltip_rows(tip)
    record = reply["el"]["AC1"]
    for band in ("transient", "short_term", "continuous"):
        assert rows[band]["demand"] == watts(record["demand"][band])
        assert rows[band]["with_margin"] == watts(record["with_margin"][band])
        assert rows[band]["capacity"] == watts(record["capacity"][band])
        assert rows[band]["margin"] == (
            f"{watts(record['margin_w'][band])} ({format_pct(record['margin_pct'][band])} %)"
        )
    assert rows["transient"]["margin"] == "-100 W (-10 %)"
    assert "−" not in tip.text_content()

    tip = tooltip_of(h, "C_G1")
    rows = tooltip_rows(tip)
    contactor = reply["el"]["C_G1"]
    assert contactor["capacity"]["transient"] is None
    for band in ("transient", "short_term", "continuous"):
        assert rows[band]["demand"] == watts(contactor["demand"][band])
    assert "no capacity" in tip.text_content()
    assert tip.locator("td[data-field=margin]").count() == 0


@pytest.mark.tc("TC-WIN-026")
def test_hover_opens_the_tooltip_with_name_and_role(h_page):
    h = h_page()
    h.open("generic_twin")
    switch = switch_of(sample_bus("DC BAT")["id"])
    for id_ in (
        sample_generator(1),
        sample_bus("AC BUS 1")["id"],
        SAMPLE["trus"][0]["id"],
        SAMPLE["contactors"][0]["id"],
        switch,
    ):
        tooltip_of(h, id_)
    ess = sample_bus("AC ESS")
    tip = tooltip_of(h, ess["id"])
    assert ess["name"] in tip.text_content()
    assert tip.locator('[data-fact="role"]').text_content() == "essential"
    own = analyse_api(h, "generic_twin")["el"][ess["id"]]["own"]
    rows = tooltip_rows(tip)
    for band in ("transient", "short_term", "continuous"):
        assert rows[band]["own"] == watts(own[band])


@pytest.mark.tc("TC-WIN-027")
def test_touch_tap(h_page, defs_dir):
    store(defs_dir, "FX-BATCH")
    h = h_page(has_touch=True)
    h.open("fx_batch")
    before = h.states()
    h.group("AC2").tap()
    tip = h.page.locator("#tooltip")
    expect(tip).to_be_visible()
    expect(tip).to_have_attribute("data-for", "AC2")
    assert h.states() == before
    assert len(h.log) == 1

    h.group("T12").tap()
    expect(h.group("T12")).to_have_attribute("data-state", "closed")
    expect(tip).to_have_attribute("data-for", "T12")
    expect(tip.locator('[data-fact="state"]')).to_have_text("closed")


@pytest.mark.tc("TC-WIN-028")
def test_source_and_tru_load(h_page, defs_dir):
    store(defs_dir, "FX-DISPLAY", "FX-SINGLE", "FX-COLOURS")
    h = h_page()
    h.open("fx_display")
    g4 = label_text(h, "G4")
    assert "45.00 kW" in g4 and "50 %" in g4
    h.open("fx_single")
    h.page.select_option("#band-select", "transient")
    expect(h.label("TRU1")).to_contain_text("1.70 kW")
    assert "28.33 %" in label_text(h, "TRU1")
    h.open("fx_colours")
    expect(h.group("G3")).to_have_attribute("data-state", "failed")
    expect(h.label("G3")).to_have_count(0)


@pytest.mark.tc("TC-WIN-029")
def test_toggle_sources_trus_and_contactors(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-ALLKINDS")
    for id_ in ("G1", "APU", "BAT", "TRU1"):
        h.group(id_).click()
        expect(h.group(id_)).to_have_attribute("data-state", "failed")
        h.group(id_).click()
        expect(h.group(id_)).to_have_attribute("data-state", "operative")
    h.group("RAT_AC").click()
    expect(h.group("RAT_AC")).to_have_attribute("data-state", "available")
    expect(h.group("RAT_DC")).to_have_attribute("data-state", "unavailable")
    h.group("RAT_AC").click()
    expect(h.group("RAT_AC")).to_have_attribute("data-state", "unavailable")
    for id_ in ("C_G1", "TRU1_IN", "T1E"):
        h.group(id_).click()
        expect(h.group(id_)).to_have_attribute("data-state", "open")
        h.group(id_).click()
        expect(h.group(id_)).to_have_attribute("data-state", "closed")
    h.group("C_RAT_DC").click()
    expect(h.group("C_RAT_DC")).to_have_attribute("data-state", "closed")


@pytest.mark.tc("TC-WIN-030")
def test_toggle_crew_switch(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-ALLKINDS")
    bands = ("transient", "short_term", "continuous")
    tip = tooltip_of(h, "DCB")
    assert [tooltip_rows(tip)[b]["own"] for b in bands] == ["34 W"] * 3
    h.group("DCB_switch").click()
    expect(h.group("DCB_switch")).to_have_attribute("data-state", "off")
    expect(h.group("DCB")).to_have_attribute("data-state", "off")
    expect(tip.locator('[data-fact="crew switch"]')).to_have_text("off")
    assert [tooltip_rows(tip)[b]["own"] for b in bands] == ["0 W"] * 3
    h.group("DCB_switch").click()
    expect(tip.locator('[data-fact="crew switch"]')).to_have_text("on")
    assert [tooltip_rows(tip)[b]["own"] for b in bands] == ["34 W"] * 3


@pytest.mark.tc("TC-WIN-031")
def test_bus_bars_are_not_clickable(h_page):
    h = h_page()
    h.open("generic_twin")
    baseline = len(h.log)
    states = h.states()
    for bus in SAMPLE["buses"]:
        h.group(bus["id"]).click()
    h.settle()
    assert len(h.log) == baseline
    assert h.states() == states


# --- C-WEBINT: interaction ----------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-032")
def test_one_analyse_per_click(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-SINGLE")
    before = len(h.log)
    h.group("G1").click()
    h.page.wait_for_load_state("networkidle")
    assert h.log[before:] == [{"url": h.log[-1]["url"], "states": {"G1": "failed"}}]
    expect(h.group("AC1")).to_have_attribute("data-status", "deenergised")
    assert hue_sat(h.colour("AC1"))[1] <= 15


@pytest.mark.tc("TC-WIN-032")
def test_a_later_click_wins_over_an_earlier_response(h_page, defs_dir):
    store(defs_dir, "FX-BATCH")
    h = h_page()
    held = []

    def hold_the_first(route):
        body = route.request.post_data_json
        if body["states"] == {"G1": "failed"}:
            held.append(route)  # answered later, after the second click's answer
        else:
            route.continue_()

    h.page.route("**/analyse", hold_the_first)
    h.open("fx_batch")
    h.group("G1").click()
    h.group("G2").click()
    expect(h.group("G2")).to_have_attribute("data-state", "failed")
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    assert len(held) == 1
    with h.page.expect_response(
        lambda r: r.url.endswith("/analyse") and r.request.post_data_json["states"] == {"G1": "failed"}
    ):
        held[0].continue_()
    h.settle()
    # The late answer knows nothing of the second click, so drawing it would show G2 operative.
    expect(h.group("G2")).to_have_attribute("data-state", "failed")
    assert h.log[-1]["states"] == {"G1": "failed", "G2": "failed"}
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")


@pytest.mark.tc("TC-WIN-032")
def test_a_click_redraws_in_place_and_keeps_the_view(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-SINGLE")
    h.page.evaluate("window.__marker = document.querySelector('#schematic [data-id=\"G1\"]')")
    start = h.empty_point()
    h.drag(start, (start[0] + 60, start[1] - 20))
    view = h.page.locator("#viewport").get_attribute("transform")
    h.group("G1").click()
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    assert h.page.locator("#viewport").get_attribute("transform") == view
    assert h.page.evaluate(
        "window.__marker === document.querySelector('#schematic [data-id=\"G1\"]')"
    )


@pytest.mark.tc("TC-WIN-026")
def test_definition_text_is_shown_as_text(h_page, defs_dir):
    markup = '<img src=x onerror="window.__pwned = 1">'
    doc = fx("FX-SINGLE")
    doc["sources"][0]["name"] = markup
    doc["buses"][0]["name"] = markup
    doc["scenarios"] = [{"id": "S1", "name": markup, "states": {}}]
    put_def(defs_dir, doc, "fx_markup.json")
    h = h_page()
    h.open("fx_markup")
    assert h.page.locator("#scenario-select option").all_text_contents() == [markup]
    tip = tooltip_of(h, "G1")
    assert markup in tip.text_content()
    tooltip_of(h, "AC1")
    assert h.page.locator("img").count() == 0
    assert h.page.evaluate("window.__pwned") is None


@pytest.mark.tc("TC-WIN-033")
def test_click_to_redraw_within_a_second(h_page):
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
        sample_generator(1), sample_generator(2), SAMPLE["contactors"][0]["id"],
        SAMPLE["contactors"][1]["id"], SAMPLE["trus"][0]["id"],
    ]
    for i in range(20):
        id_ = targets[i % len(targets)]
        before = h.group(id_).get_attribute("data-state")
        h.group(id_).click()
        expect(h.group(id_)).not_to_have_attribute("data-state", before)
    timing = h.page.evaluate("window.__timing")
    assert len(timing) >= 20
    assert max(timing) <= 1000


@pytest.mark.tc("TC-WIN-034")
def test_no_editing_controls(h_page):
    h = h_page()
    h.open("generic_twin")
    kinds = h.page.locator("input").evaluate_all("els => els.map(e => e.type)")
    assert kinds == ["file"]
    assert h.page.locator("textarea, [contenteditable]").count() == 0
    digest = hashlib.sha256((h.defs / "generic_twin.json").read_bytes()).hexdigest()
    ids = [
        sample_generator(1), sample_generator(2), SAMPLE["trus"][0]["id"], SAMPLE["contactors"][0]["id"],
    ]
    for i in range(20):
        id_ = ids[i % len(ids)]
        before = h.group(id_).get_attribute("data-state")
        h.group(id_).click()
        expect(h.group(id_)).not_to_have_attribute("data-state", before)
    assert hashlib.sha256((h.defs / "generic_twin.json").read_bytes()).hexdigest() == digest


@pytest.mark.tc("TC-WIN-035")
def test_reset_keeps_the_band_and_clears_the_scenario(h_page, defs_dir):
    doc = fx("FX-ALLKINDS")
    doc["scenarios"].append({"id": "R1", "name": "G1 lost", "states": {"G1": "failed"}})
    put_def(defs_dir, doc, "fx_allkinds.json")
    h = h_page()
    h.open("fx_allkinds")
    states = h.states()
    verdict = h.page.locator("#status-verdict").text_content()
    h.page.select_option("#band-select", "short_term")
    labels = h.labels()
    assert labels

    h.group("G1").click()
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    h.group("T1E").click()
    expect(h.group("T1E")).to_have_attribute("data-state", "open")
    h.group("DCB_switch").click()
    expect(h.group("DCB_switch")).to_have_attribute("data-state", "off")
    h.page.click("#reset")
    expect(h.group("DCB_switch")).to_have_attribute("data-state", "on")
    assert h.states() == states
    expect(h.page.locator("#status-verdict")).to_have_text(verdict)
    assert h.page.input_value("#band-select") == "short_term"
    assert h.labels() == labels
    assert h.page.input_value("#scenario-select") == ""

    h.page.select_option("#scenario-select", "R1")
    expect(h.group("G1")).to_have_attribute("data-state", "failed")
    h.page.click("#reset")
    expect(h.group("G1")).to_have_attribute("data-state", "operative")
    assert h.states() == states
    assert h.page.input_value("#scenario-select") == ""
    assert h.page.input_value("#band-select") == "short_term"


@pytest.mark.tc("TC-WIN-036")
def test_load_scenario(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    names = [s["name"] for s in fx("FX-BATCH")["scenarios"]]
    assert h.page.locator("#scenario-select option").all_text_contents() == names
    assert len(names) == 5
    h.group("G2").click()
    expect(h.group("G2")).to_have_attribute("data-state", "failed")
    h.page.select_option("#scenario-select", "S5")
    expect(h.group("G2")).to_have_attribute("data-state", "operative")
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")  # hand-worked in FX-BATCH
    assert h.page.input_value("#scenario-select") == "S5"


@pytest.mark.tc("TC-WIN-036")
@pytest.mark.parametrize("scenario_id", ["S07", "S13"])
def test_load_scenario_gives_the_hand_calculated_verdict(h_page, scenario_id):
    hand = json.loads((REPO / "tests" / "data" / "generic_twin_expected.json").read_text("utf-8"))
    h = h_page()
    h.open("generic_twin")
    h.page.select_option("#scenario-select", scenario_id)
    verdict = h.page.locator("#status-verdict")
    expect(verdict).to_have_text(hand["scenarios"][scenario_id]["result"])


@pytest.mark.tc("TC-WIN-046")
def test_a_schematic_click_clears_a_stale_scenario_selection(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    h.page.select_option("#scenario-select", "S5")
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    baseline = len(h.log)
    h.group("AC1").click()
    h.settle()
    assert len(h.log) == baseline
    assert h.page.input_value("#scenario-select") == "S5"
    h.group("T12").click()
    expect(h.group("T12")).to_have_attribute("data-state", "closed")
    assert h.page.input_value("#scenario-select") == ""
    expect(h.group("T13")).to_have_attribute("data-state", "closed")
    h.page.select_option("#scenario-select", "S5")
    expect(h.group("T12")).to_have_attribute("data-state", "open")
    assert h.page.input_value("#scenario-select") == "S5"


# --- C-WEBINT: status panel ---------------------------------------------------------------------


def overload_entries(h):
    return h.page.locator("#status-list li.overload").evaluate_all(
        """els => els.map(e => ({
            element: e.querySelector('.element').textContent,
            band: e.querySelector('.band').textContent,
            with_margin: e.querySelector('.with-margin').textContent,
            capacity: e.querySelector('.capacity').textContent,
        }))"""
    )


@pytest.mark.tc("TC-WIN-037")
def test_status_panel_verdict_and_overloads(h_page, defs_dir):
    store(defs_dir, "FX-BATCH")
    h = h_page()
    h.open("fx_batch")
    expect(h.page.locator("#status-verdict")).to_have_text("PASS")
    h.page.select_option("#scenario-select", "S5")
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    entries = overload_entries(h)
    assert sorted((e["element"], e["band"], e["with_margin"], e["capacity"]) for e in entries) == [
        ("G1", "Continuous", "2200 W", "2000 W"),
        ("G1", "Transient", "3300 W", "3000 W"),
        ("T13", "Transient", "2200 W", "1500 W"),
    ]
    h.open("generic_twin")
    expect(h.page.locator("#status-verdict")).to_have_text("PASS")
    (failing,) = [s for s in SAMPLE["scenarios"] if s["id"] == "S13"]
    assert "designed to fail" in failing["description"]
    h.page.select_option("#scenario-select", failing["id"])
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")


@pytest.mark.tc("TC-WIN-038")
def test_status_panel_configuration_error(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-BATCH")
    h.group("T12").click()
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    expect(h.page.locator("#status-list")).to_contain_text("AC sources paralleled")


@pytest.mark.tc("TC-WIN-047")
def test_status_panel_paralleling_on_the_sample(h_page):
    h = h_page()
    h.open("generic_twin")
    expect(h.page.locator("#status-verdict")).to_have_text("PASS")
    tie = sample_tie("AC BUS 1", "AC BUS 2")
    h.group(tie).click()
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    expect(h.page.locator("#status-list")).to_contain_text("AC sources paralleled")


@pytest.mark.tc("TC-WIN-039")
def test_status_panel_essential_loads(h_page, defs_dir):
    store(defs_dir, "FX-ESS")
    h = h_page()
    h.open("fx_ess")
    h.group("G1").click()
    unpowered = h.page.locator("#status-list li.unpowered .load-name")
    expect(unpowered).to_have_text(["LE1", "LE2"])
    h.group("DCS_switch").click()
    expect(unpowered).to_have_text(["LE1", "LE2", "LE3"])

    h.open("generic_twin")
    bus = sample_bus("DC BAT")["id"]
    h.group(switch_of(bus)).click()
    wanted = [load["name"] for load in SAMPLE["loads"] if load["bus"] == bus and load.get("essential")]
    assert wanted
    expect(h.page.locator("#status-list li.unpowered .load-name")).to_have_text(wanted)


@pytest.mark.tc("TC-WIN-040")
def test_status_panel_mesh_warning(h_page, defs_dir):
    h = opened(h_page, defs_dir, "FX-RING")
    item = h.page.locator("#status-list li.warning")
    expect(item).to_have_count(1)
    assert "meshed_island" in item.text_content()
    assert "T23" in item.text_content()
    expect(h.page.locator("#status-verdict")).to_have_text("PASS")


# --- C-WEBINT: stack ----------------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-041")
def test_no_framework():
    for path in sorted(WEB.iterdir()):
        text = path.read_text("utf-8")
        assert not re.search(r"react|vue|angular|svelte", text, re.IGNORECASE), path.name
        assert not re.search(r"<script[^>]+src=[\"']?(https?:)?//", text, re.IGNORECASE), path.name
        assert not re.search(r"(from|import)\s*[\"']https?:", text), path.name


@pytest.mark.tc("TC-WIN-042")
def test_es_modules_with_no_build_step():
    index = (WEB / "index.html").read_text("utf-8")
    assert re.search(r"<script[^>]*type=\"module\"[^>]*src=\"app\.js\"", index)
    banned = ("package.json", "webpack", "vite", "rollup", "esbuild", "tsconfig")
    skip = {".venv", ".git", "node_modules", ".pytest_cache", ".ruff_cache", "__pycache__"}
    found = []
    for path in REPO.rglob("*"):
        relative = path.relative_to(REPO)
        if skip & set(relative.parts):
            continue
        if path.is_file() and any(word in path.name.lower() for word in banned):
            found.append(str(relative))
    assert found == []
    assert not (WEB / "package.json").exists()


@pytest.mark.tc("TC-WIN-043")
def test_front_end_files(start_server):
    server = start_server()
    for name in ("index.html", "app.js", "schematic.js", "styles.css"):
        assert (WEB / name).is_file(), name
        path = "/" if name == "index.html" else f"/{name}"
        with urllib.request.urlopen(server.url + path) as reply:
            assert reply.status == 200
            assert reply.read() == (WEB / name).read_bytes()


@pytest.mark.tc("TC-WIN-045")
def test_playwright_is_dev_only():
    import tomllib

    config = tomllib.loads((REPO / "pyproject.toml").read_text("utf-8"))
    assert not [d for d in config["project"]["dependencies"] if "playwright" in d.lower()]
    assert [d for d in config["dependency-groups"]["dev"] if "playwright" in d.lower()]
    for path in WEB.iterdir():
        assert "playwright" not in path.read_text("utf-8").lower(), path.name


@pytest.mark.tc("TC-WIN-048")
def test_published_dom_hooks(h_page):
    h = h_page()
    h.open("generic_twin")
    for id_ in (
        "definition-select", "definition-upload", "band-select", "scenario-select", "reset",
        "status-verdict", "status-list", "tooltip", "message", "warnings", "schematic",
    ):
        assert h.page.locator(f"[id='{id_}']").count() == 1, id_
    reply = httpx.get(f"{h.server.url}/api/definitions/generic_twin").json()
    analysis = analyse_api(h, "generic_twin")
    for item in reply["layout"]["items"]:
        group = h.page.locator(f'#schematic [data-id="{item["id"]}"][data-state]')
        assert group.count() == 1, item["id"]
        state = group.get_attribute("data-state")
        if item["kind"] == "bus":
            has_switch = any(b["id"] == item["id"] and b.get("crew_switch") for b in SAMPLE["buses"])
            assert (state != "") == has_switch, item["id"]
            if analysis["el"][item["id"]]["energised"]:
                assert h.label(item["id"]).count() == 1
        else:
            assert state, item["id"]


@pytest.mark.tc("TC-WIN-044")
@pytest.mark.meta
def test_interactive_front_end_has_browser_tests(e2e_run):
    from test_traceability import collected_marked, covered_by, requirement_ids

    section = [
        r
        for r in requirement_ids()
        if r.startswith("L2-WIN-") and (int(r.split("-")[-1]) <= 47 or r == "L2-WIN-053")
    ]
    assert len(section) == 48
    covered = covered_by(collected_marked("e2e and not meta"))
    assert sorted(set(section) - covered) == []
    assert e2e_run.returncode == 0, e2e_run.stdout[-3000:]
