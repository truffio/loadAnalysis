"""Schematic layout (docs/spec.md §6.2, §7.1): coordinates computed from a definition alone.

`layout(defn)` is a layered, Sugiyama-style drawing in five steps.

1. Rows. Every displayed element gets a fixed row, top to bottom as in §6.2. A link that spans
   several rows gets a dummy node in each row it passes, which reserves a lane through that row.
2. Order. Barycentre sweeps, then sifting, order each row from several starting orders. The source
   row is fixed, and a source contactor stays under its source.
3. Strands. Links are made straight wherever the order allows. A strand is a set of nodes sharing
   one `x`, and a bus bar has to reach every strand that lands on it. A link that would need a
   bar or an item to change places stays a dogleg, and it is the crossing the order could not avoid.
4. Position. `x` comes from difference constraints, solved by longest path from both sides and
   averaged. Spacing steps down through `SPACINGS` until the drawing fits `DRAW_WIDTH`.
5. Routing. Straight links are drawn first, then each dogleg takes the cheapest orthogonal path on
   a sparse grid, which never enters an item and pays for each bend and crossing. A connector
   shares a line only as a last resort, and then only with one that ends on the same node.

Everything is a function of the definition's contents. Ids sort naturally, so `AC2` < `AC10`.
"""

import heapq
import itertools
import re
from bisect import bisect_left, bisect_right, insort
from dataclasses import dataclass, field

from ela.model import Definition

DRAW_WIDTH = 1000
DRAW_HEIGHT = 560
MARGIN = 16  # around the drawing
LANE = 6  # the outermost routing lanes, inside MARGIN

SOURCE_SIZE = (32, 32)
CONTACTOR_SIZE = (20, 20)
TRU_SIZE = (36, 28)
SWITCH_SIZE = (20, 20)
BAR_HEIGHT = 14

BAR_END = 12  # a strand stays this far inside the ends of its bar
SWITCH_DROP = 2  # gap between a bar and its crew switch
GAP_MIN = 18  # vertical gap between rows
GAP_MAX = 44
TEXT_HEIGHT = 12  # one line of 10 px text
BUS_LABEL_WIDTH = 104  # "115 V  7.25 A  2.50 kW"
ICON_LABEL_WIDTH = 64  # "45.2 kW  50 %"
CLEARANCE = 3  # routing keeps this far from any item
TIE_ROOM = 16  # extra space between two level ties in one gap
TRACK = 6  # spacing of routing lanes in a gap between rows

BEND_COST = 40
CROSSING_COST = 80
OVERLAP_COST = 5000
ENGINE_SWAP_COST = 0.6  # against one crossing, when ordering rows

ROW_NAMES = (
    "source",
    "source_contactor",
    "ac_main",
    "ac_tie",
    "ac_other",
    "tru_in",
    "tru",
    "tru_out",
    "dc_main",
    "dc_tie_main",
    "dc_essential",
    "dc_tie_essential",
    "dc_other",
)
TIE_ROW_BELOW = {
    "ac_main": "ac_tie",
    "dc_main": "dc_tie_main",
    "dc_essential": "dc_tie_essential",
}

EAST, WEST, SOUTH, NORTH = range(4)
STEPS = {EAST: (1, 0), WEST: (-1, 0), SOUTH: (0, 1), NORTH: (0, -1)}


@dataclass(frozen=True)
class Spacing:
    """One step of horizontal density: text room beside an icon, gap between entries, bar width."""

    label: int
    gap: int
    bar: int


