"""Static electrical load analysis (docs/spec.md §3, as ruled in docs/decisions.md).

`analyse` works in the order of the method. It resolves states, builds islands, energises AC buses
then TRUs then DC buses, totals demand from the DC islands up through the TRUs to the AC islands,
finds contactor flow on a spanning tree of each island, and checks capacities. TRUs pass power one
way, so the AC to DC structure is a DAG and needs no iteration.

Every per-band figure is a dict keyed by band, and is None where no value applies.
"""

from collections import deque
from dataclasses import asdict, dataclass, field

from ela.model import BAND_NAMES, Definition

TOLERANCE_W = 1e-6  # DD-023
TOLERANCE_PCT = 1e-6  # DD-023
LIVE_STATES = ("operative", "available")
# A tiny divisor can overflow a ratio even under DD-028's cap. This keeps every figure finite, with
# room for the sums and the margin applied to it.
FIGURE_LIMIT = 1e280


def _no_figures():
    return dict.fromkeys(BAND_NAMES)


@dataclass
class ElementRecord:
    state: str | None = None
    energised: bool = False
    demand: dict = field(default_factory=_no_figures)
    with_margin: dict = field(default_factory=_no_figures)
    capacity: dict = field(default_factory=_no_figures)
    margin_w: dict = field(default_factory=_no_figures)
    margin_pct: dict = field(default_factory=_no_figures)


@dataclass
class SourceRecord(ElementRecord):
    load_pct: dict = field(default_factory=_no_figures)


@dataclass
class BusRecord(ElementRecord):
    own: dict = field(default_factory=_no_figures)
    voltage: dict = field(default_factory=_no_figures)
    current: dict = field(default_factory=_no_figures)
    fed_by: list = field(default_factory=list)


@dataclass
class TruRecord(ElementRecord):
    load_pct: dict = field(default_factory=_no_figures)
    input: dict = field(default_factory=_no_figures)
    output: dict = field(default_factory=_no_figures)


@dataclass
class ContactorRecord(ElementRecord):
    pass


@dataclass
class Overload:
    element: str
    band: str
    demand_with_margin: float
    capacity: float


@dataclass
class UnpoweredLoad:
    id: str
    name: str
    bus: str


@dataclass
class AnalysisWarning:
    code: str
    element: str
    message: str


@dataclass
class Worst:
    element: str | None = None
    band: str | None = None
    margin_pct: float | None = None


@dataclass
class Island:
    buses: list[str]
    sources: list[str]


@dataclass
class AnalysisResult:
    verdict: str
    overloads: list[Overload]
    config_errors: list[str]
    unpowered: list[UnpoweredLoad]
    warnings: list[AnalysisWarning]
    worst: Worst
    checked: list[str]
    islands: list[Island]
    el: dict[str, ElementRecord]

    def to_dict(self) -> dict:
        """The whole result as plain JSON-ready data."""
        return asdict(self)


@dataclass
class _Island:
    """Buses and live sources joined by closed contactors, with the working figures."""

    buses: list[str]
    sources: list[str]
    feeding_trus: list[str] = field(default_factory=list)
    paralleled: bool = False

    @property
    def energised(self):
        return bool(self.sources or self.feeding_trus)


def _sum(figures):
    return {band: sum(f[band] for f in figures) for band in BAND_NAMES}


def _zero():
    return dict.fromkeys(BAND_NAMES, 0.0)


def _ratio(top, bottom):
    """`top / bottom`, held to FIGURE_LIMIT when a tiny divisor would overflow it."""
    return max(-FIGURE_LIMIT, min(FIGURE_LIMIT, top / bottom))


