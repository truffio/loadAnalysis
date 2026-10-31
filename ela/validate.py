"""Definition file validator (docs/spec.md §5.2).

`validate` first runs the Pydantic schema, which finds missing keys, wrong types and values out of
range across the whole document. It then runs the checks that span elements over the raw document,
so one broken element never hides a fault in another. Those checks skip any element or reference
that is already reported, which keeps each fault to one error.
"""

from collections import Counter
from dataclasses import dataclass, field

from pydantic import ValidationError

from ela.model import (
    BandInfo,
    Bands,
    BandSettings,
    Bus,
    Contactor,
    Definition,
    Load,
    Meta,
    Scenario,
    Settings,
    Source,
    Tru,
)

COLLECTIONS = ("sources", "buses", "trus", "contactors", "loads")
RUN_STATES = ("operative", "failed")
CONTACTOR_ENDS = {
    "source": ({"source", "bus"}, "a source and a bus"),
    "bus_tie": ({"bus"}, "two buses"),
    "tru": ({"bus", "tru"}, "a bus and a TRU"),
}


@dataclass
class Issue:
    """One error or warning, located by a `$`-rooted JSON path."""

    path: str
    message: str


@dataclass
class ValidationResult:
    errors: list[Issue] = field(default_factory=list)
    warnings: list[Issue] = field(default_factory=list)
    definition: Definition | None = None


def validate(doc) -> ValidationResult:
    """Check a parsed JSON document. Invalid content is reported, never raised."""
    result = ValidationResult()
    definition = None
    try:
        definition = Definition.model_validate(doc)
    except ValidationError as exc:
        result.errors += [_schema_issue(e) for e in exc.errors()]
    if isinstance(doc, dict):
        _Checks(doc, result).run()
    if not result.errors:
        result.definition = definition
    return result


def check_states(definition, states, path="$.states") -> list[Issue]:
    """Check a state map, as used by scenarios and by the interactive analysis request.

    `definition` is a `Definition` or a parsed document. Each error is at `<path>.<key>`.
    """
    if isinstance(definition, Definition):
        definition = definition.model_dump(by_alias=True)
    if not isinstance(states, dict):
        return [Issue(path, "states must be an object")]
    allowed = _state_values(definition)
    issues = []
    for key, value in states.items():
        if key not in allowed:
            issues.append(Issue(f"{path}.{key}", f"'{key}' is not a component with a state"))
        elif value not in allowed[key]:
            choices = " or ".join(allowed[key])
            issues.append(
                Issue(f"{path}.{key}", f"'{value}' is not a state of '{key}', use {choices}")
            )
    return issues


def _state_values(doc) -> dict[str, tuple[str, ...]]:
    """Each stateful component's id and allowed values (DD-009)."""
    allowed = {}
    for _, s in _indexed(doc.get("sources")):
        rat = s.get("kind") == "emergency_generator"
        allowed[_str(s.get("id"))] = ("available", "unavailable") if rat else RUN_STATES
    for _, t in _indexed(doc.get("trus")):
        allowed[_str(t.get("id"))] = RUN_STATES
    for _, c in _indexed(doc.get("contactors")):
        allowed[_str(c.get("id"))] = ("closed", "open")
    for _, b in _indexed(doc.get("buses")):
        if b.get("crew_switch") is True:
            allowed[_str(b.get("id"))] = ("on", "off")
    return allowed


def _schema_issue(error) -> Issue:
    """Turn a Pydantic error into an Issue, with a missing key reported at its parent."""
    loc = error["loc"]
    if error["type"] in ("missing", "missing_key"):
        key = loc[-1]
        return Issue(_path(loc[:-1]), f"missing required key '{key}'")
    return Issue(_path(loc), error["msg"])


def _path(loc) -> str:
    return "$" + "".join(f"[{p}]" if isinstance(p, int) else f".{p}" for p in loc)


def _indexed(value):
    """Index and element of each object in a list."""
    if isinstance(value, list):
        yield from ((i, v) for i, v in enumerate(value) if isinstance(v, dict))


def _str(value) -> str | None:
    return value if isinstance(value, str) else None