# Widest first. The last step has no text room and is the densest the icons allow.
SPACINGS = (
    *(Spacing(68 + 2 * t, 12 + t // 2, 64 + 5 * t) for t in range(22, -1, -1)),
    *(Spacing(6 * t, 12, 44 + 2 * t) for t in range(10, -1, -1)),
)


@dataclass
class Link:
    """One electrical link between two items in different rows. `top` is the upper one."""

    top: str
    bottom: str
    ends: tuple  # (from, to) for the connector
    chain: list = field(default_factory=list)  # top, one dummy per row passed, bottom


@dataclass
class LevelTie:
    """A bus tie drawn level between two bars of one row."""

    tie: str
    from_: str
    to: str


@dataclass
class Stepover:
    """A connector from a level tie to a bar that is not its neighbour in the row."""

    bar: str
    tie: str
    ends: tuple
    on_left: bool


@dataclass
class Box:
    x: int
    y: int
    w: int
    h: int

    @property
    def right(self):
        return self.x + self.w

    @property
    def bottom(self):
        return self.y + self.h

    @property
    def cx(self):
        return self.x + self.w // 2

    @property
    def cy(self):
        return self.y + self.h // 2

    def hits(self, other):
        return (
            self.x < other.right
            and other.x < self.right
            and self.y < other.bottom
            and other.y < self.bottom
        )

    def hits_segment(self, a, b):
        return self.hits(
            Box(min(a[0], b[0]), min(a[1], b[1]), abs(a[0] - b[0]) or 1, abs(a[1] - b[1]) or 1)
        )


def _natural(text):
    return [int(t) if t.isdigit() else t for t in re.split(r"(\d+)", text)]


def _source_rank(source):
    rank = {"engine_generator": 0, "apu_generator": 1, "emergency_generator": 2, "battery": 3}
    return (rank[source.kind], source.engine or 0, _natural(source.id))


class _Network:
    """Items, rows and links of a definition. Rows hold ids, and dummies start with a NUL."""

    def __init__(self, defn: Definition):
        self.defn = defn
        self.kind = {}
        self.size = {}
        self.place = {}  # item id to row name
        self.links = []
        self.level_ties = []
        self.declared = {}  # item id to its position in the definition
        self.single_feed = {}  # source id to its number of contactors
        self.orientation = {}
        self.crew_buses = [b.id for b in defn.buses if b.crew_switch]
        self._add_items()
        self._add_contactors()
        self._build_rows()

    def _add(self, id_, kind, size, row):
        self.kind[id_] = kind
        self.size[id_] = size
        self.place[id_] = row
        self.declared[id_] = len(self.declared)

    def _add_items(self):
        defn = self.defn
        for s in defn.sources:
            self._add(s.id, s.kind, SOURCE_SIZE, "source")
        for b in defn.buses:
            self._add(b.id, "bus", (0, BAR_HEIGHT), _bus_row(b))
        for t in defn.trus:
            self._add(t.id, "tru", TRU_SIZE, "tru")

    def _add_contactors(self):
        sources = {s.id for s in self.defn.sources}
        trus = {t.id: t for t in self.defn.trus}
        buses = {b.id for b in self.defn.buses}
        for c in self.defn.contactors:
            self.orientation[c.id] = "vertical"
            if c.from_ in buses and c.to in buses:
                row = self._add_tie(c)
            elif c.from_ in sources or c.to in sources:
                row = "source_contactor"
                source, bus = (c.from_, c.to) if c.from_ in sources else (c.to, c.from_)
                self.single_feed[source] = self.single_feed.get(source, 0) + 1
                self._link(source, c.id, (c.from_, c.id) if c.from_ == source else (c.id, c.to))
                self._link(c.id, bus, (c.from_, c.id) if c.from_ == bus else (c.id, c.to))
            else:
                row = self._tru_contactor_row(c, trus)
                self._link(c.from_, c.id, (c.from_, c.id))
                self._link(c.id, c.to, (c.id, c.to))
            self._add(c.id, "contactor", CONTACTOR_SIZE, row)

    @staticmethod
    def _tru_contactor_row(c, trus):
        """The bus joined sets the role, not `from`/`to`, as in `ela.engine`."""
        tru, bus = (trus[c.to], c.from_) if c.to in trus else (trus[c.from_], c.to)
        return "tru_in" if bus == tru.input_bus else "tru_out"

    def _add_tie(self, c):
        """Set up a bus tie. Returns its row name."""
        a_row, b_row = self.place[c.from_], self.place[c.to]
        if a_row == b_row:
            self.orientation[c.id] = "horizontal"
            self.level_ties.append(LevelTie(c.id, c.from_, c.to))
            return a_row
        upper = min(a_row, b_row, key=ROW_NAMES.index)
        self._link(c.from_, c.id, (c.from_, c.id))
        self._link(c.id, c.to, (c.id, c.to))
        return TIE_ROW_BELOW[upper]

    def _link(self, a, b, ends):
        self.links.append(Link(a, b, ends))

    def _build_rows(self):
        names = [n for n in ROW_NAMES if n in set(self.place.values())]
        self.row_names = names
        self.row_of = {i: names.index(n) for i, n in self.place.items()}
        for link in self.links:
            if self.row_of[link.top] > self.row_of[link.bottom]:
                link.top, link.bottom = link.bottom, link.top
        self.tie_ids = {t.tie for t in self.level_ties}
        self.rows = [[] for _ in names]
        for id_ in sorted(self.place, key=_natural):
            if id_ not in self.tie_ids:
                self.rows[self.row_of[id_]].append(id_)
        count = 0
        for link in sorted(self.links, key=lambda k: (_natural(k.top), _natural(k.bottom))):
            link.chain = [link.top]
            for r in range(self.row_of[link.top] + 1, self.row_of[link.bottom]):
                count += 1
                dummy = f"\0{count}"
                self.rows[r].append(dummy)
                self.row_of[dummy] = r
                link.chain.append(dummy)
            link.chain.append(link.bottom)
        self.segments = [[] for _ in names]  # by upper row
        for link in self.links:
            for u, v in zip(link.chain, link.chain[1:], strict=False):
                self.segments[self.row_of[u]].append((u, v))
        self.up = {n: [] for row in self.rows for n in row}
        self.down = {n: [] for row in self.rows for n in row}
        for segments in self.segments:
            for u, v in segments:
                self.down[u].append(v)
                self.up[v].append(u)
        self.source_order = [s.id for s in sorted(self.defn.sources, key=_source_rank)]
        if self.source_order:
            self.rows[0] = list(self.source_order)

    def is_bar(self, node):
        return self.kind.get(node) == "bus"

    def is_dummy(self, node):
        return node.startswith("\0")


def _bus_row(bus):
    if bus.type == "AC":
        return "ac_main" if bus.role == "main" else "ac_other"
    if bus.role == "main":
        return "dc_main"
    return "dc_essential" if bus.role == "essential" else "dc_other"


# --- Step 2: order within rows ---------------------------------------------------------------


def _inversions(segments, position):
    """Pairs of segments whose ends swap sides between two rows."""
    pairs = sorted((position[u], position[v]) for u, v in segments)
    seen, total = [], 0
    for _, lower in pairs:
        total += len(seen) - bisect_right(seen, lower)
        insort(seen, lower)
    return total


class _Orderer:
    def __init__(self, net: _Network):
        self.net = net
        self.ties_by_row = {}
        for t in net.level_ties:
            self.ties_by_row.setdefault(net.row_of[t.from_], []).append(t)
        self.free_from = 1 if net.source_order else 0
        names = net.row_names
        self.contactor_row = names.index("source_contactor") if "source_contactor" in names else -1
        self.source_at = {s: i for i, s in enumerate(net.source_order)}
        self.real = [link for link in net.links if len(link.chain) == 2]
        engines = {src.id for src in net.defn.sources if src.kind == "engine_generator"}
        self.main_feeds = [
            (k.chain[0], k.chain[1])
            for k in net.links
            if net.place.get(k.top) == "source_contactor" and net.up[k.top][0] in engines
        ]

    def feed(self, contactor):
        """Place in the source row of the source above a source contactor."""
        return self.source_at[self.net.up[contactor][0]]

    def positions(self, rows):
        return {n: i for row in rows for i, n in enumerate(row)}

    def tie_cost(self, row, r):
        """What level ties pay to step over what lies between their two bars."""
        ties = self.ties_by_row.get(r)
        if not ties:
            return 0
        total = 0
        for t in ties:
            low, high = sorted((row.index(t.from_), row.index(t.to)))
            for node in row[low + 1 : high]:
                total += 4 if self.net.is_bar(node) else 1
        return total

    def total(self, rows):
        pos = self.positions(rows)
        cost = sum(_inversions(s, pos) for s in self.net.segments)
        cost += sum(self.tie_cost(rows[r], r) for r in self.ties_by_row)
        # Engine order carries on down the page unless that takes a whole crossing more.
        cost += ENGINE_SWAP_COST * _inversions(self.main_feeds, pos)
        length = 0.0
        for segments in self.net.segments:
            for u, v in segments:
                ru, rv = self.net.row_of[u], self.net.row_of[v]
                length += abs((pos[u] + 0.5) / len(rows[ru]) - (pos[v] + 0.5) / len(rows[rv]))
        return (cost, round(length, 6))

    def real_inversions(self, rows):
        """Inversions counted on real items in adjacent rows only, as L2-LAY-014 counts them."""
        pos = self.positions(rows)
        return sum(
            _inversions(
                [(k.top, k.bottom) for k in self.real if self.net.row_of[k.top] == r], pos
            )
            for r in range(len(rows) - 1)
        )

    def sweep(self, rows, r, neighbours):
        pos = self.positions(rows)
        keys = {}
        for i, node in enumerate(rows[r]):
            near = [pos[n] for n in neighbours[node]]
            keys[node] = (sum(near) / len(near) if near else None, i)
        for t in self.ties_by_row.get(r, ()):  # tied bars pull towards each other
            for bar, other in ((t.from_, t.to), (t.to, t.from_)):
                value, i = keys[bar]
                keys[bar] = (pos[other] if value is None else (2 * value + pos[other]) / 3, i)

        def order(node):
            value, i = keys[node]
            first = self.feed(node) if r == self.contactor_row else 0
            return (first, i if value is None else value, i)

        rows[r] = sorted(rows[r], key=order)

    def crossed(self, left, right, pos):
        """Crossings between the links of two nodes of a row, with `left` on the left."""
        net = self.net
        total = 0
        for table in (net.up, net.down):
            for a in table[left]:
                for b in table[right]:
                    if pos[a] > pos[b]:
                        total += 1
        return total

    def sift(self, rows, r):
        """Moves each node of a row to its best place there, with the other rows held still."""
        pos = self.positions(rows)
        row = rows[r]
        for node in sorted(row, key=lambda n: _natural(n)):
            row.remove(node)
            value = sum(self.crossed(node, other, pos) for other in row)
            best, best_at = None, 0
            for at in range(len(row) + 1):
                cost = (value + self.tie_cost([*row[:at], node, *row[at:]], r), at)
                if best is None or cost < best:
                    best, best_at = cost, at
                if at < len(row):
                    other = row[at]
                    value += self.crossed(other, node, pos) - self.crossed(node, other, pos)
            row.insert(best_at, node)

    def group_swaps(self, rows, r):
        """Contactors of one source trade places. A source contactor stays under its source."""
        pos = self.positions(rows)
        row = rows[r]
        for i in range(len(row) - 1):
            a, b = row[i], row[i + 1]
            better = self.crossed(b, a, pos) < self.crossed(a, b, pos)
            if better and self.feed(a) == self.feed(b):
                row[i], row[i + 1] = b, a

    def search(self, seed):
        rows = [list(r) for r in seed]
        best, best_cost = [list(r) for r in rows], self.total(rows)

        def keep():
            nonlocal best, best_cost
            cost = self.total(rows)
            if cost < best_cost:
                best, best_cost = [list(r) for r in rows], cost

        free = range(self.free_from, len(rows))
        for _ in range(6):
            for r in free:
                self.sweep(rows, r, self.net.up)
            keep()
            for r in reversed(free):
                self.sweep(rows, r, self.net.down)
            keep()
        rows = [list(r) for r in best]
        for _ in range(6):
            before = best_cost
            for r in (*free, *reversed(free)):
                if r == self.contactor_row:
                    self.group_swaps(rows, r)
                else:
                    self.sift(rows, r)
                keep()
            if best_cost == before:
                break
        return best

    def walked_seed(self):
        """Rows in the order a depth-first walk from the sources, left to right, reaches them."""
        net = self.net
        tied = {}
        for t in net.level_ties:
            tied.setdefault(t.from_, []).append(t.to)
            tied.setdefault(t.to, []).append(t.from_)
        seen = {}

        def walk(start):
            stack = [start]
            while stack:
                node = stack.pop()
                if node not in seen:
                    seen[node] = len(seen)
                    near = net.down[node] + tied.get(node, []) + net.up[node]
                    stack.extend(reversed(near))

        for row in net.rows:
            for node in row:
                walk(node)
        return [
            sorted(row, key=seen.__getitem__) if i >= self.free_from else list(row)
            for i, row in enumerate(net.rows)
        ]

    def declared_seed(self):
        net = self.net
        return [
            sorted(row, key=lambda n: (net.declared.get(n, len(net.declared)), _natural(n)))
            if i >= self.free_from
            else list(row)
            for i, row in enumerate(net.rows)
        ]

    def run(self):
        declared = self.declared_seed()
        limit = self.real_inversions(declared)
        mirrored = [
            row[::-1] if i >= self.free_from else list(row) for i, row in enumerate(self.net.rows)
        ]
        seeds = (self.net.rows, declared, mirrored, self.walked_seed())
        results = [self.search(seed) for seed in seeds]
        for rows in sorted(results, key=self.total):
            if self.real_inversions(rows) <= limit:
                return rows
        return declared


# --- Steps 3 and 4: strands and x ------------------------------------------------------------


class _Horizontal:
    """Finds the strands, then solves `x` for one spacing."""

    def __init__(self, net: _Network, rows):
        self.net = net
        self.rows = self._with_level_ties(rows)
        self.parent = {n: n for row in self.rows for n in row}
        self.covers = set()  # (bar, node): the strand of node lands on this bar
        self.straight = []  # links drawn as one straight segment
        self._find_strands()

    def _with_level_ties(self, rows):
        """Each level tie goes just to the right of the left of its two bars."""
        rows = [list(r) for r in rows]
        for t in sorted(self.net.level_ties, key=lambda k: _natural(k.tie)):
            row = rows[self.net.row_of[t.from_]]
            low = min(row.index(t.from_), row.index(t.to))
            row.insert(low + 1, t.tie)
        return rows

    def _find(self, parent, node):
        while parent[node] != node:
            parent[node] = parent[parent[node]]
            node = parent[node]
        return node

    def _edges(self, parent, covers):
        """Who must lie left of whom: pairs of variables, with no weights yet."""
        net = self.net
        edges = []

        def right_var(n):
            return ("R", n) if net.is_bar(n) else self._find(parent, n)

        def left_var(n):
            return ("L", n) if net.is_bar(n) else self._find(parent, n)

        for row in self.rows:
            for a, b in itertools.pairwise(row):
                edges.append((right_var(a), left_var(b), a, b))
            for n in row:
                if net.is_bar(n):
                    edges.append((("L", n), ("R", n), n, n))
        for bar, node in covers:
            var = self._find(parent, node)
            edges.append((("L", bar), var, bar, node))
            edges.append((var, ("R", bar), node, bar))
        return edges

    def _acyclic(self, parent, covers):
        edges = self._edges(parent, covers)
        out, into = {}, {}
        for a, b, *_ in edges:
            if a == b:
                return False
            out.setdefault(a, []).append(b)
            into[b] = into.get(b, 0) + 1
            into.setdefault(a, 0)
        ready = [n for n, k in into.items() if k == 0]
        seen = 0
        while ready:
            n = ready.pop()
            seen += 1
            for m in out.get(n, ()):
                into[m] -= 1
                if into[m] == 0:
                    ready.append(m)
        return seen == len(into)

    def _priority(self, link):
        """Which links win a column: inside a TRU or a feed, then main feeds, TRUs, ties."""
        net = self.net
        kinds = {net.kind[link.top], net.kind[link.bottom]}
        place = net.place[link.top if net.kind[link.top] == "contactor" else link.bottom]
        if "tru" in kinds:
            rank = (0, 0)
        elif "bus" not in kinds:
            rank = (1, 0)
        elif place == "source_contactor" and len(link.chain) == 2:
            rank = (2, net.source_order.index(net.up[link.top][0]))
        elif place in ("tru_in", "tru_out"):
            rank = (3, 0)
        elif place == "source_contactor":
            rank = (4, 0)  # a feed that passes other rows gives way to what starts in them
        else:
            rank = (5, 0)
        return (rank, -len(link.chain), _natural(link.top), _natural(link.bottom))

    def _find_strands(self):
        net = self.net
        for link in sorted(net.links, key=self._priority):
            if net.kind[link.top] != "bus" and net.single_feed.get(link.top, 1) > 1:
                continue  # a source with several contactors sits above them all
            parent = dict(self.parent)
            covers = set(self.covers)
            for u, v in zip(link.chain, link.chain[1:], strict=False):
                if net.is_bar(u):
                    covers.add((u, v))
                elif net.is_bar(v):
                    covers.add((v, u))
                else:
                    parent[self._find(parent, u)] = self._find(parent, v)
            if self._acyclic(parent, covers):
                self.parent, self.covers = parent, covers
                self.straight.append(link)

    def _half(self, node, spacing, side):
        """Room an entry needs on one side of its centre."""
        net = self.net
        if net.is_dummy(node):
            return 0
        half = net.size[node][0] // 2
        if side == "right" and (net.kind[node] == "tru" or net.place[node] == "source"):
            half += spacing.label
        return half

    def _weighted(self, spacing):
        net = self.net
        edges = []
        for a_var, b_var, a, b in self._edges(self.parent, self.covers):
            if a == b:
                w = spacing.bar
            elif a_var == ("L", a) or b_var == ("R", b):
                w = BAR_END  # a strand inside its bar
            else:
                left = 0 if net.is_bar(a) else self._half(a, spacing, "right")
                right = 0 if net.is_bar(b) else self._half(b, spacing, "left")
                w = left + spacing.gap + right
                if a in net.tie_ids and b in net.tie_ids:
                    w += TIE_ROOM  # two step-overs may leave between neighbouring ties
            edges.append((a_var, b_var, w))
        for bus in net.crew_buses:
            switch = ("S", bus)
            half = SWITCH_SIZE[0] // 2
            edges.append((("L", bus), switch, half + 4))
            edges.append((switch, ("R", bus), half + 4))
            for row in self.rows:
                for n in row:
                    if (bus, n) in self.covers and n in net.down.get(bus, ()):
                        var = self._find(self.parent, n)
                        edges.append((switch, var, 2 * half + 4))
        for row in self.rows:
            first, last = row[0], row[-1]
            a = ("L", first) if net.is_bar(first) else self._find(self.parent, first)
            b = ("R", last) if net.is_bar(last) else self._find(self.parent, last)
            left = 0 if net.is_bar(first) else self._half(first, spacing, "left")
            right = 0 if net.is_bar(last) else self._half(last, spacing, "right")
            edges.append(("START", a, MARGIN + left))
            edges.append((b, "END", MARGIN + right))
        return edges

    @staticmethod
    def _longest(edges, reverse=False):
        out, into = {}, {}
        for a, b, w in edges:
            if reverse:
                a, b = b, a
            out.setdefault(a, []).append((b, w))
            into[b] = into.get(b, 0) + 1
            into.setdefault(a, 0)
        ready = sorted((n for n, k in into.items() if k == 0), key=repr)
        dist = {n: 0 for n in into}
        while ready:
            n = ready.pop()
            for m, w in out.get(n, ()):
                dist[m] = max(dist[m], dist[n] + w)
                into[m] -= 1
                if into[m] == 0:
                    ready.append(m)
        return dist

    def _solve(self, spacing):
        edges = self._weighted(spacing)
        forward = self._longest(edges)
        backward = self._longest(edges, reverse=True)
        total = forward["END"]
        x = {v: (forward[v] + total - backward[v]) / 2 for v in forward}
        self._relax(x, edges)
        return x, total

    def _relax(self, x, edges):
        """Slide each source with several contactors, and each dogleg end, towards its partners."""
        net = self.net
        lower, upper = {}, {}
        for a, b, w in edges:
            lower.setdefault(b, []).append((a, w))
            upper.setdefault(a, []).append((b, w))
        straight = {id(link) for link in self.straight}
        partners = {}
        for link in net.links:
            if id(link) not in straight:
                for me, other in ((link.top, link.bottom), (link.bottom, link.top)):
                    feeds_on = net.place.get(me) == "source_contactor" and net.is_bar(other)
                    if not net.is_bar(me) and not feeds_on:
                        var = self._find(self.parent, me)
                        partners.setdefault(var, []).append(other)
        for _ in range(8):
            for var in sorted(partners, key=repr):
                wanted = [self._centre(x, other) for other in partners[var]]
                target = sum(wanted) / len(wanted)
                low = max((x[a] + w for a, w in lower.get(var, ())), default=x[var])
                high = min((x[b] - w for b, w in upper.get(var, ())), default=x[var])
                x[var] = min(max(target, low), high)

    def _centre(self, x, node):
        if self.net.is_bar(node):
            return (x[("L", node)] + x[("R", node)]) / 2
        return x[self._find(self.parent, node)]

    def solve(self):
        for spacing in SPACINGS:
            x, total = self._solve(spacing)
            if total <= DRAW_WIDTH:
                break
        self.spacing = spacing
        self.total = total
        self.x = x
        return x

    def centre(self, node):
        return round(self.x[self._find(self.parent, node)])

    def bar_span(self, bar):
        return round(self.x[("L", bar)]), round(self.x[("R", bar)])

    def switch_centre(self, bus):
        """At the left end of the bar, the rest of which stays free for its label."""
        return self.bar_span(bus)[0] + SWITCH_SIZE[0] // 2 + 4


# --- Step 5: y and routing -------------------------------------------------------------------


def _row_tops(net: _Network):
    """Top of each row and each row's height, spread to fill DRAW_HEIGHT within the gap limits."""
    heights, extras = [], []
    for row in net.rows:
        heights.append(max((net.size[n][1] for n in row if not net.is_dummy(n)), default=0))
        crew = any(n in net.crew_buses for n in row)
        extras.append(SWITCH_SIZE[1] + SWITCH_DROP if crew else 0)
    for t in net.level_ties:
        r = net.row_of[t.from_]
        heights[r] = max(heights[r], CONTACTOR_SIZE[1])
    count = len(heights)
    spare = DRAW_HEIGHT - 2 * MARGIN - sum(heights) - sum(extras)
    gap = spare // (count - 1) if count > 1 else 0
    gap = max(GAP_MIN, min(GAP_MAX, gap))
    tops, y = [], MARGIN
    for height, extra in zip(heights, extras, strict=True):
        tops.append(y)
        y += height + extra + gap
    return tops, heights, extras


def _boxes(net, horizontal, tops, heights):
    boxes = {}
    for r, row in enumerate(horizontal.rows):
        cy = tops[r] + heights[r] // 2
        for node in row:
            if net.is_dummy(node):
                continue
            if net.is_bar(node):
                left, right = horizontal.bar_span(node)
                boxes[node] = Box(left, cy - BAR_HEIGHT // 2, right - left, BAR_HEIGHT)
            else:
                w, h = net.size[node]
                boxes[node] = Box(horizontal.centre(node) - w // 2, cy - h // 2, w, h)
    for bus in net.crew_buses:
        w, h = SWITCH_SIZE
        bar = boxes[bus]
        boxes[f"{bus}_switch"] = Box(
            horizontal.switch_centre(bus) - w // 2, bar.bottom + SWITCH_DROP, w, h
        )
    return boxes


class _Router:
    """Cheapest orthogonal paths on a sparse grid. All connectors lie on its lines."""

    def __init__(self, boxes, xs, ys):
        self.boxes = boxes
        self.xs = sorted(set(xs))
        self.ys = sorted(set(ys))
        self.xi = {x: i for i, x in enumerate(self.xs)}
        self.yi = {y: j for j, y in enumerate(self.ys)}
        self.h_used = set()  # (i, j): the edge from node (i, j) to (i + 1, j)
        self.v_used = set()  # (i, j): the edge from node (i, j) to (i, j + 1)
        self.drawn_ends = {}  # the same edges, by direction, to the items of what is drawn there
        self.joints = set()  # ends and bends of connectors, by (i, j)
        self.h_near = {}  # items each grid edge passes within CLEARANCE of
        self.v_near = {}
        for id_, box in boxes.items():
            self._mark(id_, box)

    def _mark(self, id_, box):
        left = bisect_left(self.xs, box.x - CLEARANCE)
        right = bisect_right(self.xs, box.right + CLEARANCE)
        top = bisect_left(self.ys, box.y - CLEARANCE)
        bottom = bisect_right(self.ys, box.bottom + CLEARANCE)
        for j in range(top, bottom):
            for i in range(max(left - 1, 0), min(right, len(self.xs) - 1)):
                self.h_near.setdefault((i, j), []).append(id_)
        for i in range(left, right):
            for j in range(max(top - 1, 0), min(bottom, len(self.ys) - 1)):
                self.v_near.setdefault((i, j), []).append(id_)

    def claim(self, points, ends):
        """Records a drawn connector, whose end items are `ends`."""
        for a, b in itertools.pairwise(points):
            ax, ay, bx, by = self.xi[a[0]], self.yi[a[1]], self.xi[b[0]], self.yi[b[1]]
            if ay == by:
                self.h_used.update((i, ay) for i in range(min(ax, bx), max(ax, bx)))
                edges = [(EAST, i, ay) for i in range(min(ax, bx), max(ax, bx))]
            else:
                self.v_used.update((ax, j) for j in range(min(ay, by), max(ay, by)))
                edges = [(SOUTH, ax, j) for j in range(min(ay, by), max(ay, by))]
            for edge in edges:
                self.drawn_ends.setdefault(edge, set()).update(ends)
        self.joints.update((self.xi[p[0]], self.yi[p[1]]) for p in points)

    def _blocked(self, i, j, direction, ends):
        """True when the grid edge leaving (i, j) enters an item or comes too close to one."""
        if direction == EAST:
            near = self.h_near.get((i, j))
        elif direction == WEST:
            near = self.h_near.get((i - 1, j))
        elif direction == SOUTH:
            near = self.v_near.get((i, j))
        else:
            near = self.v_near.get((i, j - 1))
        if not near:
            return False
        dx, dy = STEPS[direction]
        a, b = (self.xs[i], self.ys[j]), (self.xs[i + dx], self.ys[j + dy])
        return any(n not in ends or _crosses(self.boxes[n], a, b) for n in near)

    def _used(self, i, j, direction):
        if direction == EAST:
            return (i, j) in self.h_used
        if direction == WEST:
            return (i - 1, j) in self.h_used
        if direction == SOUTH:
            return (i, j) in self.v_used
        return (i, j - 1) in self.v_used

    def _foreign(self, i, j, direction, ends):
        """True when an edge already carries a connector sharing no item with `ends`."""
        if not self._used(i, j, direction):
            return False
        horizontal = direction in (EAST, WEST)
        edge = (EAST if horizontal else SOUTH, i - (direction == WEST), j - (direction == NORTH))
        return not self.drawn_ends[edge] & ends

    def _through(self, i, j, direction):
        """True when moving straight through a node crosses a connector."""
        if direction in (EAST, WEST):
            return (i, j) in self.v_used and (i, j - 1) in self.v_used
        return (i, j) in self.h_used and (i - 1, j) in self.h_used

    def route(self, starts, goals, ends, allow_overlap=False, any_connector=False):
        """`starts` and `goals` are (x, y, direction). Returns corner points, or None.

        `allow_overlap` lets a route share a line with a connector that ends on one of its items,
        and `any_connector` with any connector.
        """
        goal_states = {(self.xi[x], self.yi[y], d) for x, y, d in goals}
        begin = {(self.xi[x], self.yi[y], d) for x, y, d in starts}
        best = dict.fromkeys(begin, 0)
        heap = [(0, state) for state in sorted(begin)]
        heapq.heapify(heap)
        came = {}
        while heap:
            cost, state = heapq.heappop(heap)
            if cost > best[state]:
                continue
            if state in goal_states:
                return self._walk(state, came)
            i, j, d = state
            for nd in (d,) if state in begin else (d, *self._turns(d)):
                dx, dy = STEPS[nd]
                ni, nj = i + dx, j + dy
                if not (0 <= ni < len(self.xs) and 0 <= nj < len(self.ys)):
                    continue
                if self._blocked(i, j, nd, ends):
                    continue
                penalty = self._penalty(i, j, d, nd, state in begin)
                if (ni, nj, nd) not in goal_states and (ni, nj) in self.joints:
                    penalty += OVERLAP_COST
                if penalty >= OVERLAP_COST and not allow_overlap:
                    continue
                if not any_connector and self._foreign(i, j, nd, ends):
                    continue
                step = abs(self.xs[ni] - self.xs[i]) + abs(self.ys[nj] - self.ys[j]) + penalty
                new = (ni, nj, nd)
                if cost + step < best.get(new, float("inf")):
                    best[new] = cost + step
                    came[new] = state
                    heapq.heappush(heap, (cost + step, new))
        return None

    def _penalty(self, i, j, direction, next_direction, at_start):
        """What it costs to leave node (i, j), given what is drawn there already."""
        penalty = 0
        if self._used(i, j, next_direction):
            penalty += OVERLAP_COST
        if at_start:
            return penalty
        if (i, j) in self.joints:
            return penalty + OVERLAP_COST
        if next_direction != direction:
            return penalty + BEND_COST + (OVERLAP_COST if self.any_used(i, j) else 0)
        return penalty + (CROSSING_COST if self._through(i, j, direction) else 0)

    def any_used(self, i, j):
        return (
            (i, j) in self.h_used
            or (i - 1, j) in self.h_used
            or (i, j) in self.v_used
            or (i, j - 1) in self.v_used
        )

    @staticmethod
    def _turns(direction):
        return (SOUTH, NORTH) if direction in (EAST, WEST) else (EAST, WEST)

    def _walk(self, state, came):
        path = [state]
        while path[-1] in came:
            path.append(came[path[-1]])
        path.reverse()
        points = [(self.xs[i], self.ys[j]) for i, j, _ in path]
        return _corners(points)


def _crosses(box, a, b):
    """True when a segment enters the open interior of a box."""
    low_x, high_x = sorted((a[0], b[0]))
    low_y, high_y = sorted((a[1], b[1]))
    if low_x == high_x:
        return box.x < low_x < box.right and low_y < box.bottom and box.y < high_y
    return box.y < low_y < box.bottom and low_x < box.right and box.x < high_x


def _corners(points):
    out = [points[0]]
    for p, q in itertools.pairwise(points):
        last = out[-1]
        if not (last[0] == p[0] == q[0] or last[1] == p[1] == q[1]):
            out.append(p)
    if len(points) > 1:
        out.append(points[-1])
    return out


class _Wiring:
    """Draws every connector, straight ones first."""

    def __init__(self, net, horizontal, boxes, tops, heights, extras):
        self.net = net
        self.h = horizontal
        self.boxes = boxes
        self.tops, self.heights, self.extras = tops, heights, extras
        self.width = horizontal.total
        self.connectors = {}
        self.pending = []
        self.router = _Router(boxes, self._grid_xs(), self._grid_ys())

    def _source_ports(self, node):
        if self.net.kind[node] != "contactor" and self.net.single_feed.get(node, 1) > 1:
            cx = self.boxes[node].cx
            return [cx - 10, cx, cx + 10]
        return [self.boxes[node].cx]

    def _grid_xs(self):
        firm, soft = [LANE, self.width - LANE], []
        for id_, box in self.boxes.items():
            if self.net.kind.get(id_) == "bus":
                firm += [box.x, box.cx, box.right]
                soft += [box.x - 8, box.right + 8]
                soft += range(box.x + BAR_END, box.right - BAR_END + 1, 24)
            else:
                firm.append(box.cx)
                if id_ in self.net.tie_ids:
                    firm += [box.x, box.right]
                elif id_ in self.net.kind:
                    firm += self._source_ports(id_)
        for row in self.h.rows:
            edges = sorted(
                (self.boxes[n].x, self.boxes[n].right) for n in row if n in self.boxes
            )
            for (_, right), (left, _) in itertools.pairwise(edges):
                gap = left - right
                if gap >= 24:  # two ways between these neighbours, or one
                    firm += [right + gap // 3, left - gap // 3]
                elif gap > 0:
                    firm.append((left + right) // 2)
        kept = set(firm)
        for x in sorted(set(soft)):
            if all(abs(x - k) >= 8 for k in kept):
                kept.add(x)
        return kept

    def _grid_ys(self):
        ys = set()
        for box in self.boxes.values():
            ys |= {box.y, box.bottom, box.cy}
        lows = [t + h + e for t, h, e in zip(self.tops, self.heights, self.extras, strict=True)]
        for low, top in zip(lows, self.tops[1:], strict=False):
            gap = top - low
            lanes = max(3, gap // TRACK - 1)
            ys |= {low + gap * k // (lanes + 1) for k in range(1, lanes + 1)}
        ys.add(lows[-1] + LANE)
        return ys

    def run(self):
        straight = {id(link) for link in self.h.straight}
        for link in self.net.links:
            if id(link) in straight:
                self._draw_straight(link)
            else:
                self.pending.append(link)
        self._draw_level_ties()
        order = sorted(self.pending, key=self._span)
        for link in order:
            self._draw_dogleg(link)
        return self._ordered()

    def _span(self, link):
        a, b = self.boxes[link.top], self.boxes[link.bottom]
        return (abs(a.cx - b.cx) + abs(a.cy - b.cy), _natural(link.top), _natural(link.bottom))

    def _store(self, ends, first, points):
        """Records a drawn connector, with `points` running from the item `first`."""
        self.router.claim(points, ends)
        self.connectors[ends] = points if ends[0] == first else points[::-1]

    def _draw_straight(self, link):
        top, bottom = self.boxes[link.top], self.boxes[link.bottom]
        node = link.bottom if self.net.is_bar(link.top) else link.top
        x = self.boxes[node].cx
        self._store(link.ends, link.top, [(x, top.bottom), (x, bottom.y)])

    def _draw_dogleg(self, link):
        top, bottom = self.boxes[link.top], self.boxes[link.bottom]
        starts = [(x, top.bottom, SOUTH) for x in self._ports(link.top, top, top.bottom)]
        goals = [(x, bottom.y, SOUTH) for x in self._ports(link.bottom, bottom, bottom.y)]
        if self.net.is_bar(link.top):
            starts += self._bar_ends(top, EAST, WEST)
        if self.net.is_bar(link.bottom):
            goals += self._bar_ends(bottom, WEST, EAST)
        self._store(link.ends, link.top, self._find_route(starts, goals, link.top, link.bottom))

    def _ports(self, node, box, y):
        if not self.net.is_bar(node):
            return self._source_ports(node)
        return self._free_landings(box, y)

    def _bar_ends(self, bar, at_right, at_left):
        """The free ends of a bar, each with the direction a route has there."""
        ends = [(bar.right, bar.cy, at_right), (bar.x, bar.cy, at_left)]
        router = self.router
        return [e for e in ends if (router.xi[e[0]], router.yi[e[1]]) not in router.joints]

    def _free_landings(self, bar, y):
        """Grid lines on one edge of a bar, keeping clear of what already lands there."""
        taken = [
            p[0]
            for points in self.connectors.values()
            for p in (points[0], points[-1])
            if p[1] == y and bar.x <= p[0] <= bar.right
        ]
        lines = [x for x in self.router.xs if bar.x + 6 <= x <= bar.right - 6]
        return [x for x in lines if all(abs(x - t) >= 12 for t in taken)] or lines

    def _find_route(self, starts, goals, a, b):
        ends = {a, b}
        points = self.router.route(starts, goals, ends)
        if points is None:
            points = self.router.route(starts, goals, ends, allow_overlap=True)
        if points is None:
            points = self.router.route(starts, goals, ends, allow_overlap=True, any_connector=True)
        if points is None:  # every grid route is walled in, which needs an item wider than a row
            x0, y0, _ = starts[0]
            x1, y1, _ = goals[0]
            points = [(x0, y0), (x0, y1), (x1, y1)] if x0 != x1 else [(x0, y0), (x1, y1)]
        return points

    def _draw_level_ties(self):
        stepovers = []
        for t in sorted(self.net.level_ties, key=lambda k: _natural(k.tie)):
            row = self.h.rows[self.net.row_of[t.from_]]
            at = row.index(t.tie)
            box = self.boxes[t.tie]
            for bar, ends in ((t.from_, (t.from_, t.tie)), (t.to, (t.tie, t.to))):
                on_left = row.index(bar) < at
                between = row[row.index(bar) + 1 : at] if on_left else row[at + 1 : row.index(bar)]
                if all(self.net.is_dummy(n) for n in between):
                    edge = self.boxes[bar].right if on_left else self.boxes[bar].x
                    face = box.x if on_left else box.right
                    self._store(ends, t.tie, [(face, box.cy), (edge, box.cy)])
                else:
                    stepovers.append(Stepover(bar, t.tie, ends, on_left))
        for stepover in stepovers:
            self._draw_stepover(stepover)

    def _draw_stepover(self, s):
        box, bar = self.boxes[s.tie], self.boxes[s.bar]
        direction = WEST if s.on_left else EAST
        face = box.x if s.on_left else box.right
        goals = [(x, bar.y, SOUTH) for x in self._free_landings(bar, bar.y)]
        goals += [(x, bar.bottom, NORTH) for x in self._free_landings(bar, bar.bottom)]
        goals.append((bar.right, bar.cy, WEST) if s.on_left else (bar.x, bar.cy, EAST))
        # Turn up or down at the first lane out, which leaves the next lane to a neighbouring tie.
        router = self.router
        xs = router.xs
        lane = xs[bisect_left(xs, face) - 1] if s.on_left else xs[bisect_right(xs, face)]
        at = (router.xi[lane], router.yi[box.cy])
        turned = at not in router.joints and not router.any_used(*at)
        if turned:
            starts = [(lane, box.cy, NORTH), (lane, box.cy, SOUTH)]
        else:
            starts = [(face, box.cy, direction)]
        points = self._find_route(starts, goals, s.tie, s.bar)
        if turned:
            points = [(face, box.cy), *points]
        self._store(s.ends, s.tie, points)

    def _ordered(self):
        out = []
        for ends in sorted(self.connectors, key=lambda e: (_natural(e[0]), _natural(e[1]))):
            points = self.connectors[ends]
            out.append({"from": ends[0], "to": ends[1], "points": [list(p) for p in points]})
        return out


# --- Text room -------------------------------------------------------------------------------


def _label_slots(net, boxes, connectors, width, height):
    """A free box for each bus, source and TRU label, so the front end needs no layout logic."""
    segments = [
        (a, b)
        for connector in connectors
        for a, b in zip(connector["points"], connector["points"][1:], strict=False)
    ]
    taken = list(boxes.values())

    def clashes(candidate, own):
        hits = sum(1 for box in taken if box is not own and box.hits(candidate))
        return hits + sum(1 for a, b in segments if candidate.hits_segment(a, b))

    def best(candidates, own):
        fitted = [
            c for c in candidates
            if c.x >= 2 and c.y >= 2 and c.right <= width - 2 and c.bottom <= height - 2
        ]
        least, chosen = None, candidates[0]
        for candidate in fitted:
            count = clashes(candidate, own)
            if count == 0:
                return candidate
            if least is None or count < least:
                least, chosen = count, candidate
        return chosen

    slots = {}
    labelled = [i for i in boxes if net.kind.get(i, "contactor") != "contactor"]
    # Narrow bars first, as they have the fewest places. Icons last, with a side each to choose.
    for id_ in sorted(labelled, key=lambda i: (net.kind[i] != "bus", boxes[i].w, _natural(i))):
        box = boxes[id_]
        candidates = _bus_candidates(box) if net.kind[id_] == "bus" else _icon_candidates(box)
        slots[id_] = best(candidates, box)
        taken.append(slots[id_])
    return slots


def _icon_candidates(box):
    top = box.cy - TEXT_HEIGHT
    out = []
    for width in (ICON_LABEL_WIDTH, ICON_LABEL_WIDTH - 8):
        out.append(Box(box.right + 4, top, width, 2 * TEXT_HEIGHT))
        out.append(Box(box.x - 4 - width, top, width, 2 * TEXT_HEIGHT))
    return out


def _bus_candidates(bar):
    """Strips along the bar, one line then two, which may run past its ends."""
    out = []
    for width, height in ((BUS_LABEL_WIDTH, TEXT_HEIGHT), (ICON_LABEL_WIDTH, 2 * TEXT_HEIGHT)):
        for y in (bar.bottom + 1, bar.bottom + 4, bar.y - height - 1, bar.y - height - 4):
            out += [Box(x, y, width, height) for x in range(bar.x, bar.right - width + 1, 4)]
            out += [Box(bar.x - shift, y, width, height) for shift in range(0, width // 2, 4)]
            out += [Box(bar.right - width + s, y, width, height) for s in range(0, width + 12, 4)]
    return out


# --- Entry point -----------------------------------------------------------------------------


def layout(defn: Definition) -> dict:
    """Coordinates for a validated definition. See the module docstring for the method."""
    net = _Network(defn)
    if not net.rows:
        return {"items": [], "connectors": [], "width": 2 * MARGIN, "height": 2 * MARGIN}
    rows = _Orderer(net).run()
    horizontal = _Horizontal(net, rows)
    horizontal.solve()
    tops, heights, extras = _row_tops(net)
    boxes = _boxes(net, horizontal, tops, heights)
    height = tops[-1] + heights[-1] + extras[-1] + MARGIN
    connectors = _Wiring(net, horizontal, boxes, tops, heights, extras).run()
    slots = _label_slots(net, boxes, connectors, horizontal.total, height)

    items = []
    for id_ in sorted(boxes, key=_natural):
        box = boxes[id_]
        kind = net.kind.get(id_, "crew_switch")
        item = {"id": id_, "kind": kind, "x": box.x, "y": box.y, "width": box.w, "height": box.h}
        if kind == "contactor":
            item["orientation"] = net.orientation[id_]
        if id_ in slots:
            slot = slots[id_]
            item["label"] = {"x": slot.x, "y": slot.y, "width": slot.w, "height": slot.h}
        items.append(item)
    return {
        "items": items,
        "connectors": connectors,
        "width": horizontal.total,
        "height": height,
    }
