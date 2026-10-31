"""Builders for the named fixtures in docs/test-cases.md, section "Fixtures".

`fx("FX-SINGLE")` returns a fresh parsed-JSON document, so a test may mutate it freely. Test modules
import from here directly (`from conftest import fx, setp`). Ad hoc definitions written inline in a
case use the same primitives: `gen`, `ac`, `dc`, `tru`, `c`, `tie`, `load`, `definition`.

Each builder follows the document text. Fixture defaults (cap 10000, eta 0.85, `name` equal to `id`)
come from the Conventions section there.
"""

import json
import os
import re
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parent.parent

BANDS = ("transient", "short_term", "continuous")


# --- Primitives ---------------------------------------------------------------------------------


def tri(value):
    """A band object from one figure or a (transient, short_term, continuous) triple."""
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, (tuple, list)):
        return dict(zip(BANDS, value, strict=True))
    return dict.fromkeys(BANDS, value)


def _element(id_, **keys):
    over = dict(keys.pop("over", {}))
    if "capacity" in over:
        over["capacity"] = tri(over["capacity"])
    return {"id": id_, "name": id_, **keys, **over}


def gen(n, cap=10000, **over):
    return _element(
        f"G{n}",
        kind="engine_generator",
        engine=n,
        output="AC",
        voltage=115,
        phases=3,
        capacity=tri(cap),
        default_state="operative",
        over=over,
    )


def apu(cap=10000, **over):
    return _element(
        "APU",
        kind="apu_generator",
        output="AC",
        voltage=115,
        phases=3,
        capacity=tri(cap),
        default_state="operative",
        over=over,
    )


def rat_ac(cap=10000, **over):
    return _element(
        "RAT_AC",
        kind="emergency_generator",
        output="AC",
        voltage=115,
        phases=3,
        capacity=tri(cap),
        default_state="unavailable",
        over=over,
    )


def rat_dc(cap=10000, **over):
    return _element(
        "RAT_DC",
        kind="emergency_generator",
        output="DC",
        voltage=28,
        capacity=tri(cap),
        default_state="unavailable",
        over=over,
    )


def bat(id_="BAT", cap=10000, **over):
    return _element(
        id_,
        kind="battery",
        output="DC",
        voltage=28,
        capacity=tri(cap),
        default_state="operative",
        over=over,
    )


def ac(id_, **over):
    return _element(id_, type="AC", role="main", voltage=115, phases=3, over=over)


def dc(id_, **over):
    return _element(id_, type="DC", role="main", voltage=28, over=over)


def tru(id_, input_bus, output_bus, eta=0.85, cap=10000, **over):
    return _element(
        id_,
        input_bus=input_bus,
        output_bus=output_bus,
        efficiency=eta,
        capacity=tri(cap),
        default_state="operative",
        over=over,
    )


def contactor(id_, kind, from_, to, state="closed", **over):
    return _element(id_, kind=kind, default_state=state, over={"from": from_, "to": to, **over})


def c(source_id, bus, state="closed", id_=None, **over):
    """`C_X`: the source contactor from source X to a bus."""
    return contactor(id_ or f"C_{source_id}", "source", source_id, bus, state, **over)


def tie(id_, a, b, state="closed", **over):
    return contactor(id_, "bus_tie", a, b, state, **over)


def tru_contactors(t):
    x = t["id"]
    return [
        contactor(f"{x}_IN", "tru", t["input_bus"], x),
        contactor(f"{x}_OUT", "tru", x, t["output_bus"]),
    ]


def load(id_, bus, power, **over):
    return _element(id_, bus=bus, power=tri(power), over=over)


def scenario(id_, states, name=None, **over):
    return {"id": id_, "name": name if name is not None else id_, "states": states, **over}


def definition(sources, buses, trus=(), contactors=(), loads=(), scenarios=(), margin=0.10):
    """A document with fixture defaults. Each TRU gets its `_IN` and `_OUT` after `contactors`."""
    all_contactors = list(contactors)
    for t in trus:
        all_contactors += tru_contactors(t)
    return {
        "meta": {"aircraft": "Test", "revision": "A"},
        "settings": {"safety_margin": margin},
        "sources": list(sources),
        "buses": list(buses),
        "trus": list(trus),
        "contactors": all_contactors,
        "loads": list(loads),
        "scenarios": list(scenarios),
    }


# --- Document helpers ---------------------------------------------------------------------------


def pick(items, id_):
    """The element with this id from a list of dicts or of models."""
    for item in items:
        got = item["id"] if isinstance(item, dict) else item.id
        if got == id_:
            return item
    raise KeyError(id_)


def find(doc, id_):
    """The element with this id from any collection of a document."""
    for name in ("sources", "buses", "trus", "contactors", "loads", "scenarios"):
        for item in doc[name]:
            if item["id"] == id_:
                return item
    raise KeyError(id_)


