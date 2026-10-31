"""C-LAYOUT: the TC-LAY cases of docs/test-cases.md.

Cases written against FX-SAMPLE also run on larger stand-ins (`sample_docs`), which hold the 50-item
rules to more than the sample's 34 items. TC-LAY-018 and the on-screen half of TC-LAY-017 need the
browser harness, so they wait for E7 (see DEFERRED_CASES in tests/test_traceability.py).
"""

import inspect
import json
import os
import subprocess
import sys
from itertools import combinations, pairwise
from pathlib import Path

import pytest
from conftest import (
    ac,
    apu,
    bat,
    c,
    dc,
    definition,
    fx,
    gen,
    rat_ac,
    rat_dc,
    setp,
    tie,
    tru,
)

from ela.layout import layout
from ela.validate import validate

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "definitions" / "generic_twin.json"
SOURCE_KINDS = ("engine_generator", "apu_generator", "emergency_generator", "battery")


# --- Stand-in definitions -------------------------------------------------------------------


def twin():
    """A twin to spec §5.3 with the bus names of L2-SMP-003, standing in for FX-SAMPLE."""
    return definition(
        [gen(1), gen(2), apu(), rat_ac(), bat("BAT")],
        [
            ac("AC1", name="AC BUS 1"),
            ac("AC2", name="AC BUS 2"),
            ac("ACESS", name="AC ESS", role="essential"),
            dc("DC1", name="DC BUS 1"),
            dc("DC2", name="DC BUS 2"),
            dc("DCESS", name="DC ESS", role="essential"),
            dc("DCBAT", name="DC BAT", role="battery", crew_switch=True),
        ],
        [
            tru("TRU1", "AC1", "DC1"),
            tru("TRU2", "AC2", "DC2"),
            tru("TRU3", "ACESS", "DCESS"),
        ],
        [
            c("G1", "AC1"),
            c("G2", "AC2"),
            c("APU", "AC1", "open"),
            c("RAT_AC", "ACESS", "open"),
            c("BAT", "DCBAT"),
            tie("BTC", "AC1", "AC2", "open"),
            tie("ETC1", "AC1", "ACESS"),
            tie("ETC2", "AC2", "ACESS", "open"),
            tie("DTC", "DC1", "DC2", "open"),
            tie("DETC1", "DC1", "DCESS"),
            tie("DETC2", "DC2", "DCESS", "open"),
            tie("BATC", "DCESS", "DCBAT"),
        ],
    )


def twin_50():
    """The twin grown to exactly 50 displayed items, with two more emergency buses."""
    doc = twin()
    doc["sources"] += [rat_dc(), bat("BAT2")]
    doc["buses"] += [
        ac("ACGAL", role="other"),
        ac("ACEMER", role="emergency"),
        dc("DCEMER", role="emergency"),
        dc("DCGND", role="other"),
    ]
    extra = tru("TRU4", "ACEMER", "DCEMER")
    doc["trus"].append(extra)
    doc["contactors"] += [
        c("RAT_DC", "DCEMER", "open"),
        c("BAT2", "DCBAT"),
        tie("GTC", "ACGAL", "ACESS"),
        tie("EMTC", "ACESS", "ACEMER", "open"),
        tie("DGTC", "DC2", "DCGND"),
        tie("DEMTC", "DCESS", "DCEMER", "open"),
        tie("MTC", "AC2", "ACEMER", "open"),
        {**tie("TRU4_IN", "ACEMER", "TRU4"), "kind": "tru"},
        {**tie("TRU4_OUT", "TRU4", "DCEMER"), "kind": "tru"},
    ]
    return doc