class _Analysis:
    def __init__(self, defn: Definition, states: dict):
        self.defn = defn
        self.sources = {s.id: s for s in defn.sources}
        self.buses = {b.id: b for b in defn.buses}
        self.trus = {t.id: t for t in defn.trus}
        self.contactors = {c.id: c for c in defn.contactors}
        self.state = self._resolve_states(states)

        self.live = {s for s in self.sources if self.state[s] in LIVE_STATES}
        self.tru_in, self.tru_out = self._tru_contactors()
        self.adjacent = self._adjacency()
        self.islands = self._build_islands()
        self.island_of = {n: i for i in self.islands for n in i.buses + i.sources}

        self.bus_live = {}
        self.tru_live = {}
        self._energise()

        self.own = self._own_loads()
        self.tru_output = {t: _zero() for t in self.trus}
        self.tru_input = {t: _zero() for t in self.trus}
        self.source_demand = {s: _zero() for s in self.live}
        self.leaving = {b: _zero() for b in self.buses}
        self.flow = {}
        self.loop_demand = {}  # rated element on a closed loop to its island's total (DD-026)
        self.warnings = []
        self.config_errors = []
        self._solve_islands()

    # --- States and topology ---

    def _resolve_states(self, states):
        resolved = {}
        for items in (self.sources, self.trus, self.contactors):
            resolved.update({i: e.default_state for i, e in items.items()})
        resolved.update({b.id: "on" for b in self.defn.buses if b.crew_switch})
        resolved.update({k: v for k, v in states.items() if k in resolved})
        return resolved

    def _closed(self, contactor_id):
        return self.state[contactor_id] == "closed"

    def _tru_contactors(self):
        """Each TRU's input and output contactor. The bus joined sets the role, not `from`/`to`."""
        inputs, outputs = {}, {}
        for c in self.contactors.values():
            if c.kind != "tru":
                continue
            tru_id = c.to if c.to in self.trus else c.from_
            bus_id = c.from_ if tru_id == c.to else c.to
            (inputs if bus_id == self.trus[tru_id].input_bus else outputs)[tru_id] = c.id
        return inputs, outputs

    def _adjacency(self):
        """Neighbours of each bus and live source across closed non-TRU contactors, sorted."""
        adjacent = {n: [] for n in [*self.buses, *self.live]}
        for c in self.contactors.values():
            joined = c.from_ in adjacent and c.to in adjacent
            if c.kind != "tru" and self._closed(c.id) and joined:
                adjacent[c.from_].append((c.to, c.id))
                adjacent[c.to].append((c.from_, c.id))
        return {n: sorted(neighbours) for n, neighbours in adjacent.items()}

    def _build_islands(self):
        islands, seen = [], set()
        for start in sorted(self.adjacent):
            if start in seen:
                continue
            nodes, pending = {start}, [start]
            while pending:
                for neighbour, _ in self.adjacent[pending.pop()]:
                    if neighbour not in nodes:
                        nodes.add(neighbour)
                        pending.append(neighbour)
            seen |= nodes
            islands.append(
                _Island(
                    buses=sorted(n for n in nodes if n in self.buses),
                    sources=sorted(n for n in nodes if n in self.live),
                )
            )
        return islands

    # --- Energisation ---

    def _energise(self):
        """AC buses from sources, then TRUs, then DC buses. Nothing passes from DC to AC."""
        for tru_id, tru in self.trus.items():
            input_id = self.tru_in[tru_id]
            self.tru_live[tru_id] = (
                self.state[tru_id] == "operative"
                and self._closed(input_id)
                and bool(self.island_of[tru.input_bus].sources)
            )
            if self.tru_live[tru_id] and self._closed(self.tru_out[tru_id]):
                self.island_of[tru.output_bus].feeding_trus.append(tru_id)
        for island in self.islands:
            island.feeding_trus.sort()
            self.bus_live.update(dict.fromkeys(island.buses, island.energised))

    # --- Demand and flow ---

    def _own_loads(self):
        own = {b: _zero() for b in self.buses}
        for load in self.defn.loads:
            if self.bus_live[load.bus] and self.state.get(load.bus) != "off":
                for band in BAND_NAMES:
                    own[load.bus][band] += getattr(load.power, band)
        return own

    def _is_ac(self, island):
        return any(self.buses[b].type == "AC" for b in island.buses)

    def _solve_islands(self):
        """DC islands first, so that each TRU's input power is known on the AC side."""
        for island in sorted(self.islands, key=self._is_ac):
            if not island.energised:
                continue
            if self._is_ac(island) and len(island.sources) > 1:
                island.paralleled = True
                self.config_errors.append(
                    f"AC sources paralleled: {', '.join(island.sources)} "
                    f"on {', '.join(island.buses)}"
                )
                self._warn_left_out(island)
                continue
            self._solve_flow(island, *self._share_demand(island))

    def _node_demand(self, bus):
        """Power a bus itself draws: own loads plus the input power of TRUs on it."""
        drawn = [self.tru_input[t] for t, tru in self.trus.items() if tru.input_bus == bus]
        return _sum([self.own[bus], *drawn])

    def _feeders(self, island):
        """The sources sharing an island's demand, batteries only when nothing else feeds it."""
        others = [s for s in island.sources if self.sources[s].kind != "battery"]
        others += island.feeding_trus
        return others or island.sources

    def _continuous_capacity(self, feeder):
        element = self.sources.get(feeder) or self.trus[feeder]
        return element.capacity.continuous

    def _share_demand(self, island):
        """Split an island's demand over its feeders (DD-006).

        Returns each node's injection and the island's total demand.
        """
        total = _sum([self._node_demand(b) for b in island.buses] or [_zero()])
        feeders = self._feeders(island)
        capacities = {f: self._continuous_capacity(f) for f in feeders}
        whole = sum(capacities.values())
        injection = {}
        for feeder in feeders:
            share = capacities[feeder] / whole if whole > 0 else 1 / len(feeders)
            injection[feeder] = {band: total[band] * share for band in BAND_NAMES}
            if feeder in self.trus:
                self.tru_output[feeder] = injection[feeder]
                efficiency = self.trus[feeder].efficiency
                self.tru_input[feeder] = {
                    b: _ratio(v, efficiency) for b, v in injection[feeder].items()
                }
            else:
                self.source_demand[feeder] = injection[feeder]
        return injection, total

    def _island_graph(self, island):
        """Each node's neighbours on an island, with its feeding TRUs as leaves."""
        adjacent = {n: list(self.adjacent[n]) for n in island.buses + island.sources}
        for tru_id in island.feeding_trus:
            bus, contactor = self.trus[tru_id].output_bus, self.tru_out[tru_id]
            adjacent[tru_id] = [(bus, contactor)]
            adjacent[bus] = sorted([*adjacent[bus], (tru_id, contactor)])
        return adjacent

    def _spanning_tree(self, island, adjacent):
        """Breadth-first tree from the lowest id source (DD-004), and the contactors left out."""
        root = min(island.sources + island.feeding_trus)
        edges, used, visited, queue = [], set(), {root}, deque([root])
        while queue:
            node = queue.popleft()
            for neighbour, contactor in adjacent[node]:
                if neighbour not in visited:
                    visited.add(neighbour)
                    used.add(contactor)
                    edges.append((node, neighbour, contactor))
                    queue.append(neighbour)
        spare = {c for n in adjacent for _, c in adjacent[n]} - used
        return edges, spare

    def _warn_mesh(self, element, text):
        self.warnings.append(AnalysisWarning("meshed_island", element, f"closed loop: {text}"))

    def _warn_left_out(self, island):
        """Names the contactors left out of a paralleled island, where no flow is attributed."""
        _, spare = self._spanning_tree(island, self._island_graph(island))
        for contactor in sorted(spare):
            self._warn_mesh(contactor, f"contactor '{contactor}' is left out of the spanning tree")

    def _still_joined(self, adjacent, contactor):
        """True when a contactor's ends stay connected without it."""
        start, goal = self.contactors[contactor].from_, self.contactors[contactor].to
        seen, pending = {start}, [start]
        while pending:
            for neighbour, via in adjacent[pending.pop()]:
                if via != contactor and neighbour not in seen:
                    seen.add(neighbour)
                    pending.append(neighbour)
        return goal in seen

    def _rated_on_loops(self, adjacent):
        """The rated contactors, and the rated buses they or unrated contactors join (DD-026)."""
        contactors = {c for n in adjacent for _, c in adjacent[n]}
        looped = {c for c in contactors if self._still_joined(adjacent, c)}
        ends = {e for c in looped for e in (self.contactors[c].from_, self.contactors[c].to)}
        rated = {c for c in looped if self.contactors[c].capacity is not None}
        return rated | {b for b in ends & self.buses.keys() if self.buses[b].capacity is not None}

    def _solve_flow(self, island, injection, total):
        """Node balance on the tree: the net demand on the side of each edge away from the root."""
        adjacent = self._island_graph(island)
        edges, spare = self._spanning_tree(island, adjacent)
        rated = self._rated_on_loops(adjacent) if spare else set()
        for element in sorted(rated):
            self.loop_demand[element] = total
            left_out = "is left out of the flow solution and " if element in spare else ""
            self._warn_mesh(element, f"'{element}' {left_out}is checked against the island total")
        for contactor in sorted(spare):
            self.flow[contactor] = _zero()
            if contactor not in rated:
                self._warn_mesh(
                    contactor,
                    f"contactor '{contactor}' is left out of the flow solution and carries 0 W",
                )
        net = {}
        for node in {node for edge in edges for node in edge[:2]}:
            demand = self._node_demand(node) if node in self.buses else _zero()
            supply = injection.get(node, _zero())
            net[node] = {b: demand[b] - supply[b] for b in BAND_NAMES}
        for parent, child, contactor in reversed(edges):
            self.flow[contactor] = {b: abs(v) for b, v in net[child].items()}
            for band, value in net[child].items():
                net[parent][band] += value
                # A positive net flows from parent to child, a negative one the other way.
                sender = parent if value > 0 else child
                if sender in self.buses:
                    self.leaving[sender][band] += abs(value)

    # --- Element records ---

    def _margin(self, element):
        own = element.safety_margin
        return self.defn.settings.safety_margin if own is None else own

    def _fill(self, record, element, demand):
        """Set the figures every element shares, from its demand per band (or None)."""
        capacity = element.capacity
        margin = self._margin(element)
        for band in BAND_NAMES:
            limit = None if capacity is None else getattr(capacity, band)
            record.capacity[band] = limit
            value = demand[band] if demand is not None else None
            record.demand[band] = value
            if value is None:
                continue
            with_margin = value * (1 + margin)
            record.with_margin[band] = with_margin
            if limit is not None:
                record.margin_w[band], record.margin_pct[band] = _remaining(
                    limit, value, with_margin
                )

    def _contactor_end_live(self, node):
        if node in self.buses:
            return self.bus_live[node]
        return self.tru_live[node] if node in self.trus else node in self.live

    def _contactor_demand(self, contactor):
        """The power crossing a contactor (DD-013), None where DD-005 removes it."""
        ends = (contactor.from_, contactor.to)
        if any(end in self.island_of and self.island_of[end].paralleled for end in ends):
            return None
        for tru_id, input_id in self.tru_in.items():
            if input_id == contactor.id:
                return self.tru_input[tru_id]
        return self.loop_demand.get(contactor.id) or self.flow.get(contactor.id, _zero())

    def records(self) -> dict[str, ElementRecord]:
        records = {}
        for id_, source in self.sources.items():
            live = id_ in self.live
            paralleled = live and self.island_of[id_].paralleled
            record = SourceRecord(state=self.state[id_], energised=live)
            self._fill(record, source, self.source_demand[id_] if live and not paralleled else None)
            record.load_pct = _load_pct(record)
            records[id_] = record
        for id_, bus in self.buses.items():
            live = self.bus_live[id_]
            demand = None
            if live:
                demand = self.loop_demand.get(id_) or _sum(
                    [self._node_demand(id_), self.leaving[id_]]
                )
            record = BusRecord(state=self.state.get(id_), energised=live, own=self.own[id_])
            self._fill(record, bus, demand)
            if live:
                divisor = bus.voltage * (bus.phases if bus.type == "AC" else 1)
                record.voltage = dict.fromkeys(BAND_NAMES, bus.voltage)
                record.current = {b: _ratio(v, divisor) for b, v in demand.items()}
                record.fed_by = sorted(self._feeders(self.island_of[id_]))
            records[id_] = record
        for id_, tru in self.trus.items():
            live = self.tru_live[id_]
            record = TruRecord(state=self.state[id_], energised=live)
            self._fill(record, tru, self.tru_output[id_] if live else None)
            if live:
                record.input = self.tru_input[id_]
                record.output = self.tru_output[id_]
            record.load_pct = _load_pct(record)
            records[id_] = record
        for id_, contactor in self.contactors.items():
            ends = (contactor.from_, contactor.to)
            live = self._closed(id_) and any(self._contactor_end_live(e) for e in ends)
            record = ContactorRecord(state=self.state[id_], energised=live)
            self._fill(record, contactor, self._contactor_demand(contactor) if live else None)
            records[id_] = record
        return records

    def unpowered(self) -> list[UnpoweredLoad]:
        return sorted(
            (
                UnpoweredLoad(load.id, load.name, load.bus)
                for load in self.defn.loads
                if load.essential
                and (not self.bus_live[load.bus] or self.state.get(load.bus) == "off")
            ),
            key=lambda u: u.id,
        )