def path_of(doc, id_):
    """The `$`-rooted path of the element with this id."""
    for name in ("sources", "buses", "trus", "contactors", "loads", "scenarios"):
        for i, item in enumerate(doc[name]):
            if item["id"] == id_:
                return f"$.{name}[{i}]"
    raise KeyError(id_)


def _walk(doc, path):
    """Parent container and final step of a path such as `$.loads[0].power`."""
    steps = [key or int(i) for key, i in re.findall(r"\.([^.\[]+)|\[(\d+)\]", path)]
    node = doc
    for step in steps[:-1]:
        node = node[step]
    return node, steps[-1]


def setp(doc, path, value):
    """`M: $.path = value`, returning the document."""
    node, last = _walk(doc, path)
    node[last] = value
    return doc


def delp(doc, path):
    """`M: del $.path`, returning the document."""
    node, last = _walk(doc, path)
    del node[last]
    return doc


def swap(item, a="from", b="to"):
    item[a], item[b] = item[b], item[a]


def has_error(result, path, text=""):
    return any(e.path == path and text in e.message for e in result.errors)


def warnings_at(result, path):
    return [w for w in result.warnings if w.path == path]


def run(doc, states=None):
    """Validate a document, which must be valid, and analyse it."""
    from ela.engine import analyse
    from ela.validate import validate

    result = validate(doc)
    assert result.errors == []
    return analyse(result.definition, states if states is not None else {})


def triple(field):
    """A per-band field as a (transient, short_term, continuous) tuple."""
    return tuple(field[b] for b in BANDS)


def D(result, id_):
    """`D(X)` from docs/test-cases.md: the demand of element X as a triple."""
    return triple(result.el[id_].demand)


def near(expected, tol=1e-6):
    """A triple comparison within the case tolerance. One figure means all three bands."""
    import pytest

    if not isinstance(expected, (tuple, list)):
        expected = (expected,) * 3
    return pytest.approx(tuple(expected), abs=tol)


# --- Small definitions --------------------------------------------------------------------------


def fx_single():
    return definition(
        [gen(1, (20000, 15000, 10000))],
        [ac("AC1"), dc("DC1")],
        [tru("TRU1", "AC1", "DC1", 0.85, (6000, 5000, 4000))],
        [c("G1", "AC1")],
        [load("LA", "AC1", (2000, 1500, 1000)), load("LD", "DC1", (1700, 1360, 850))],
    )


def fx_single_e():
    doc = fx_single()
    find(doc, "LA")["essential"] = True
    return doc


def fx_chain():
    return definition(
        [gen(1, 20000)],
        [ac("AC1"), ac("AC2"), ac("AC3")],
        [],
        [c("G1", "AC1"), tie("T12", "AC1", "AC2"), tie("T23", "AC2", "AC3")],
        [load("L1", "AC1", 100), load("L2", "AC2", 200), load("L3", "AC3", 300)],
    )


def fx_ring():
    return definition(
        [gen(1, 20000)],
        [ac("AC1"), ac("AC2"), ac("AC3")],
        [],
        [
            c("G1", "AC1"),
            tie("T12", "AC1", "AC2"),
            tie("T13", "AC1", "AC3"),
            tie("T23", "AC2", "AC3"),
        ],
        [load("L1", "AC1", 100), load("L2", "AC2", 200), load("L3", "AC3", 300)],
        [scenario("M1", {})],
    )


def fx_srcbridge():
    return definition(
        [gen(1, 10000), gen(2, 10000, default_state="failed")],
        [ac("AC1"), ac("AC2")],
        [],
        [c("G1", "AC1", id_="C1A"), c("G1", "AC2", id_="C1B"), c("G2", "AC1")],
        [load("LA", "AC1", 300), load("LB", "AC2", 500)],
    )


def fx_through():
    return definition(
        [gen(1, 20000)],
        [ac("AC1"), ac("AC2"), dc("DC1")],
        [tru("TRU1", "AC1", "DC1", 0.85, (6000, 5000, 4000))],
        [c("G1", "AC1"), tie("T12", "AC1", "AC2")],
        [
            load("LA1", "AC1", (1200, 1100, 1000)),
            load("LA2", "AC2", (700, 600, 500)),
            load("LD", "DC1", (1700, 1360, 850)),
        ],
    )


def fx_two_tru():
    return definition(
        [gen(1, 50000), gen(2, 50000)],
        [ac("AC1"), ac("AC2"), dc("DC1")],
        [
            tru("TRU1", "AC1", "DC1", 0.80, (9000, 7000, 6000)),
            tru("TRU2", "AC2", "DC1", 0.75, (3600, 3200, 3000)),
        ],
        [c("G1", "AC1"), c("G2", "AC2")],
        [load("LD", "DC1", (1800, 1350, 900))],
    )