def four_engine():
    """A 4-engine transport with one AC and DC bus per engine and two essential buses."""
    ks = range(1, 5)
    trus = [tru(f"TRU{k}", f"AC{k}", f"DC{k}") for k in ks] + [tru("TRU5", "ACESS", "DCESS")]
    return definition(
        [gen(k) for k in ks] + [apu(), rat_ac(), bat("BAT")],
        [ac(f"AC{k}", name=f"AC BUS {k}") for k in ks]
        + [ac("ACESS", name="AC ESS", role="essential")]
        + [dc(f"DC{k}", name=f"DC BUS {k}") for k in ks]
        + [
            dc("DCESS", name="DC ESS", role="essential"),
            dc("DCBAT", name="DC BAT", role="battery", crew_switch=True),
        ],
        trus,
        [c(f"G{k}", f"AC{k}") for k in ks]
        + [c("APU", "AC2", "open"), c("RAT_AC", "ACESS", "open"), c("BAT", "DCBAT")]
        + [tie(f"BT{k}", f"AC{k}", f"AC{k + 1}", "open") for k in (1, 2, 3)]
        + [tie("EBT2", "AC2", "ACESS"), tie("EBT3", "AC3", "ACESS", "open")]
        + [tie("DEBT", "DC2", "DCESS"), tie("BATC", "DCESS", "DCBAT")],
    )


def sample_docs():
    """FX-SAMPLE, and stand-ins of the same shape."""
    return [json.loads(SAMPLE.read_text("utf-8")), twin(), twin_50(), four_engine()]


def readable_docs():
    """Everything the 50-item readability rules are held to."""
    return [fx("FX-50"), *sample_docs()]


# --- Reading a layout -----------------------------------------------------------------------


def lay(doc):
    result = validate(doc)
    assert result.errors == []
    return layout(result.definition)


def by_id(drawn):
    return {item["id"]: item for item in drawn["items"]}


def cy(item):
    return item["y"] + item["height"] / 2


def bus_named(doc, name):
    """The id of the one bus whose `name` contains this text."""
    found = [b["id"] for b in doc["buses"] if name in b["name"]]
    assert len(found) == 1, name
    return found[0]


def overlap(a, b):
    return (
        a["x"] < b["x"] + b["width"]
        and b["x"] < a["x"] + a["width"]
        and a["y"] < b["y"] + b["height"]
        and b["y"] < a["y"] + a["height"]
    )


def segments(connector):
    return list(zip(connector["points"], connector["points"][1:], strict=False))


def segment_meets(seg, item):
    """True when a segment touches the closed box of an item."""
    (x1, y1), (x2, y2) = seg
    return (
        min(x1, x2) <= item["x"] + item["width"]
        and max(x1, x2) >= item["x"]
        and min(y1, y2) <= item["y"] + item["height"]
        and max(y1, y2) >= item["y"]
    )


def segments_cross(s, t):
    """True when a horizontal and a vertical segment cross at an interior point of each."""
    for hor, ver in ((s, t), (t, s)):
        (hx1, hy), (hx2, _) = hor
        (vx, vy1), (_, vy2) = ver
        if hor[0][1] == hor[1][1] and ver[0][0] == ver[1][0]:
            low_x, high_x = sorted((hx1, hx2))
            low_y, high_y = sorted((vy1, vy2))
            if low_x < vx < high_x and low_y < hy < high_y:
                return True
    return False


def segments_share_a_line(s, t):
    """True when two segments run along the same line for some length."""
    for axis in (0, 1):
        if s[0][axis] == s[1][axis] == t[0][axis] == t[1][axis]:
            other = 1 - axis
            low = max(min(s[0][other], s[1][other]), min(t[0][other], t[1][other]))
            high = min(max(s[0][other], s[1][other]), max(t[0][other], t[1][other]))
            if low < high:
                return True
    return False


def crossings(drawn):
    pairs = combinations(drawn["connectors"], 2)
    return sum(
        segments_cross(s, t) for a, b in pairs for s in segments(a) for t in segments(b)
    )


def extents(drawn):
    xs = [p[0] for k in drawn["connectors"] for p in k["points"]]
    ys = [p[1] for k in drawn["connectors"] for p in k["points"]]
    for item in drawn["items"]:
        xs += [item["x"], item["x"] + item["width"]]
        ys += [item["y"], item["y"] + item["height"]]
    return max(xs) - min(xs), max(ys) - min(ys)


