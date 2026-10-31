"""Hand calculation of definitions/generic_twin.json, written like a spreadsheet.

Run it to print the working and regenerate tests/data/generic_twin_expected.json. With --check it
only compares that file with a fresh calculation.

This script stands apart from the tool: it does not import `ela`, and it does no graph search. It
takes loads, capacities and efficiencies from the definition file. How power flows in each scenario
is read off the schematic by the engineer and written in PLAN below, so a wrong contactor in a
scenario shows up as a difference from the engine.

Method (docs/spec.md Â§3, as ruled in docs/decisions.md), per band:

  1. Own load of a bus = sum of its loads. A dead bus, or one with its crew switch off, is 0.
  2. DC island total = sum of own loads. Feeders share it by continuous capacity (DD-006).
     TRU input = TRU output / efficiency.
  3. AC island total = sum of own loads + TRU inputs. This is the source demand.
     A paralleled AC island gets no source figure (DD-005).
  4. Tie flow = |net demand on the far side of the tie|, the cut-set rule of DD-013.
  5. Bus demand = own load + TRU inputs on it + everything it passes on (DD-002).
  6. Margin % = (capacity - demand x (1 + margin)) / capacity x 100 (DD-011).
     The worst element is the smallest %, then the lowest id, then the band order.
"""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DEFINITION = ROOT / "definitions" / "generic_twin.json"
EXPECTED = ROOT / "tests" / "data" / "generic_twin_expected.json"

BANDS = ("transient", "short_term", "continuous")
ZERO = (0.0, 0.0, 0.0)
SAME_MARGIN_PCT = 1e-6  # DD-023


def add(*rows):
    return tuple(sum(values) for values in zip(*rows, strict=True)) if rows else ZERO


def scale(row, factor):
    return tuple(value * factor for value in row)


def bands(row):
    """A band row as JSON. None stays None: the element carries no figure."""
    if row is None:
        return None
    return {band: round(value, 6) for band, value in zip(BANDS, row, strict=True)}


def island(feeders, buses, cuts=(), paralleled=False):
    """One electrical island, read off the schematic.

    A cut is (tie, near bus, far buses). The tie lands on the first far bus, and the far buses are
    everything on that side of the tie.
    """
    return {"feeders": feeders, "buses": buses, "cuts": cuts, "paralleled": paralleled}


# Islands that recur. DTCEB always joins DC ESS and DC BAT.
DC1_ON_TRU1 = island(["TRU1"], ["DC1"])
DC2_ON_TRU2 = island(["TRU2"], ["DC2"])
ESS_ON_TRU3 = island(["TRU3"], ["DCESS", "DCBAT"], [("DTCEB", "DCESS", ["DCBAT"])])
ESS_ON_BAT = island(["BAT"], ["DCBAT", "DCESS"], [("DTCEB", "DCBAT", ["DCESS"])])
AC1_AND_ESS = [("BTC1E", "AC1", ["ACESS"])]

PLAN = {
    "S01": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S02": [DC2_ON_TRU2, ESS_ON_BAT, island(["GEN2"], ["AC2"])],
    "S03": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["APUGEN"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S04": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["APUGEN"], ["AC2"]),
    ],
    "S05": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["APUGEN"], ["AC1", "AC2", "ACESS"], AC1_AND_ESS),
    ],
    "S06": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(
            ["GEN2"],
            ["AC2", "AC1", "ACESS"],
            [("BTC12", "AC2", ["AC1"]), ("BTC2E", "AC2", ["ACESS"])],
        ),
    ],
    "S07": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["GEN1"], ["AC1", "AC2", "ACESS"], [("BTC12", "AC1", ["AC2"]), *AC1_AND_ESS]),
    ],
    "S08": [
        island(["TRU2"], ["DC2", "DC1"], [("DTC12", "DC2", ["DC1"])]),
        ESS_ON_TRU3,
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S09": [
        island(
            ["TRU1", "TRU3"],
            ["DC1", "DC2", "DCESS", "DCBAT"],
            [
                ("DTC12", "DC1", ["DC2"]),
                ("DTC1E", "DCESS", ["DC1", "DC2"]),
                ("DTCEB", "DCESS", ["DCBAT"]),
            ],
        ),
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S10": [
        island(
            ["TRU1"],
            ["DC1", "DCESS", "DCBAT"],
            [("DTC1E", "DC1", ["DCESS", "DCBAT"]), ("DTCEB", "DCESS", ["DCBAT"])],
        ),
        DC2_ON_TRU2,
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S11": [ESS_ON_TRU3, island(["RAT_AC"], ["ACESS"])],
    "S12": [ESS_ON_BAT],
    "S13": [
        island(
            ["TRU1"],
            ["DC1", "DC2", "DCESS", "DCBAT"],
            [
                ("DTC12", "DC1", ["DC2"]),
                ("DTC1E", "DC1", ["DCESS", "DCBAT"]),
                ("DTCEB", "DCESS", ["DCBAT"]),
            ],
        ),
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S14": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["GEN1"], ["AC1", "ACESS"], AC1_AND_ESS),
        island(["GEN2"], ["AC2"]),
    ],
    "S15": [
        DC1_ON_TRU1,
        DC2_ON_TRU2,
        ESS_ON_TRU3,
        island(["GEN1", "GEN2"], ["AC1", "AC2", "ACESS"], paralleled=True),
    ],
}