def fx_tie_dc():
    return definition(
        [gen(1, 50000), gen(2, 50000)],
        [ac("AC1"), ac("AC2"), dc("DC1"), dc("DC2")],
        [
            tru("TRU1", "AC1", "DC1", 0.80, (9000, 7000, 6000)),
            tru("TRU2", "AC2", "DC2", 0.75, (3600, 3200, 3000)),
        ],
        [c("G1", "AC1"), c("G2", "AC2"), tie("T_DC", "DC1", "DC2")],
        [load("LD1", "DC1", 800), load("LD2", "DC2", 100)],
    )


def fx_tie_eq():
    return definition(
        [gen(1, 5000), gen(2, 5000)],
        [ac("AC1"), ac("AC2"), dc("DCA"), dc("DCB")],
        [
            tru("TRU_A", "AC1", "DCA", 0.80, 1000),
            tru("TRU_B", "AC2", "DCB", 0.80, 1000),
        ],
        [c("G1", "AC1"), c("G2", "AC2"), tie("T_DC", "DCA", "DCB")],
        [load("LDA", "DCA", 300), load("LDB", "DCB", 100)],
    )


def fx_bat():
    return definition(
        [gen(1, 5000), bat("BAT", (6000, 4500, 3000))],
        [ac("AC1"), dc("DC1"), dc("DCB")],
        [tru("TRU1", "AC1", "DC1", 0.85, 3000)],
        [c("G1", "AC1"), c("BAT", "DCB"), tie("T_B", "DC1", "DCB")],
        [load("LD", "DC1", 340), load("LB", "DCB", 510)],
    )


def fx_bat2():
    return definition(
        [bat("BAT1", (6000, 4500, 3000)), bat("BAT2", (2000, 1500, 1000))],
        [dc("DC1")],
        [],
        [c("BAT1", "DC1"), c("BAT2", "DC1")],
        [load("L", "DC1", 800)],
    )


def fx_tru_rat():
    return definition(
        [
            gen(1, 20000),
            rat_dc((1000, 3000, 3000), default_state="available"),
            bat("BAT", (6000, 4500, 3000)),
        ],
        [ac("AC1"), dc("DC1")],
        [tru("TRU1", "AC1", "DC1", 0.80, (9000, 7000, 6000))],
        [c("G1", "AC1"), c("RAT_DC", "DC1"), c("BAT", "DC1")],
        [load("L", "DC1", 900)],
    )


def fx_rat():
    return definition(
        [rat_ac(5000), rat_dc(3000)],
        [ac("ACE", role="emergency"), dc("DCE", role="emergency")],
        [],
        [c("RAT_AC", "ACE"), c("RAT_DC", "DCE")],
        [load("LAE", "ACE", 4500), load("LDE", "DCE", 2700)],
    )


def fx_rat_ac_only():
    """FX-RAT without RAT_DC, as TC-VAL-022 and TC-ENG-029 use it. DCE and LDE stay."""
    doc = fx_rat()
    doc["sources"] = [s for s in doc["sources"] if s["id"] != "RAT_DC"]
    doc["contactors"] = [x for x in doc["contactors"] if x["id"] != "C_RAT_DC"]
    return doc


def fx_par():
    return definition(
        [gen(1, 1000), gen(2, 1000)],
        [ac("AC1"), ac("AC2"), dc("DC1")],
        [tru("TRU1", "AC1", "DC1", 0.80, 1000)],
        [c("G1", "AC1"), c("G2", "AC2"), tie("T12", "AC1", "AC2")],
        [load("LA1", "AC1", 1000), load("LA2", "AC2", 3000), load("LD", "DC1", 400)],
    )


def fx_ess():
    return definition(
        [gen(1, 10000), bat("BAT", 1000)],
        [ac("AC1"), dc("DCS", crew_switch=True)],
        [],
        [c("G1", "AC1"), c("BAT", "DCS")],
        [
            load("LE1", "AC1", 100, essential=True),
            load("LE2", "AC1", 200, essential=True),
            load("LN", "AC1", 300),
            load("LE3", "DCS", 50, essential=True),
        ],
    )


def fx_crew():
    return definition(
        [bat("BAT", (6000, 4500, 3000))],
        [dc("DCS", role="battery", crew_switch=True), dc("DCX")],
        [],
        [c("BAT", "DCS"), tie("T_S", "DCS", "DCX")],
        [load("LS", "DCS", (200, 150, 100)), load("LX", "DCX", (300, 250, 200))],
    )


def fx_margin():
    return definition([gen(1, 1100)], [ac("AC1")], [], [c("G1", "AC1")], [load("L1", "AC1", 1000)])


def fx_override():
    return definition(
        [gen(1, 1250, safety_margin=0.25)],
        [ac("AC1", capacity=1100)],
        [],
        [c("G1", "AC1")],
        [load("L1", "AC1", 1000)],
    )