def fit_scale(drawn):
    width, height = extents(drawn)
    return min(1000 / width, 560 / height)


def assert_no_overlap(doc, drawn):
    crew = {f"{b['id']}_switch": b["id"] for b in doc["buses"] if b.get("crew_switch")}
    for a, b in combinations(drawn["items"], 2):
        if crew.get(a["id"]) == b["id"] or crew.get(b["id"]) == a["id"]:
            # touching its own bar does not count, sitting inside it would
            assert a["y"] >= b["y"] + b["height"] or b["y"] >= a["y"] + a["height"]
        else:
            assert not overlap(a, b), (a, b)


def assert_nothing_through(drawn):
    for connector in drawn["connectors"]:
        ends = {connector["from"], connector["to"]}
        for seg in segments(connector):
            for item in drawn["items"]:
                if item["id"] not in ends:
                    assert not segment_meets(seg, item), (connector, item)


# --- Straight-line inversions, from the definition alone ------------------------------------


def layer_table(doc):
    """Items by layer, top to bottom, and the links between them, independent of the layout."""
    role = {b["id"]: (b["type"], b["role"]) for b in doc["buses"]}

    def bus_layer(bus):
        kind, name = role[bus]
        if kind == "AC":
            return "ac main" if name == "main" else "ac other"
        if name == "main":
            return "dc main"
        return "dc essential" if name == "essential" else "dc other"

    order = [
        "source",
        "source contactor",
        "ac main",
        "ac tie",
        "ac other",
        "tru in",
        "tru",
        "tru out",
        "dc main",
        "dc tie 1",
        "dc essential",
        "dc tie 2",
        "dc other",
    ]
    layers = {name: [] for name in order}
    links = []
    layers["source"] = [s["id"] for s in doc["sources"]]
    for b in doc["buses"]:
        layers[bus_layer(b["id"])].append(b["id"])
    layers["tru"] = [t["id"] for t in doc["trus"]]
    trus = set(layers["tru"])
    for k in doc["contactors"]:
        a, b = k["from"], k["to"]
        if k["kind"] == "source":
            layers["source contactor"].append(k["id"])
        elif k["kind"] == "tru":
            layers["tru in" if b in trus else "tru out"].append(k["id"])
        else:
            pa, pb = bus_layer(a), bus_layer(b)
            if pa == pb:
                continue
            upper = min(pa, pb, key=order.index)
            name = {"ac main": "ac tie", "dc main": "dc tie 1", "dc essential": "dc tie 2"}[upper]
            layers[name].append(k["id"])
        links += [(a, k["id"]), (k["id"], b)]
    used = [layers[name] for name in order if layers[name]]
    # Sources are in their fixed order in both counts (L2-LAY-006).
    rank = {
        s["id"]: (SOURCE_KINDS.index(s["kind"]), s.get("engine") or 0) for s in doc["sources"]
    }
    used[0] = sorted(used[0], key=lambda i: rank[i])
    return used, links


def inversions(layers, links, position):
    index = {item: i for i, layer in enumerate(layers) for item in layer}
    total = 0
    for i in range(len(layers) - 1):
        between = [
            (a, b) if index[a] == i else (b, a)
            for a, b in links
            if {index[a], index[b]} == {i, i + 1}
        ]
        for (a, b), (e, f) in combinations(between, 2):
            if (position[a] - position[e]) * (position[b] - position[f]) < 0:
                total += 1
    return total


def declared_positions(layers):
    return {item: i for layer in layers for i, item in enumerate(layer)}


def drawn_positions(drawn, layers):
    items = by_id(drawn)
    return {
        item: items[item]["x"] + items[item]["width"] / 2 for layer in layers for item in layer
    }


def inversion_counts(doc):
    layers, links = layer_table(doc)
    drawn = lay(doc)
    return (
        inversions(layers, links, drawn_positions(drawn, layers)),
        inversions(layers, links, declared_positions(layers)),
    )


# --- Stand-ins are what they claim ----------------------------------------------------------