class Scenario:
    """The working for one scenario. Each step below is one numbered step of the method."""

    def __init__(self, doc, scenario):
        self.doc = doc
        self.scenario = scenario
        self.states = scenario["states"]
        self.margin = doc["settings"]["safety_margin"]
        self.buses = {b["id"]: b for b in doc["buses"]}
        self.trus = {t["id"]: t for t in doc["trus"]}
        self.sources = {s["id"]: s for s in doc["sources"]}
        self.contactors = {c["id"]: c for c in doc["contactors"]}
        self.islands = PLAN[scenario["id"]]
        self.live_buses = {bus for i in self.islands for bus in i["buses"]}

        self.tru_in = {}
        self.tru_out = {}
        self.source_demand = {}
        self.tie_flow = {}
        self.passed_on = dict.fromkeys(self.buses, ZERO)

        self.own = {bus: self.own_load(bus) for bus in self.buses}  # step 1
        dc = [i for i in self.islands if self.buses[i["buses"][0]]["type"] == "DC"]
        ac = [i for i in self.islands if self.buses[i["buses"][0]]["type"] == "AC"]
        for each in dc + ac:  # DC first, so that each TRU input is known on the AC side
            self.share(each)  # steps 2 and 3
            self.flows(each)  # step 4
        self.demand = {bus: self.bus_demand(bus) for bus in self.live_buses}  # step 5

    def state(self, element):
        return self.states.get(element["id"], element["default_state"])

    def is_live(self, source):
        return self.state(source) in ("operative", "available")

    def own_load(self, bus):
        if bus not in self.live_buses or self.states.get(bus) == "off":
            return ZERO
        powers = [load["power"] for load in self.doc["loads"] if load["bus"] == bus]
        return add(*[tuple(p[band] for band in BANDS) for p in powers])

    def tru_inputs_on(self, bus):
        on_bus = [self.tru_in[t] for t in self.tru_in if self.trus[t]["input_bus"] == bus]
        return add(*on_bus) if on_bus else ZERO

    def net_load(self, bus):
        return add(self.own[bus], self.tru_inputs_on(bus))

    def injected_on(self, bus):
        """Output of any TRU landing on this bus. Sources sit on the near side of every cut."""
        fed = [self.tru_out[t] for t in self.tru_out if self.trus[t]["output_bus"] == bus]
        return add(*fed) if fed else ZERO

    def share(self, each):
        total = add(*[self.net_load(bus) for bus in each["buses"]])
        if each["paralleled"]:
            return
        feeders = {f: (self.trus.get(f) or self.sources[f]) for f in each["feeders"]}
        whole = sum(f["capacity"]["continuous"] for f in feeders.values())
        for feeder_id, feeder in feeders.items():
            part = scale(total, feeder["capacity"]["continuous"] / whole)
            if feeder_id in self.trus:
                self.tru_out[feeder_id] = part
                self.tru_in[feeder_id] = scale(part, 1 / feeder["efficiency"])
            else:
                self.source_demand[feeder_id] = part

    def flows(self, each):
        if each["paralleled"]:
            return
        for tie, near, far in each["cuts"]:
            net = add(
                *[self.net_load(b) for b in far], *[scale(self.injected_on(b), -1) for b in far]
            )
            self.tie_flow[tie] = tuple(abs(value) for value in net)
            into_far = tuple(value if value > 0 else 0.0 for value in net)
            out_of_far = tuple(-value if value < 0 else 0.0 for value in net)
            self.passed_on[near] = add(self.passed_on[near], into_far)
            self.passed_on[far[0]] = add(self.passed_on[far[0]], out_of_far)

    def bus_demand(self, bus):
        return add(self.net_load(bus), self.passed_on[bus])

    # --- Results ---

    def paralleled_sources(self):
        return [f for i in self.islands if i["paralleled"] for f in i["feeders"]]

    def source_row(self, source):
        """Demand on a source. None means not live or paralleled, 0 means live and idle."""
        if not self.is_live(source) or source["id"] in self.paralleled_sources():
            return None
        return self.source_demand.get(source["id"], ZERO)

    def tie_is_energised(self, tie):
        closed = self.state(tie) == "closed"
        return closed and bool({tie["from"], tie["to"]} & self.live_buses)

    def tie_row(self, tie):
        """Flow on a rated tie. None means dead, open, or on a paralleled island."""
        if not self.tie_is_energised(tie):
            return None
        paralleled = {b for i in self.islands if i["paralleled"] for b in i["buses"]}
        if tie["from"] in paralleled or tie["to"] in paralleled:
            return None
        return self.tie_flow[tie["id"]]  # a KeyError here means PLAN missed a closed tie

    def rated_rows(self):
        """(id, element, demand) of each element that takes a capacity check (Â§3.6)."""
        rows = [(i, s, self.source_row(s)) for i, s in self.sources.items()]
        rows += [(i, t, self.tru_out.get(i)) for i, t in self.trus.items()]
        rows += [(i, self.buses[i], self.demand[i]) for i in self.live_buses]
        for id_, contactor in self.contactors.items():
            if "capacity" in contactor:
                rows.append((id_, contactor, self.tie_row(contactor)))
        return [row for row in rows if row[2] is not None]

    def checks(self):
        """One row per checked element and band: demand with margin, capacity, margin %."""
        lines = []
        for id_, element, demand in sorted(self.rated_rows(), key=lambda row: row[0]):
            margin = element.get("safety_margin", self.margin)
            for index, band in enumerate(BANDS):
                capacity = element["capacity"][band]
                with_margin = demand[index] * (1 + margin)
                pct = (capacity - with_margin) / capacity * 100
                lines.append((id_, band, with_margin, capacity, pct))
        return lines

    def record(self):
        checks = self.checks()
        overloads = [line for line in checks if line[2] > line[3] + 1e-6]
        smallest = min(line[4] for line in checks)
        worst = next(line for line in checks if line[4] - smallest <= SAME_MARGIN_PCT)
        unpowered = [
            load["id"]
            for load in self.doc["loads"]
            if load.get("essential")
            and (load["bus"] not in self.live_buses or self.states.get(load["bus"]) == "off")
        ]
        result = "FAIL" if overloads or unpowered or self.paralleled_sources() else "PASS"
        return {
            "name": self.scenario["name"],
            "result": result,
            "worst_element": worst[0],
            "worst_band": worst[1],
            "smallest_margin_pct": round(worst[4], 6),
            "overloads": len(overloads),
            "configuration_errors": 1 if self.paralleled_sources() else 0,
            "unpowered_essential": len(unpowered),
            "overload_details": [
                {
                    "element": line[0],
                    "band": line[1],
                    "demand_with_margin": round(line[2], 6),
                    "capacity": line[3],
                }
                for line in overloads
            ],
            "unpowered_details": unpowered,
            "paralleled_sources": self.paralleled_sources(),
            "checked": sorted({line[0] for line in checks}),
            "sources": {
                id_: {"demand": bands(self.source_row(s)), "capacity": s["capacity"]}
                for id_, s in self.sources.items()
            },
            "trus": {
                id_: {
                    "output": bands(self.tru_out.get(id_)),
                    "input": bands(self.tru_in.get(id_)),
                    "capacity": t["capacity"],
                }
                for id_, t in self.trus.items()
            },
            "buses": {id_: self.bus_record(id_) for id_ in self.buses},
            "ties": {
                id_: {"demand": bands(self.tie_row(c)), "capacity": c["capacity"]}
                for id_, c in self.contactors.items()
                if "capacity" in c
            },
        }

    def bus_record(self, id_):
        bus = self.buses[id_]
        live = id_ in self.live_buses
        divisor = bus["voltage"] * (bus["phases"] if bus["type"] == "AC" else 1)  # Â§3.7
        return {
            "energised": live,
            "own": bands(self.own[id_]),
            "demand": bands(self.demand[id_]) if live else None,
            "current": bands(scale(self.demand[id_], 1 / divisor)) if live else None,
            "capacity": bus.get("capacity"),
        }

    def print_sheet(self):
        rec = self.record()
        print(f"\n{self.scenario['id']}  {self.scenario['name']}  ->  {rec['result']}")
        print(f"  {'':<10}{'transient':>12}{'short_term':>12}{'continuous':>12}")

        def row(label, values):
            print(f"  {label:<10}" + "".join(f"{v:>12.1f}" for v in values))

        for bus in self.buses:
            if bus in self.live_buses:
                row(f"{bus} own", self.own[bus])
        for tru in self.tru_out:
            row(f"{tru} out", self.tru_out[tru])
            row(f"{tru} in", self.tru_in[tru])
        for source, values in self.source_demand.items():
            row(source, values)
        for tie, values in self.tie_flow.items():
            row(tie, values)
        for bus in self.buses:
            if bus in self.live_buses:
                row(f"{bus} dem", self.demand[bus])
        print(
            f"  worst {rec['worst_element']} {rec['worst_band']} "
            f"{rec['smallest_margin_pct']:.2f} %, overloads {rec['overloads']}, "
            f"unpowered {rec['unpowered_essential']}, paralleled {rec['paralleled_sources']}"
        )


def calculate(doc):
    return {
        "source": "tools/hand_calc_sample.py, from definitions/generic_twin.json. Do not edit.",
        "scenarios": {s["id"]: Scenario(doc, s).record() for s in doc["scenarios"]},
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--check", action="store_true", help="compare only, write nothing")
    args = parser.parse_args()

    doc = json.loads(DEFINITION.read_text("utf-8"))
    expected = calculate(doc)
    if args.check:
        same = json.loads(EXPECTED.read_text("utf-8")) == expected
        print("expected file is current" if same else "expected file is stale")
        return 0 if same else 1
    for scenario in doc["scenarios"]:
        Scenario(doc, scenario).print_sheet()
    text = json.dumps(expected, indent=2) + "\n"
    EXPECTED.write_text(text, "utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