def fx_zero():
    return definition(
        [gen(1, 1000)], [ac("AC1", capacity=0)], [], [c("G1", "AC1")], [load("L1", "AC1", 1)]
    )


def fx_worst():
    return definition(
        [gen(1, 1000), gen(2, 1000), gen(3, 1000)],
        [ac("AC1"), ac("AC2"), ac("AC3")],
        [],
        [c("G1", "AC1"), c("G2", "AC2"), c("G3", "AC3")],
        [load("L1", "AC1", 600), load("L2", "AC2", 880), load("L3", "AC3", 750)],
        margin=0,
    )


def fx_empty():
    return definition(
        [gen(1, 1000), gen(2, 1000)],
        [ac("AC1"), ac("AC2"), dc("DC1")],
        [tru("TRU1", "AC1", "DC1", 0.85, 1000)],
        [c("G1", "AC1"), tie("T12", "AC1", "AC2", "open")],
    )


def fx_eng(n):
    return definition(
        [gen(k, 10000) for k in range(1, n + 1)],
        [ac(f"AC{k}") for k in range(1, n + 1)],
        [],
        [c(f"G{k}", f"AC{k}") for k in range(1, n + 1)],
        [load(f"L{k}", f"AC{k}", 1000) for k in range(1, n + 1)],
    )


def fx_4eng():
    doc = fx_eng(4)
    t = tru("TRU1", "AC1", "DC1", 0.85, 5000)
    doc["buses"].append(dc("DC1"))
    doc["trus"].append(t)
    doc["contactors"] += tru_contactors(t)
    doc["loads"].append(load("LD", "DC1", 425))
    doc["scenarios"] = [scenario("S1", {}), scenario("S2", {"G1": "failed"})]
    return doc


def fx_apu():
    doc = fx_single()
    doc["sources"].append(apu(10000))
    doc["contactors"].append(c("APU", "AC1", "open"))
    return doc


def fx_allkinds():
    return definition(
        [
            gen(1, 20000),
            apu(10000),
            rat_ac(5000),
            rat_dc(3000),
            bat("BAT", (6000, 4500, 3000)),
        ],
        [
            ac("AC1"),
            ac("ACE", role="essential"),
            dc("DC1"),
            dc("DCB", role="battery", crew_switch=True),
        ],
        [tru("TRU1", "AC1", "DC1", 0.85, 5000)],
        [
            c("G1", "AC1"),
            c("APU", "AC1", "open"),
            c("RAT_AC", "ACE", "open"),
            c("RAT_DC", "DC1", "open"),
            c("BAT", "DCB"),
            tie("T1E", "AC1", "ACE"),
            tie("T_DC", "DC1", "DCB"),
        ],
        [
            load("LA", "AC1", 500),
            load("LE", "ACE", 100),
            load("LD", "DC1", 170),
            load("LB", "DCB", 34),
        ],
    )


def fx_batch():
    return definition(
        [gen(1, (3000, 2500, 2000)), gen(2, (3000, 2500, 2000))],
        [ac("AC1"), ac("AC2"), ac("AC3")],
        [],
        [
            c("G1", "AC1"),
            c("G2", "AC2"),
            tie("T12", "AC1", "AC2", "open", capacity=1500),
            tie("T13", "AC1", "AC3", "open", capacity=1500),
        ],
        [
            load("LA1", "AC1", (1000, 900, 800), essential=True),
            load("LA2", "AC2", (1000, 900, 800)),
            load("LX", "AC3", (2000, 1000, 1200)),
        ],
        [
            scenario("S1", {}, "Normal"),
            scenario("S2", {"G1": "failed", "T12": "closed"}, "G1 lost"),
            scenario("S3", {"T12": "closed"}, "Paralleled"),
            scenario("S4", {"G1": "failed", "G2": "failed"}, "Dark"),
            scenario("S5", {"T13": "closed"}, 'Overload, tie to "AC3" — T13'),
        ],
    )


def fx_allpass():
    doc = fx_batch()
    doc["scenarios"] = doc["scenarios"][:2]
    return doc


def fx_batch12():
    doc = fx_batch()
    cycle = doc["scenarios"]
    ids = ["Z01", "A02", "M03", "B04", "Y05", "C06", "X07", "D08", "W09", "E10", "V11", "F12"]
    doc["scenarios"] = [
        {**cycle[i % len(cycle)], "id": id_} for i, id_ in enumerate(ids)
    ]
    return doc