@pytest.mark.tc("TC-LAY-016")
def test_stand_ins_have_the_stated_item_counts():
    assert len(lay(twin_50())["items"]) == 50
    assert 45 <= len(lay(four_engine())["items"]) <= 50


# --- Layers ---------------------------------------------------------------------------------


@pytest.mark.tc("TC-LAY-001")
def test_layout_takes_the_definition_alone():
    assert len(inspect.signature(layout).parameters) == 1
    failed = setp(fx("FX-SINGLE"), "$.sources[0].default_state", "failed")
    assert lay(fx("FX-SINGLE")) == lay(failed)


@pytest.mark.tc("TC-LAY-001")
def test_layout_is_deterministic_and_ignores_array_order():
    doc = twin()
    assert lay(doc) == lay(twin())
    shuffled = twin()
    for name in ("buses", "trus"):
        shuffled[name].reverse()
    first, second = by_id(lay(doc)), by_id(lay(shuffled))
    assert [first[i]["y"] for i in first] == [second[i]["y"] for i in first]


@pytest.mark.tc("TC-LAY-001")
def test_layout_does_not_depend_on_the_hash_seed():
    code = (
        "import json, sys; sys.path.insert(0, 'tests')\n"
        "from test_layout import lay, twin_50\n"
        "print(json.dumps(lay(twin_50())))"
    )
    runs = [
        subprocess.run(
            [sys.executable, "-c", code],
            cwd=ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        for seed in ("1", "2")
    ]
    assert runs[0] == runs[1]


@pytest.mark.tc("TC-LAY-017")
def test_entry_point_and_item_fields():
    # The on-screen half of this case, AC1's drawn top edge, belongs to the browser suite (E7).
    drawn = lay(fx("FX-MARGIN"))
    assert {i["id"] for i in drawn["items"]} == {"G1", "C_G1", "AC1"}
    for item in drawn["items"]:
        assert {"id", "kind", "x", "y", "width", "height"} <= set(item)
    assert len(drawn["connectors"]) == 2
    for connector in drawn["connectors"]:
        assert {"from", "to", "points"} <= set(connector)


@pytest.mark.tc("TC-LAY-002")
@pytest.mark.parametrize("doc", sample_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_one_item_per_displayed_element(doc):
    drawn = lay(doc)
    expected = [e["id"] for key in ("sources", "contactors", "buses", "trus") for e in doc[key]]
    crew = [b["id"] for b in doc["buses"] if b.get("crew_switch")]
    expected += [f"{b}_switch" for b in crew]
    assert sorted(i["id"] for i in drawn["items"]) == sorted(expected)
    items = by_id(drawn)
    for item in drawn["items"]:
        assert {"x", "y", "width", "height"} <= set(item)
    assert crew
    for bus in crew:
        bar, switch = items[bus], items[f"{bus}_switch"]
        vertical = max(switch["y"] - (bar["y"] + bar["height"]), bar["y"] - switch["y"] - 20)
        assert vertical <= 16
        assert switch["x"] + switch["width"] >= bar["x"]
        assert switch["x"] <= bar["x"] + bar["width"]


def layer_groups(doc):
    """Item ids in the six groups of TC-LAY-003."""
    trus = {t["id"] for t in doc["trus"]}
    buses = doc["buses"]
    return [
        [s["id"] for s in doc["sources"]],
        [k["id"] for k in doc["contactors"] if k["kind"] == "source"],
        [b["id"] for b in buses if b["type"] == "AC" and b["role"] == "main"],
        [b["id"] for b in buses if b["type"] == "AC" and b["role"] != "main"],
        sorted(trus),
        [b["id"] for b in buses if b["type"] == "DC"],
    ]


@pytest.mark.tc("TC-LAY-003")
@pytest.mark.parametrize(
    "doc", [fx("FX-ROLES"), *sample_docs()], ids=lambda d: d["meta"]["aircraft"]
)
def test_layer_order(doc):
    items = by_id(lay(doc))
    groups = [g for g in layer_groups(doc) if g]
    assert len(groups) == 6
    for upper, lower in pairwise(groups):
        assert max(items[i]["y"] for i in upper) < min(items[i]["y"] for i in lower)


@pytest.mark.tc("TC-LAY-003")
def test_other_ac_bus_shares_the_essential_layer():
    items = by_id(lay(fx("FX-ROLES")))
    assert cy(items["ACO"]) == cy(items["ACE"]) == cy(items["ACM"])


@pytest.mark.tc("TC-LAY-004")
@pytest.mark.parametrize("doc", sample_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_tru_contactors_above_and_below(doc):
    items = by_id(lay(doc))
    for t in doc["trus"]:
        ins = [k for k in doc["contactors"] if k["kind"] == "tru" and k["to"] == t["id"]]
        outs = [k for k in doc["contactors"] if k["kind"] == "tru" and k["from"] == t["id"]]
        assert len(ins) == len(outs) == 1
        assert items[ins[0]["id"]]["y"] < items[t["id"]]["y"] < items[outs[0]["id"]]["y"]


@pytest.mark.tc("TC-LAY-005")
@pytest.mark.parametrize("doc", sample_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_dc_bus_role_order_on_the_sample(doc):
    items = by_id(lay(doc))
    ys = [items[bus_named(doc, name)]["y"] for name in ("DC BUS 1", "DC ESS", "DC BAT")]
    assert ys == sorted(ys)


@pytest.mark.tc("TC-LAY-005")
def test_dc_bus_role_order_on_roles():
    items = by_id(lay(fx("FX-ROLES")))
    assert items["DC1"]["y"] <= items["DCE"]["y"]
    for bus in ("DCM", "DCB", "DCO"):
        assert items["DCE"]["y"] <= items[bus]["y"]


@pytest.mark.tc("TC-LAY-006")
def test_source_layer_order():
    items = by_id(lay(fx("FX-REVERSE")))
    xs = [items[i]["x"] for i in ("G1", "G2", "APU", "RAT_AC", "BAT")]
    assert xs == sorted(xs) and len(set(xs)) == 5


@pytest.mark.tc("TC-LAY-007")
@pytest.mark.parametrize("n", [2, 4, 8, 12])
def test_any_number_of_engines(n):
    doc = fx("FX-ENG", n)
    drawn = lay(doc)
    assert sum(i["kind"] == "engine_generator" for i in drawn["items"]) == n
    assert_no_overlap(doc, drawn)


@pytest.mark.tc("TC-LAY-008")
@pytest.mark.parametrize("doc", sample_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_no_load_or_breaker_items(doc):
    drawn = lay(doc)
    loads = {x["id"] for x in doc["loads"]}
    assert not loads & {i["id"] for i in drawn["items"]}
    assert not {"load", "breaker"} & {i["kind"] for i in drawn["items"]}


@pytest.mark.tc("TC-LAY-009")
def test_layout_has_no_web_dependency():
    assert (ROOT / "ela" / "layout.py").is_file()
    code = (
        "import sys, ela.layout\n"
        "print(*sorted({'fastapi', 'starlette', 'uvicorn'} & set(sys.modules)))"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == ""


# --- Routing --------------------------------------------------------------------------------


@pytest.mark.tc("TC-LAY-010")
@pytest.mark.parametrize("doc", readable_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_connectors_join_the_right_items_orthogonally(doc):
    drawn = lay(doc)
    items = by_id(drawn)
    links = {(k["from"], k["to"]): k for k in drawn["connectors"]}
    for contactor in doc["contactors"]:
        assert (contactor["from"], contactor["id"]) in links
        assert (contactor["id"], contactor["to"]) in links
    assert len(links) == len(drawn["connectors"]) == 2 * len(doc["contactors"])
    for (start, end), connector in links.items():
        points = connector["points"]
        assert len(points) >= 2
        assert on_bounds(points[0], items[start]), connector
        assert on_bounds(points[-1], items[end]), connector
        for a, b in pairwise(points):
            assert a != b
            assert a[0] == b[0] or a[1] == b[1]


def on_bounds(point, item):
    x, y = point
    left, right = item["x"], item["x"] + item["width"]
    top, bottom = item["y"], item["y"] + item["height"]
    inside = left <= x <= right and top <= y <= bottom
    return inside and (x in (left, right) or y in (top, bottom))


@pytest.mark.tc("TC-LAY-011")
def test_same_layer_tie_stays_level():
    items = by_id(lay(fx("FX-BATCH")))
    t12, ac1, ac2 = items["T12"], items["AC1"], items["AC2"]
    assert cy(t12) == cy(ac1) == cy(ac2)
    low, high = sorted((ac1, ac2), key=lambda i: i["x"])
    assert low["x"] + low["width"] <= t12["x"]
    assert t12["x"] + t12["width"] <= high["x"]


@pytest.mark.tc("TC-LAY-011")
def test_tie_past_a_bar_stays_level_and_clear():
    doc = fx("FX-RING")
    drawn = lay(doc)
    items = by_id(drawn)
    assert cy(items["T13"]) == cy(items["T12"]) == cy(items["T23"]) == cy(items["AC1"])
    assert_no_overlap(doc, drawn)
    assert_nothing_through(drawn)


@pytest.mark.tc("TC-LAY-012")
def test_cross_layer_tie_on_roles():
    items = by_id(lay(fx("FX-ROLES")))
    assert items["AC1"]["y"] < items["T1E"]["y"] < items["ACE"]["y"]


@pytest.mark.tc("TC-LAY-012")
@pytest.mark.parametrize("doc", sample_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_cross_layer_tie_on_the_sample(doc):
    items = by_id(lay(doc))
    ess = bus_named(doc, "AC ESS")
    roles = {b["id"]: b["role"] for b in doc["buses"]}
    ties = [
        k
        for k in doc["contactors"]
        if k["kind"] == "bus_tie"
        and ess in (k["from"], k["to"])
        and {roles[k["from"]], roles[k["to"]]} == {"main", roles[ess]}
    ]
    assert ties
    for k in ties:
        low, high = sorted((items[k["from"]]["y"], items[k["to"]]["y"]))
        assert low < items[k["id"]]["y"] < high


@pytest.mark.tc("TC-LAY-013")
def test_barycentre_uncrosses_fx_cross():
    returned, declared = inversion_counts(fx("FX-CROSS"))
    assert returned == 0
    assert declared >= 1


@pytest.mark.tc("TC-LAY-013")
@pytest.mark.parametrize(
    "doc",
    [fx("FX-ENG", 4), fx("FX-50"), *sample_docs()],
    ids=lambda d: f"{d['meta']['aircraft']}-{len(d['contactors'])}",
)
def test_barycentre_does_not_add_crossings(doc):
    returned, declared = inversion_counts(doc)
    assert returned <= declared


@pytest.mark.tc("TC-LAY-014")
def test_independent_chains_do_not_cross():
    drawn = lay(fx("FX-CHAINS"))
    assert crossings(drawn) == 0
    for connector in drawn["connectors"]:
        assert len(connector["points"]) == 2  # each chain is one straight run


@pytest.mark.tc("TC-LAY-015")
@pytest.mark.parametrize("doc", readable_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_no_overlaps_and_no_connector_through_an_item(doc):
    drawn = lay(doc)
    assert_no_overlap(doc, drawn)
    assert_nothing_through(drawn)


@pytest.mark.tc("TC-LAY-015")
@pytest.mark.parametrize("doc", readable_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_connectors_never_run_along_each_other(doc):
    drawn = lay(doc)
    for a, b in combinations(drawn["connectors"], 2):
        for s in segments(a):
            for t in segments(b):
                assert not segments_share_a_line(s, t), (a, b)


def on_polyline(point, connector):
    x, y = point
    return any(
        min(a[0], b[0]) <= x <= max(a[0], b[0]) and min(a[1], b[1]) <= y <= max(a[1], b[1])
        for a, b in segments(connector)
    )


@pytest.mark.tc("TC-LAY-015")
@pytest.mark.parametrize(
    "doc",
    [*readable_docs(), fx("FX-RING"), fx("FX-SRCBRIDGE"), fx("FX-ROLES"), fx("FX-ALLKINDS")],
    ids=lambda d: f"{d['meta']['aircraft']}-{len(d['contactors'])}",
)
def test_no_false_joins(doc):
    """A connector's end or bend on another connector would read as an electrical joint."""
    drawn = lay(doc)
    for a, b in combinations(drawn["connectors"], 2):
        for point in a["points"]:
            assert not on_polyline(point, b), (a, b)
        for point in b["points"]:
            assert not on_polyline(point, a), (a, b)


VALID_FIXTURES = [
    "FX-SINGLE", "FX-CHAIN", "FX-RING", "FX-SRCBRIDGE", "FX-THROUGH", "FX-TWO-TRU", "FX-TIE-DC",
    "FX-TIE-EQ", "FX-BAT", "FX-BAT2", "FX-TRU-RAT", "FX-RAT", "FX-PAR", "FX-ESS", "FX-CREW",
    "FX-MARGIN", "FX-OVERRIDE", "FX-ZERO", "FX-WORST", "FX-EMPTY", "FX-4ENG", "FX-APU",
    "FX-ALLKINDS", "FX-BATCH", "FX-ROLES", "FX-REVERSE", "FX-CHAINS", "FX-CROSS", "FX-COLOURS",
    "FX-TRAN", "FX-DISPLAY",
]  # fmt: skip


@pytest.mark.tc("TC-LAY-015")
@pytest.mark.parametrize("name", VALID_FIXTURES)
def test_every_small_fixture_draws_cleanly(name):
    doc = fx(name)
    drawn = lay(doc)
    assert_no_overlap(doc, drawn)
    assert_nothing_through(drawn)
    assert fit_scale(drawn) >= 1


@pytest.mark.tc("TC-LAY-016")
@pytest.mark.parametrize("doc", readable_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_item_size_at_fit_scale(doc):
    drawn = lay(doc)
    scale = fit_scale(drawn)
    for item in drawn["items"]:
        if item["kind"] != "bus":
            assert item["width"] * scale >= 16
            assert item["height"] * scale >= 16


@pytest.mark.tc("TC-LAY-016")
def test_fx_50_has_50_items():
    assert len(lay(fx("FX-50"))["items"]) == 50


@pytest.mark.tc("TC-LAY-016")
@pytest.mark.parametrize("doc", readable_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_fit_scale_keeps_10_px_text_legible(doc):
    # L2-WIN-016 wants 10 px text at the initial view. A fit scale of 1 or more gives that with a
    # 10-unit font, and the label boxes hold a line of it.
    drawn = lay(doc)
    assert fit_scale(drawn) >= 1
    assert drawn["width"] <= 1000
    assert drawn["height"] <= 560


@pytest.mark.tc("TC-LAY-016")
@pytest.mark.parametrize("doc", readable_docs(), ids=lambda d: d["meta"]["aircraft"])
def test_label_boxes_stay_clear(doc):
    drawn = lay(doc)
    labelled = [i for i in drawn["items"] if "label" in i]
    assert {i["id"] for i in labelled} >= {b["id"] for b in doc["buses"]}
    boxes = [i["label"] for i in labelled]
    for box in boxes:
        assert box["height"] >= 12
        assert 0 <= box["x"] and box["x"] + box["width"] <= drawn["width"]
        assert 0 <= box["y"] and box["y"] + box["height"] <= drawn["height"]
    for a, b in combinations(boxes, 2):
        assert not overlap(a, b)
    for item in labelled:
        box = item["label"]
        for other in drawn["items"]:
            assert not overlap(box, other), (item["id"], other["id"])
        for connector in drawn["connectors"]:
            for seg in segments(connector):
                inner = {
                    "x": box["x"] + 1,
                    "y": box["y"] + 1,
                    "width": box["width"] - 2,
                    "height": box["height"] - 2,
                }
                assert not segment_meets(seg, inner), (item["id"], connector)
