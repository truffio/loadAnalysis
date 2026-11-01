"""C-WEBINT cases on the text of the schematic: names, room for text, and numbers at the extremes.

Text is measured as the browser draws it, so a name that does not fit, two texts that touch and a
text cut off by the edge of the drawing are found in real boxes (tests/textfit.py), not guessed from
character counts.
"""

import httpx
import pytest
import textfit
from conftest import find, fx, put_def, setp
from playwright.sync_api import expect
from test_web_interactive import analyse_api, label_text, store, tooltip_of

pytestmark = pytest.mark.e2e

ELLIPSIS = "…"
EDGE = 1.5  # the halo that sets text off from a line behind it widens the measured box by about 1


def drawn_names(h):
    """Id to the text drawn as its name."""
    return {
        t["forId"]: t["text"] for t in textfit.measure(h.page)["texts"] if t["kind"] == "name"
    }


def layout_of(h, def_id):
    return httpx.get(f"{h.server.url}/api/definitions/{def_id}").json()["layout"]


def names_of(doc):
    return {e["id"]: e["name"] for key in ("sources", "trus", "buses") for e in doc[key]}


def is_cut_from(drawn, name):
    return drawn.endswith(ELLIPSIS) and drawn != name and name.startswith(drawn[:-1].rstrip())


# --- Names ----------------------------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-053")
def test_names_are_drawn_cut_with_an_ellipsis_and_the_id_is_in_the_tooltip(h_page, defs_dir):
    long_gen = "Engine driven generator number one on the left wing"
    long_bus = "AC MAIN DISTRIBUTION BUS WITH A VERY LONG NAME"
    doc = fx("FX-SINGLE")
    for id_, name in (("G1", long_gen), ("AC1", long_bus), ("TRU1", "Main TRU"), ("DC1", "DC 1")):
        find(doc, id_)["name"] = name
    put_def(defs_dir, doc, "fx_names.json")
    h = h_page()
    h.open("fx_names")
    names = drawn_names(h)
    # The name is what a person reads, and the id is not drawn.
    assert names["TRU1"] == "Main TRU"
    assert names["DC1"] == "DC 1"
    assert "TRU1" not in names.values() and "G1" not in names.values()
    # A name that does not fit is cut, never dropped, and what is left starts the full name.
    assert is_cut_from(names["G1"], long_gen)
    assert is_cut_from(names["AC1"], long_bus)
    # Cut text stays inside its room: the label box of an icon, the bar of a bus.
    layout = layout_of(h, "fx_names")
    items = {i["id"]: i for i in layout["items"]}
    boxes = {t["forId"]: t for t in textfit.measure(h.page)["texts"] if t["kind"] == "name"}
    for id_ in ("G1", "TRU1"):
        box, text = items[id_]["label"], boxes[id_]
        assert box["x"] - EDGE <= text["x"] and text["r"] <= box["x"] + box["width"] + EDGE, id_
    x, _, w, _ = h.in_layout_units("AC1")
    assert x - EDGE <= boxes["AC1"]["x"] and boxes["AC1"]["r"] <= x + w + EDGE
    # The full name and the id are in the tooltip.
    for id_, full in (("G1", long_gen), ("AC1", long_bus), ("TRU1", "Main TRU")):
        tip = tooltip_of(h, id_)
        assert tip.locator(".tt-title").text_content() == full
        assert tip.locator('dd[data-fact="id"]').text_content() == id_


@pytest.mark.tc("TC-WIN-053")
def test_a_name_is_cut_only_when_it_does_not_fit(h_page, defs_dir):
    doc = fx("FX-SINGLE")
    find(doc, "G1")["name"] = "Generator 1"
    find(doc, "AC1")["name"] = "AC BUS 1"
    put_def(defs_dir, doc, "fx_fits.json")
    h = h_page()
    h.open("fx_fits")
    assert drawn_names(h)["G1"] == "Generator 1"
    assert drawn_names(h)["AC1"] == "AC BUS 1"
    # A narrow room cuts the same name, so the cut follows the room and not the name.
    cuts = h.page.evaluate(
        """async () => {
            const m = await import('/schematic.js');
            const text = document.querySelector('#schematic .names .icon-name');
            return [200, 40, 20, 5].map(room => m.fitText(text, 'Generator 1', room));
        }"""
    )
    assert cuts[0] == "Generator 1"
    assert all(c.endswith(ELLIPSIS) for c in cuts[1:])
    assert [len(c) for c in cuts[1:]] == sorted((len(c) for c in cuts[1:]), reverse=True)
    assert cuts[3] == ELLIPSIS  # never nothing


# --- Room for text --------------------------------------------------------------------------------

STATES = {"FX-50N": [{}, {"G1": "failed", "G3": "failed"}], "FX-8ENGN": [{}, {"G2": "failed"}]}


def open_and_apply(h, def_name, states):
    h.open(def_name.lower().replace("-", "_"))
    for id_, state in states.items():
        h.group(id_).click()
        expect(h.group(id_)).to_have_attribute("data-state", state)