def fx_roles():
    return definition(
        [gen(1), gen(2), apu(), rat_ac(), bat("BAT")],
        [
            ac("AC1"),
            ac("AC2"),
            ac("ACE", role="essential"),
            ac("ACM", role="emergency"),
            ac("ACO", role="other"),
            dc("DC1"),
            dc("DCE", role="essential"),
            dc("DCM", role="emergency"),
            dc("DCB", role="battery"),
            dc("DCO", role="other"),
        ],
        [tru("TRU1", "AC1", "DC1", 0.85, 5000)],
        [
            c("G1", "AC1"),
            c("G2", "AC2"),
            c("APU", "AC1", "open"),
            c("RAT_AC", "ACM"),
            c("BAT", "DCB"),
            tie("T12", "AC1", "AC2", "open"),
            tie("T1E", "AC1", "ACE"),
            tie("TEM", "ACE", "ACM", "open"),
            tie("TEO", "ACE", "ACO"),
            tie("T_DE", "DC1", "DCE"),
            tie("T_EM", "DCE", "DCM"),
            tie("T_EB", "DCE", "DCB"),
            tie("T_EO", "DCE", "DCO"),
        ],
    )


def fx_reverse():
    """The case text gives no bus ids. `B_<source>` is used here."""
    sources = [bat("BAT"), rat_ac(), apu(), gen(2), gen(1)]
    buses = [dc("B_BAT")] + [ac(f"B_{s['id']}") for s in sources[1:]]
    return definition(
        sources, buses, [], [c(s["id"], b["id"]) for s, b in zip(sources, buses, strict=True)]
    )


def fx_chains():
    return definition(
        [gen(2), gen(1)],
        [dc("DC2"), ac("AC2"), dc("DC1"), ac("AC1")],
        [tru("TRU2", "AC2", "DC2"), tru("TRU1", "AC1", "DC1")],
        [c("G2", "AC2"), c("G1", "AC1")],
    )


def fx_cross():
    return definition(
        [gen(1), gen(2)],
        [ac("AC2"), ac("AC1"), dc("DC1"), dc("DC2")],
        [tru("TRU_A", "AC1", "DC2"), tru("TRU_B", "AC2", "DC1")],
        [c("G1", "AC1"), c("G2", "AC2")],
    )


def fx_50():
    ks = range(1, 7)
    return definition(
        [gen(k) for k in ks] + [bat("BAT")],
        [ac(f"AC{k}") for k in ks]
        + [dc(f"DC{k}") for k in range(1, 6)]
        + [dc("DC6", crew_switch=True)],
        [tru(f"TRU{k}", f"AC{k}", f"DC{k}") for k in ks],
        [c(f"G{k}", f"AC{k}") for k in ks]
        + [tie(f"T{k}{k + 1}", f"AC{k}", f"AC{k + 1}", "open") for k in range(1, 6)]
        + [c("BAT", "DC6")],
    )


def fx_colours():
    return definition(
        [
            gen(1, 100000),
            gen(2, 100000),
            gen(3, 100000, default_state="failed"),
            rat_ac(5000),
        ],
        [
            ac("AC1"),
            ac("AC2", capacity=100),
            ac("AC3"),
            ac("ACE"),
            dc("DC1"),
            dc("DC2"),
            dc("DC3"),
        ],
        [
            tru("TRU1", "AC1", "DC1", 0.85, 5000),
            tru("TRU2", "AC3", "DC2", 0.85, 5000),
            tru("TRU3", "AC1", "DC3", 0.85, 5000, default_state="failed"),
        ],
        [
            c("G1", "AC1"),
            c("G2", "AC2"),
            c("G3", "AC3"),
            c("RAT_AC", "ACE"),
            tie("T13", "AC1", "AC3", "open"),
        ],
        [
            load("LA1", "AC1", 1000),
            load("LA2", "AC2", (1000, 50, 50)),
            load("LD", "DC1", 850),
        ],
    )


def fx_tran():
    return definition(
        [gen(1, 100000), gen(2, 100000), gen(3, 100000), gen(4, 1000)],
        [ac("AC1", capacity=1000), ac("AC2", capacity=1000), ac("AC3"), ac("AC4")],
        [],
        [c("G1", "AC1"), c("G2", "AC2"), c("G3", "AC3", capacity=100), c("G4", "AC4")],
        [
            load("LT1", "AC1", (1000, 500, 100)),
            load("LT2", "AC2", (1000, 950, 100)),
            load("LT3", "AC3", (500, 50, 50)),
            load("LT4", "AC4", (1000, 1000, 500)),
        ],
    )


def fx_display():
    powers = [999, 1000, 12340, 45000, 999.6]
    ks = range(1, 6)
    return definition(
        [gen(k, 90000 if k == 4 else 100000) for k in ks],
        [ac(f"AC{k}") for k in ks],
        [],
        [c(f"G{k}", f"AC{k}") for k in ks],
        [load(f"L{k}", f"AC{k}", powers[k - 1]) for k in ks],
    )


# --- Faulty documents ---------------------------------------------------------------------------