class _Checks:
    """The checks that span elements, run over the raw document."""

    def __init__(self, doc, result):
        self.doc = doc
        self.result = result
        self.sources = {
            s["id"]: s for _, s in _indexed(doc.get("sources")) if _str(s.get("id")) is not None
        }
        self.buses = {
            b["id"]: b for _, b in _indexed(doc.get("buses")) if _str(b.get("id")) is not None
        }
        self.trus = {
            t["id"]: t for _, t in _indexed(doc.get("trus")) if _str(t.get("id")) is not None
        }
        self.contactors = list(_indexed(doc.get("contactors")))
        self.node_ids = self.sources.keys() | self.buses.keys() | self.trus.keys()
        self.repeated = self._repeated_ids()
        # A missing collection is its own error, and every reference into it would repeat that.
        self.can_resolve = all(isinstance(doc.get(k), list) for k in ("sources", "buses", "trus"))
        self.loose = set()  # contactors with an already reported fault, by list index

    def run(self):
        self._report_repeated_ids()
        self._check_sources()
        self._check_load_references()
        self._check_trus()
        self._check_contactors()
        self._check_tru_contactors()
        self._check_scenarios()
        self._warn_unknown_keys()
        self._warn_voltage_mismatch()
        self._warn_unconnected()
        self._warn_no_essential_load()

    def _error(self, path, message):
        self.result.errors.append(Issue(path, message))

    def _warn(self, path, message):
        self.result.warnings.append(Issue(path, message))

    # --- Identity ---

    def _ids(self):
        for collection in COLLECTIONS:
            for i, element in _indexed(self.doc.get(collection)):
                id_ = _str(element.get("id"))
                if id_ is not None:
                    yield id_, f"$.{collection}[{i}].id"

    def _repeated_ids(self):
        counts = Counter(id_ for id_, _ in self._ids())
        return {id_ for id_, n in counts.items() if n > 1}

    def _report_repeated_ids(self):
        seen = set()
        for id_, path in self._ids():
            if id_ in seen:
                self._error(path, f"id '{id_}' is already used")
            seen.add(id_)
        seen = set()
        for i, scenario in _indexed(self.doc.get("scenarios")):
            id_ = _str(scenario.get("id"))
            if id_ in seen:
                self._error(f"$.scenarios[{i}].id", f"scenario id '{id_}' is already used")
            seen.add(id_)

    # --- Sources ---

    def _check_sources(self):
        apu_seen = False
        engines = set()
        for i, source in _indexed(self.doc.get("sources")):
            kind = source.get("kind")
            output = source.get("output")
            if kind == "apu_generator":
                if apu_seen:
                    self._error(f"$.sources[{i}].kind", "only one APU generator is allowed")
                apu_seen = True
            if kind == "engine_generator":
                engine = source.get("engine")
                if isinstance(engine, int) and engine in engines:
                    self._error(f"$.sources[{i}].engine", f"engine {engine} already has a generator")
                if isinstance(engine, int):
                    engines.add(engine)
            if (kind == "battery" and output == "AC") or (
                kind in ("engine_generator", "apu_generator") and output == "DC"
            ):
                self._error(f"$.sources[{i}].output", f"a {kind} cannot have output {output}")

    # --- References ---

    def _check_load_references(self):
        if not self.can_resolve:
            return
        for i, load in _indexed(self.doc.get("loads")):
            bus = _str(load.get("bus"))
            if bus is not None and bus not in self.buses:
                self._error(f"$.loads[{i}].bus", f"unknown bus '{bus}'")

    def _check_trus(self):
        for i, tru in _indexed(self.doc.get("trus")):
            for key, wanted in (("input_bus", "AC"), ("output_bus", "DC")):
                bus_id = _str(tru.get(key))
                if bus_id is None or not self.can_resolve:
                    continue
                path = f"$.trus[{i}].{key}"
                if bus_id not in self.buses:
                    self._error(path, f"unknown bus '{bus_id}'")
                elif self.buses[bus_id].get("type") not in (wanted, None):
                    self._error(path, f"'{bus_id}' is not a {wanted} bus")

    def _node_class(self, id_):
        if id_ in self.buses:
            return "bus"
        return "source" if id_ in self.sources else "tru"

    def _tru_buses_sound(self, tru):
        """True when a TRU's own bus keys are good enough to judge its contactors."""
        in_bus = self.buses.get(_str(tru.get("input_bus")))
        out_bus = self.buses.get(_str(tru.get("output_bus")))
        return (
            in_bus is not None
            and out_bus is not None
            and in_bus.get("type") in ("AC", None)
            and out_bus.get("type") in ("DC", None)
        )

    def _side(self, id_, other):
        """AC or DC for a node at a contactor, or None when it cannot be told."""
        if id_ in self.buses:
            return self.buses[id_].get("type")
        if id_ in self.sources:
            return self.sources[id_].get("output")
        tru = self.trus[id_]
        if self._tru_buses_sound(tru):
            if other == tru.get("input_bus"):
                return "AC"
            if other == tru.get("output_bus"):
                return "DC"
        return None

    def _check_contactors(self):
        for i, contactor in self.contactors:
            path = f"$.contactors[{i}]"
            ends = _str(contactor.get("from")), _str(contactor.get("to"))
            if self.can_resolve:
                for key, end in zip(("from", "to"), ends, strict=True):
                    if end is not None and end not in self.node_ids:
                        self._error(f"{path}.{key}", f"unknown node '{end}'")
                        self.loose.add(i)
            if _str(contactor.get("kind")) not in CONTACTOR_ENDS or None in ends:
                self.loose.add(i)
            a, b = ends
            if None in ends or not {a, b} <= self.node_ids or {a, b} & self.repeated:
                continue
            if a == b:
                self._error(path, f"contactor joins '{a}' to itself")
                self.loose.add(i)
                continue
            self._check_contactor_kind(i, path, contactor, a, b)
            sides = self._side(a, b), self._side(b, a)
            if None not in sides and sides[0] != sides[1]:
                self._error(path, f"contactor joins an AC node to a DC node ('{a}', '{b}')")

    def _check_contactor_kind(self, i, path, contactor, a, b):
        kind = _str(contactor.get("kind"))
        if kind not in CONTACTOR_ENDS:
            return
        wanted, described = CONTACTOR_ENDS[kind]
        if {self._node_class(a), self._node_class(b)} != wanted:
            self._error(path, f"a '{kind}' contactor must join {described} ('{a}', '{b}')")
            self.loose.add(i)

    def _check_tru_contactors(self):
        for i, tru in _indexed(self.doc.get("trus")):
            tru_id = _str(tru.get("id"))
            if tru_id is None or tru_id in self.repeated or not self._tru_buses_sound(tru):
                continue
            in_bus, out_bus = tru.get("input_bus"), tru.get("output_bus")
            if {in_bus, out_bus} & self.repeated or self._contactor_unclear(tru_id, in_bus, out_bus):
                continue
            joined = Counter()
            for _, contactor in self.contactors:
                ends = _str(contactor.get("from")), _str(contactor.get("to"))
                if contactor.get("kind") == "tru" and tru_id in ends:
                    other = ends[1] if ends[0] == tru_id else ends[0]
                    joined[other] += 1
            if joined != Counter({in_bus: 1, out_bus: 1}):
                self._error(
                    f"$.trus[{i}]",
                    f"TRU '{tru_id}' needs exactly one contactor from '{in_bus}' and one to "
                    f"'{out_bus}'",
                )

    def _contactor_unclear(self, tru_id, in_bus, out_bus):
        """True when an already reported contactor may be one this TRU depends on."""
        for i, contactor in self.contactors:
            if i not in self.loose:
                continue
            ends = {_str(contactor.get("from")), _str(contactor.get("to"))}
            if tru_id in ends or (None in ends and ends & {in_bus, out_bus, None}):
                return True
        return False

    # --- Scenarios ---

    def _check_scenarios(self):
        for i, scenario in _indexed(self.doc.get("scenarios")):
            states = scenario.get("states")
            if isinstance(states, dict):
                strings = {k: v for k, v in states.items() if isinstance(v, str)}
                self.result.errors += check_states(
                    self.doc, strings, f"$.scenarios[{i}].states"
                )

    # --- Warnings ---

    def _unknown(self, model, data, path, *extra_known):
        known = {f.alias or name for name, f in model.model_fields.items()} | set(extra_known)
        if not isinstance(data, dict):
            return
        for key in data:
            if key not in known:
                self._warn(f"{path}.{key}", f"unknown key '{key}' is ignored")

    def _unknown_in_list(self, collection, model, is_dc=lambda _: False):
        for i, element in _indexed(self.doc.get(collection)):
            path = f"$.{collection}[{i}]"
            self._unknown(model, element, path)
            if "phases" in element and is_dc(element):
                self._warn(f"{path}.phases", "unknown key 'phases' is ignored on a DC element")
            for key in ("capacity", "power"):
                if key in model.model_fields:
                    self._unknown(Bands, element.get(key), f"{path}.{key}")

    def _warn_unknown_keys(self):
        doc = self.doc
        self._unknown(Definition, doc, "$")
        self._unknown(Meta, doc.get("meta"), "$.meta")
        settings = doc.get("settings")
        self._unknown(Settings, settings, "$.settings")
        if isinstance(settings, dict):
            bands = settings.get("bands")
            self._unknown(BandSettings, bands, "$.settings.bands")
            if isinstance(bands, dict):
                for band in BandSettings.model_fields:
                    self._unknown(BandInfo, bands.get(band), f"$.settings.bands.{band}")
        self._unknown_in_list("sources", Source, lambda s: s.get("output") == "DC")
        self._unknown_in_list("buses", Bus, lambda b: b.get("type") == "DC")
        self._unknown_in_list("trus", Tru)
        self._unknown_in_list("contactors", Contactor)
        self._unknown_in_list("loads", Load)
        self._unknown_in_list("scenarios", Scenario)

    def _voltage(self, id_):
        node = self.buses.get(id_) or self.sources.get(id_) or {}
        volts = node.get("voltage")
        return volts if isinstance(volts, (int, float)) else None

    def _warn_voltage_mismatch(self):
        for i, contactor in self.contactors:
            a, b = _str(contactor.get("from")), _str(contactor.get("to"))
            if a not in self.node_ids or b not in self.node_ids or a in self.trus or b in self.trus:
                continue
            same_side = self._side(a, b) == self._side(b, a)
            volts = self._voltage(a), self._voltage(b)
            if same_side and None not in volts and volts[0] != volts[1]:
                self._warn(
                    f"$.contactors[{i}]",
                    f"contactor joins different voltages: '{a}' {volts[0]} V, "
                    f"'{b}' {volts[1]} V",
                )

    def _warn_unconnected(self):
        connected = set()
        for _, contactor in self.contactors:
            connected |= {_str(contactor.get("from")), _str(contactor.get("to"))}
        for i, source in _indexed(self.doc.get("sources")):
            if isinstance(source.get("id"), str) and source["id"] not in connected:
                self._warn(f"$.sources[{i}]", f"source '{source['id']}' has no contactor")
        reached = self._reachable()
        for i, bus in _indexed(self.doc.get("buses")):
            if isinstance(bus.get("id"), str) and bus["id"] not in reached:
                self._warn(f"$.buses[{i}]", f"bus '{bus['id']}' has no possible feed")

    def _reachable(self):
        """Nodes fed with every contactor closed and every source and TRU live."""
        forward = {}
        for _, contactor in self.contactors:
            a, b = _str(contactor.get("from")), _str(contactor.get("to"))
            if a is None or b is None:
                continue
            for near, far in ((a, b), (b, a)):
                tru = self.trus.get(far)
                if tru is not None and near != tru.get("input_bus"):
                    continue  # a TRU is entered only from its input bus
                tru = self.trus.get(near)
                if tru is not None and far != tru.get("output_bus"):
                    continue  # and left only to its output bus
                forward.setdefault(near, []).append(far)
        reached = set(self.sources)
        pending = list(reached)
        while pending:
            for node in forward.get(pending.pop(), ()):
                if node not in reached:
                    reached.add(node)
                    pending.append(node)
        return reached

    def _warn_no_essential_load(self):
        loads = self.doc.get("loads")
        if isinstance(loads, list) and not any(
            load.get("essential") is True for _, load in _indexed(loads)
        ):
            self._warn("$.loads", "no load is marked essential, so total power loss still passes")