@pytest.mark.tc("TC-WIN-054")
@pytest.mark.parametrize(
    ("def_name", "states", "band"),
    [
        (name, states, band)
        for name, options in STATES.items()
        for states in options
        for band in ("continuous", "transient")
    ],
    ids=lambda v: str(v) if not isinstance(v, dict) else ",".join(v) or "default",
)
def test_no_text_overlaps_is_clipped_or_dropped(h_page, defs_dir, def_name, states, band):
    doc = fx(def_name)
    store(defs_dir, def_name)
    h = h_page()
    open_and_apply(h, def_name, states)
    h.page.select_option("#band-select", band)
    layout = layout_of(h, def_name.lower().replace("-", "_"))
    assert len(layout["items"]) in (49, 50)
    assert textfit.problems(h.page, layout["width"], layout["height"]) == []
    # Every element with a name shows it, and the names that fit are shown whole.
    drawn = drawn_names(h)
    for id_, name in names_of(doc).items():
        assert id_ in drawn, f"{id_} has no name drawn"
        assert drawn[id_] == name or is_cut_from(drawn[id_], name), (id_, drawn[id_], name)
    for bus in doc["buses"]:
        assert drawn[bus["id"]] == bus["name"], f"{bus['id']} is cut: {drawn[bus['id']]}"
    # Every text lies in the box the layout reserved for it, so the room is not borrowed.
    items = {i["id"]: i for i in layout["items"]}
    for t in textfit.measure(h.page)["texts"]:
        if t["forId"] in items and not t["cls"].startswith("bus-name"):
            box = items[t["forId"]]["label"]
            assert box["x"] - EDGE <= t["x"] and t["r"] <= box["x"] + box["width"] + EDGE, t


@pytest.mark.tc("TC-WIN-054")
def test_overload_notes_stay_clear_of_other_text(h_page, defs_dir):
    # "over: Transient" is a line more than the layout reserves, so it must still touch nothing.
    doc = fx("FX-50N")
    setp(doc, "$.sources[1].capacity.transient", 100)
    setp(doc, "$.buses[2].capacity", {"transient": 100, "short_term": 1e9, "continuous": 1e9})
    put_def(defs_dir, doc, "fx_over.json")
    h = h_page()
    h.open("fx_over")
    assert "over: Transient" in label_text(h, "G2")
    assert "over: Transient" in label_text(h, "AC3")
    layout = layout_of(h, "fx_over")
    assert textfit.problems(h.page, layout["width"], layout["height"]) == []


@pytest.mark.tc("TC-WIN-054")
def test_text_stays_inside_the_drawing_at_the_edges(h_page, defs_dir):
    # Names of the first and last icon of a wide row are what the left and right edges clip.
    doc = fx("FX-8ENGN")
    store(defs_dir, "FX-8ENGN")
    h = h_page()
    h.open("fx_8engn")
    layout = layout_of(h, "fx_8engn")
    texts = textfit.measure(h.page)["texts"]
    assert min(t["x"] for t in texts) >= 0
    assert max(t["r"] for t in texts) <= layout["width"]
    names = drawn_names(h)
    assert names["G1"] == names_of(doc)["G1"]  # the leftmost icon's name is whole


# --- Numbers at the extremes --------------------------------------------------------------------


@pytest.mark.tc("TC-WIN-055")
def test_number_formats_cope_with_the_largest_and_smallest_values(h_page):
    h = h_page()
    shown = h.page.evaluate(
        """async () => {
            const m = await import('/schematic.js');
            const huge = [1e21, 1e24, -1.2345e25, 1.5e300, 1e20, 999999999999999900000];
            const small = [5e-324, 1e-300, 1e-7, -1e-30, 0];
            return {
                fixed: huge.map(v => m.fmtFixed(v, 2)), fixedSmall: small.map(v => m.fmtFixed(v, 2)),
                num: huge.map(v => m.fmtNum(v)), numSmall: small.map(v => m.fmtNum(v)),
                power: huge.map(m.fmtPower), powerSmall: small.map(m.fmtPower),
                odd: [Infinity, -Infinity, NaN, null, undefined].map(v => [m.fmtFixed(v), m.fmtNum(v), m.fmtPower(v)]),
            };
        }"""
    )
    assert shown["fixed"] == [
        "1.00e+21", "1.00e+24", "-1.23e+25", "1.50e+300", "100000000000000000000.00",
        "999999999999999900000.00",
    ]
    assert shown["num"] == [
        "1e+21", "1e+24", "-1.23e+25", "1.5e+300", "100000000000000000000", "999999999999999900000",
    ]
    assert shown["power"] == [
        "1.00e+21 W", "1.00e+24 W", "-1.23e+25 W", "1.50e+300 W", "100000000000000000.00 kW",
        "999999999999999900.00 kW",
    ]
    assert shown["fixedSmall"] == ["0.00"] * 5
    assert shown["numSmall"] == ["0"] * 5
    assert shown["powerSmall"] == ["0 W"] * 5
    assert shown["odd"] == [["—", "—", "—"]] * 5


@pytest.mark.tc("TC-WIN-055")
def test_legal_extreme_values_are_drawn_without_error(h_page, defs_dir):
    # 1e12 W with a margin of 1e12 is 1e24 W with margin, and a capacity of 1e-300 W is as legal.
    doc = fx("FX-SINGLE")
    setp(doc, "$.settings.safety_margin", 1e12)
    setp(doc, "$.loads[0].power", {"transient": 1e12, "short_term": 1e12, "continuous": 1e12})
    setp(doc, "$.sources[0].capacity", {"transient": 1e-300, "short_term": 1e-300, "continuous": 1e-300})
    put_def(defs_dir, doc, "fx_extreme.json")
    h = h_page()
    h.open("fx_extreme")  # an error raised in the page fails the test at teardown
    reply = analyse_api(h, "fx_extreme")
    assert reply["verdict"] == "FAIL"
    expect(h.page.locator("#status-verdict")).to_have_text("FAIL")
    assert h.page.locator("#status-list li.overload").count() >= 1
    overloads = h.page.locator("#status-list").text_content()
    tip = tooltip_of(h, "G1").text_content()
    assert "e+24" in overloads and "e+24" in tip  # 1e12 W with a margin of 1e12
    for text in (overloads, tip, label_text(h, "AC1"), label_text(h, "G1")):
        assert "NaN" not in text and "undefined" not in text and "Infinity" not in text