def fx_threeerr():
    doc = fx_single_e()
    delp(doc, "$.loads[0].power.short_term")
    setp(doc, "$.trus[0].efficiency", 1.5)
    setp(doc, "$.loads[1].bus", "NOBUS")
    return doc


def fx_five():
    doc = fx_single()
    delp(doc, "$.meta.revision")
    setp(doc, "$.loads[1].id", "LA")
    setp(doc, "$.loads[0].bus", "NOBUS")
    swap(doc["trus"][0], "input_bus", "output_bus")
    doc["contactors"].append(tie("TBAD", "AC1", "DC1"))
    return doc


def fx_many():
    doc = fx_threeerr()
    delp(doc, "$.settings.safety_margin")
    setp(doc, "$.loads[0].power.transient", -1)
    setp(doc, "$.buses[0].voltage", 0)
    doc["loads"].append(load("LA", "AC1", 1))
    doc["contactors"].append(tie("TBAD", "AC1", "DC1"))
    doc["scenarios"].append(scenario("S1", {"GHOST": "failed", "G1": "closed"}, "n"))
    return doc


def fx_warn():
    return setp(fx_single(), "$.zzz", 1)


def fx_malformed():
    """The 20 parsed documents, in the order of the case text."""
    all_null = dict.fromkeys(fx_single())
    return [
        [],
        {},
        None,
        42,
        "text",
        True,
        [{}],
        {"meta": 1},
        {"sources": {}},
        setp(fx_single(), "$.sources", "x"),
        setp(fx_single(), "$.buses", [1, 2]),
        setp(fx_single(), "$.loads", [None]),
        setp(fx_single(), "$.contactors", [{}]),
        setp(fx_single(), "$.settings", []),
        setp(fx_single(), "$.scenarios", {"a": 1}),
        setp(fx_single(), "$.loads[0].power", 5),
        setp(fx_single(), "$.sources[0].capacity", "big"),
        setp(fx_single(), "$.scenarios", [{"id": "S", "name": "n", "states": []}]),
        setp(fx_single(), "$.trus[0].efficiency", None),
        all_null,
    ]


_BUILDERS = {
    "FX-SINGLE": fx_single,
    "FX-SINGLE-E": fx_single_e,
    "FX-CHAIN": fx_chain,
    "FX-RING": fx_ring,
    "FX-SRCBRIDGE": fx_srcbridge,
    "FX-THROUGH": fx_through,
    "FX-TWO-TRU": fx_two_tru,
    "FX-TIE-DC": fx_tie_dc,
    "FX-TIE-EQ": fx_tie_eq,
    "FX-BAT": fx_bat,
    "FX-BAT2": fx_bat2,
    "FX-TRU-RAT": fx_tru_rat,
    "FX-RAT": fx_rat,
    "FX-PAR": fx_par,
    "FX-ESS": fx_ess,
    "FX-CREW": fx_crew,
    "FX-MARGIN": fx_margin,
    "FX-OVERRIDE": fx_override,
    "FX-ZERO": fx_zero,
    "FX-WORST": fx_worst,
    "FX-EMPTY": fx_empty,
    "FX-ENG": fx_eng,
    "FX-4ENG": fx_4eng,
    "FX-APU": fx_apu,
    "FX-ALLKINDS": fx_allkinds,
    "FX-BATCH": fx_batch,
    "FX-ALLPASS": fx_allpass,
    "FX-BATCH12": fx_batch12,
    "FX-ROLES": fx_roles,
    "FX-REVERSE": fx_reverse,
    "FX-CHAINS": fx_chains,
    "FX-CROSS": fx_cross,
    "FX-50": fx_50,
    "FX-COLOURS": fx_colours,
    "FX-TRAN": fx_tran,
    "FX-DISPLAY": fx_display,
    "FX-THREEERR": fx_threeerr,
    "FX-FIVE": fx_five,
    "FX-MANY": fx_many,
    "FX-WARN": fx_warn,
    "FX-MALFORMED": fx_malformed,
}


def fx(name, *args):
    """A fresh copy of a named fixture: `fx("FX-SINGLE")`, `fx("FX-ENG", 8)`."""
    return _BUILDERS[name](*args)


# --- HTTP harness (H-DEFS, H-CLIENT, H-SERVER) --------------------------------------------------


def put_def(folder, doc, name):
    """Store a fixture document (or raw text or bytes) in a definitions folder as `name`."""
    path = Path(folder) / name
    if isinstance(doc, bytes):
        path.write_bytes(doc)
    elif isinstance(doc, str):
        path.write_text(doc, encoding="utf-8")
    else:
        path.write_text(json.dumps(doc), encoding="utf-8")
    return path