def _remaining(capacity, demand, with_margin):
    """Remaining margin in W and % (DD-011). Within DD-023 tolerance it is exactly at the limit."""
    remaining = capacity - with_margin
    if abs(remaining) <= TOLERANCE_W:
        remaining = 0.0
    if capacity == 0:
        return remaining, -100.0 if demand > 0 else 0.0
    return remaining, _ratio(remaining, capacity) * 100


def _load_pct(record):
    return {
        band: None
        if record.demand[band] is None or not record.capacity[band]
        else _ratio(record.demand[band], record.capacity[band]) * 100
        for band in BAND_NAMES
    }


def _check(records):
    """The checked ids, overload entries and worst element across all records."""
    checked, overloads, margins = [], [], []
    for id_ in sorted(records):
        record = records[id_]
        if not record.energised or record.margin_pct[BAND_NAMES[0]] is None:
            continue
        checked.append(id_)
        for band in BAND_NAMES:
            margins.append((record.margin_pct[band], id_, band))
            if record.with_margin[band] > record.capacity[band] + TOLERANCE_W:
                overloads.append(
                    Overload(id_, band, record.with_margin[band], record.capacity[band])
                )
    return checked, overloads, _worst(margins)


def _worst(margins):
    """The smallest margin. Ties within tolerance go to the lowest id, then the band order."""
    if not margins:
        return Worst()
    smallest = min(m[0] for m in margins)
    tied = [m for m in margins if m[0] - smallest <= TOLERANCE_PCT]
    pct, element, band = min(tied, key=lambda m: (m[1], BAND_NAMES.index(m[2])))
    return Worst(element, band, pct)


def analyse(defn: Definition, states: dict) -> AnalysisResult:
    """Analyse one configuration: a validated definition and the states that differ from default."""
    analysis = _Analysis(defn, states)
    records = analysis.records()
    checked, overloads, worst = _check(records)
    unpowered = analysis.unpowered()
    config_errors = sorted(analysis.config_errors)
    verdict = "FAIL" if overloads or config_errors or unpowered else "PASS"
    return AnalysisResult(
        verdict=verdict,
        overloads=overloads,
        config_errors=config_errors,
        unpowered=unpowered,
        warnings=sorted(analysis.warnings, key=lambda w: w.element),
        worst=worst,
        checked=checked,
        islands=sorted(
            (Island(i.buses, i.sources) for i in analysis.islands),
            key=lambda i: (i.buses, i.sources),
        ),
        el=records,
    )