@pytest.fixture
def defs_dir(tmp_path, monkeypatch):
    """H-DEFS: a temporary definitions folder holding generic_twin.json, set as ELA_DEFINITIONS_DIR.

    A test adds the fixtures it names with `put_def(defs_dir, fx("FX-SINGLE"), "fx_single.json")`.
    """
    folder = tmp_path / "defs"
    folder.mkdir()
    shutil.copyfile(REPO / "definitions" / "generic_twin.json", folder / "generic_twin.json")
    monkeypatch.setenv("ELA_DEFINITIONS_DIR", str(folder))
    return folder


@pytest.fixture
def client(defs_dir):
    """H-CLIENT: a FastAPI TestClient on `ela.api.app` with H-DEFS set."""
    from fastapi.testclient import TestClient

    from ela.api import app

    return TestClient(app)


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class Server:
    """A `uvicorn ela.api:app` subprocess on a free port."""

    def __init__(self, env_dir=None, cwd=None, extra_args=()):
        self.port = free_port()
        env = {k: v for k, v in os.environ.items() if k != "ELA_DEFINITIONS_DIR"}
        if env_dir is not None:
            env["ELA_DEFINITIONS_DIR"] = str(env_dir)
        self.proc = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "ela.api:app", "--port", str(self.port), *extra_args],
            env=env,
            cwd=cwd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        self.url = f"http://127.0.0.1:{self.port}"
        deadline = time.monotonic() + 30
        while True:
            try:
                urllib.request.urlopen(self.url + "/api/definitions", timeout=1).close()
                return
            except OSError:
                if self.proc.poll() is not None or time.monotonic() > deadline:
                    self.stop()
                    raise RuntimeError("server did not start") from None
                time.sleep(0.1)

    def stop(self):
        if self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                self.proc.wait()


@pytest.fixture
def start_server(defs_dir):
    """H-SERVER: `start_server()` starts a server on H-DEFS and returns it, all stopped at teardown.

    `start_server(env_dir=other)` points it at another folder, `start_server(env_dir=None)` leaves
    the variable unset, and `cwd` sets the working directory.
    """
    started = []

    def start(env_dir=defs_dir, cwd=None, extra_args=()):
        server = Server(env_dir, cwd, extra_args)
        started.append(server)
        return server

    yield start
    for server in started:
        server.stop()


# --- Browser harness (H-PAGE) -------------------------------------------------------------------

# Wraps fetch so that each analyse request is logged in the page, at the moment it is made. A click
# handler has finished by the time Playwright's click returns, so a count read afterwards is exact.
LOG_SCRIPT = """
window.__analyse = [];
const realFetch = window.fetch;
window.fetch = function (input, init) {
  const url = typeof input === "string" ? input : input.url;
  if (init && init.method === "POST" && url.endsWith("/analyse")) {
    window.__analyse.push({url, states: JSON.parse(init.body).states});
  }
  return realFetch.apply(this, arguments);
};
"""

VIEWPORT = {"width": 1366, "height": 768}


def rgb_of(css):
    """(r, g, b) from a computed `rgb(...)` or `rgba(...)` colour."""
    return tuple(float(n) for n in re.findall(r"[\d.]+", css)[:3])


def hue_sat(rgb):
    """Hue in degrees and HSL saturation in percent of an (r, g, b) colour."""
    r, g, b = (v / 255 for v in rgb)
    hi, lo = max(r, g, b), min(r, g, b)
    delta = hi - lo
    if delta == 0:
        return 0.0, 0.0
    light = (hi + lo) / 2
    sat = delta / (1 - abs(2 * light - 1))
    if hi == r:
        hue = ((g - b) / delta) % 6
    elif hi == g:
        hue = (b - r) / delta + 2
    else:
        hue = (r - g) / delta + 4
    return hue * 60, sat * 100


def contrast(a, b):
    """WCAG contrast ratio of two (r, g, b) colours."""

    def luminance(rgb):
        lin = [v / 255 / 12.92 if v / 255 <= 0.03928 else ((v / 255 + 0.055) / 1.055) ** 2.4 for v in rgb]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


class HPage:
    """A Chromium page at 1366 x 768 open on a server over H-DEFS, with an analyse request log."""

    def __init__(self, page, server, defs):
        self.page = page
        self.server = server
        self.defs = defs
        self.errors = []
        page.on("pageerror", lambda e: self.errors.append(str(e)))
        page.add_init_script(LOG_SCRIPT)
        self.goto()

    # --- Navigation ---

    def _retry_navigation(self, navigate):
        """Retry a load that fails on a local socket shortage.

        Windows reports net::ERR_NO_BUFFER_SPACE when it runs short of socket buffers under load.
        That is the test machine's limit, not page behaviour, so only this error is retried.
        """
        from playwright.sync_api import Error as PlaywrightError

        for attempt in range(5):
            try:
                navigate()
                return
            except PlaywrightError as error:
                if "ERR_NO_BUFFER_SPACE" not in str(error) or attempt == 4:
                    raise
                time.sleep(0.5 * (attempt + 1))

    def goto(self):
        self._retry_navigation(lambda: self.page.goto(self.server.url + "/"))
        self.page.locator("#definition-select option").first.wait_for(state="attached")

    def reload(self):
        self._retry_navigation(self.page.reload)
        self.page.locator("#definition-select option").first.wait_for(state="attached")

    def open(self, def_id):
        """Choose a definition and wait for its first verdict."""
        from playwright.sync_api import expect

        self.page.select_option("#definition-select", def_id)
        expect(self.page.locator("#status-verdict")).not_to_be_empty()

    def options(self, selector="#definition-select"):
        return self.page.locator(f"{selector} option").evaluate_all("els => els.map(e => e.value)")

    # --- Log and barrier ---

    @property
    def log(self):
        return self.page.evaluate("window.__analyse")

    def settle(self):
        """Wait for two animation frames, so that anything a handler started has been issued."""
        self.page.evaluate("new Promise(r => requestAnimationFrame(() => requestAnimationFrame(r)))")

    # --- Reading the drawing ---

    def group(self, id_):
        return self.page.locator(f'#schematic [data-id="{id_}"]')

    def label(self, id_):
        return self.page.locator(f'#schematic [data-label="{id_}"]')

    def states(self):
        """data-state of every drawn element, by id."""
        return self.page.evaluate(
            "Object.fromEntries([...document.querySelectorAll('#schematic [data-id]')]"
            ".map(g => [g.dataset.id, g.dataset.state]))"
        )

    def labels(self):
        return self.page.evaluate(
            "Object.fromEntries([...document.querySelectorAll('#schematic [data-label]')]"
            ".map(t => [t.dataset.label, t.textContent]))"
        )

    def view(self):
        """(tx, ty, k) of the view transform."""
        text = self.page.locator("#viewport").get_attribute("transform")
        tx, ty, k = (float(n) for n in re.findall(r"-?\d+(?:\.\d+)?(?:e-?\d+)?", text))
        return tx, ty, k

    def rect(self, id_):
        """On-screen box of an element: (x, y, width, height)."""
        box = self.group(id_).evaluate(
            "g => { const b = g.getBoundingClientRect(); return [b.x, b.y, b.width, b.height]; }"
        )
        return tuple(box)

    def center(self, id_):
        x, y, w, h = self.rect(id_)
        return x + w / 2, y + h / 2

    def svg_box(self):
        return self.page.locator("#schematic").bounding_box()

    def in_layout_units(self, id_):
        """An element's on-screen box with the view transform undone: (x, y, width, height)."""
        box = self.svg_box()
        tx, ty, k = self.view()
        x, y, w, h = self.rect(id_)
        return (x - box["x"] - tx) / k, (y - box["y"] - ty) / k, w / k, h / k

    def colour(self, id_):
        return rgb_of(self.group(id_).evaluate("g => getComputedStyle(g).color"))

    def background(self):
        return rgb_of(
            self.page.evaluate("getComputedStyle(document.querySelector('.drawing')).backgroundColor")
        )

    # --- Acting ---

    def empty_point(self, right=False):
        """A point at the bottom of the drawing area where no element lies."""
        box = self.svg_box()
        x = box["x"] + (box["width"] - 30 if right else 30)
        y = box["y"] + box["height"] - 30
        free = self.page.evaluate(
            "([x, y]) => document.elementFromPoint(x, y) === document.getElementById('schematic')",
            [x, y],
        )
        assert free, "expected an empty spot on the drawing"
        return x, y

    def drag(self, start, end, steps=8):
        self.page.mouse.move(*start)
        self.page.mouse.down()
        self.page.mouse.move(*end, steps=steps)
        self.page.mouse.up()
        self.settle()


@pytest.fixture
def h_page(start_server, defs_dir, browser):
    """H-PAGE: `h_page()` opens a page on the test's H-SERVER and returns an `HPage`. A test adds the
    fixtures it names to H-DEFS first, and `h_page(has_touch=True)` gives a touch context. All pages
    are closed at teardown, and an error raised in the browser fails the test.
    """
    made = []
    servers = []

    def make(has_touch=False):
        if not servers:
            servers.append(start_server())
        context = browser.new_context(viewport=VIEWPORT, has_touch=has_touch, accept_downloads=True)
        context.set_default_timeout(10_000)
        harness = HPage(context.new_page(), servers[0], defs_dir)
        made.append((context, harness))
        return harness

    yield make
    for context, _ in made:
        context.close()
    for _, harness in made:
        assert harness.errors == [], harness.errors


@pytest.fixture(scope="session")
def e2e_run():
    """One subprocess run of `pytest tests -m "e2e and not meta"`, shared by the cases that need it."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-m", "e2e and not meta", "-q", "-p", "no:cacheprovider"],
        cwd=REPO,
        capture_output=True,
        text=True,
        check=False,
    )
