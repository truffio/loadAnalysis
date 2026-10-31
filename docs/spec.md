# Electrical Load Analysis (ELA) Tool — Specification

**Version:** 1.0 (initial build)
**Date:** 31 October 2026
**Reference methodology:** MIL-E-7016F, *Electric Load and Power Source Capacity, Aircraft, Analysis of* (civil counterpart: ASTM F2490)

---

## 1. Intent

When an aircraft's electrical generation and distribution system is designed, it must be shown that, in **every planned configuration** of the system (including failures such as an engine shutdown and loss of its generator), the available power is sufficient to supply the connected loads, so that the crew can deal with the emergency and return safely.

This tool performs that electrical load analysis. It is **generic**: it is not tied to one aircraft. The aircraft's electrical architecture, its loads and the scenarios to check are all read from a single JSON definition file.

The analysis is deliberately simple. It is **not** a time-domain or circuit simulation. It is a summation of power demand in three time bands, compared against the capacity of each source and distribution element, with a safety margin. (Conceptually, it could be done in a spreadsheet; the tool automates it, visualises it and runs it across all scenarios.)

The tool has two uses:

1. **Interactive exploration** — see the system drawn as a schematic, click components to fail them or open/close contactors, and immediately see what is energised and how loaded each bus is.
2. **Batch verification** — run every defined scenario automatically and report any that fail the continued safe flight criteria.

---

## 2. Scope

### In scope (this build)

- Load and validate a single JSON definition file (topology + loads + analysis settings + scenarios).
- Analysis engine: energisation, load summation per time band, propagation upstream (including TRU losses), capacity check with safety margin.
- Interactive schematic front end with automatic layout and point-and-click state changes.
- Batch run of all defined scenarios with a pass/fail report.
- Support for multiple definition files (any aircraft).

### Out of scope (possible follow-ups)

- Editing the topology or loads in the UI (the JSON file is edited by hand for now).
- Automatic reconfiguration logic (automatic bus transfers, load shedding). All configurations are static and planned in advance as scenarios.
- Battery endurance (amp-hour) checks.
- Flight-phase-dependent loads (loads are always on, as defined).
- Time-domain simulation of current/voltage.
- Display of individual loads or circuit breakers on the schematic.

---

## 3. Analysis method

### 3.1 Time bands

Every load and every capacity is defined in three time bands (MIL-E-7016F style):

| Band | Meaning |
|---|---|
| `transient` | Peak demand at switch-on / inrush |
| `short_term` | Demand over the first ~5 seconds (between peak and steady state) |
| `continuous` | Steady-state demand |

Typically `transient ≥ short_term ≥ continuous` for a load, but the tool must not enforce this.

### 3.2 Loads

- Each load is connected to exactly one bus, through a circuit breaker.
- Circuit breakers are **lossless** and are not displayed. They exist only implicitly as the load-to-bus link.
- Loads are **always on**. Whether a load draws power depends only on whether its bus is energised. If a bus is lost, every load on it is lost.
- Voltage is treated as constant (the bus nominal voltage).

### 3.3 Energisation

A component is **energised** if there is a path to it from an **operative source** through **closed contactors** and **energised converters**.

- Sources: engine generators, APU generator, emergency (RAT) generator, batteries.
- Contactors and bus ties pass power in both directions when closed, nothing when open.
- TRUs pass power **only from AC to DC**. A TRU is energised if its input AC bus is energised and its input contactor is closed.
- A failed source supplies nothing.

### 3.4 Demand and propagation

For each time band:

1. **Bus demand** = sum of the band's power for all loads on that bus (only if the bus is energised; loads on a crew-switched bus whose switch is off count as zero, see §4.9).
2. Demand flows **upstream** from each bus toward the source feeding it, through closed contactors/ties and TRUs.
3. Across a **TRU**, input demand = output demand ÷ efficiency. So the AC side always supplies more than the DC side consumes.
4. **Source demand** = total demand flowing back to it.

### 3.5 Source-feeding rules (static configurations)

Because configurations are static, normally each energised bus is fed by exactly one source. The engine applies these rules:

- **AC paralleling:** if two AC sources end up connected to the same island of buses through closed contactors/ties, this is flagged as a **configuration error** for that state/scenario (unsynchronised AC generators are not paralleled). The scenario fails with an explicit "AC sources paralleled" message.
- **DC sharing:** if a DC island is fed by more than one TRU, demand is shared between them in proportion to their continuous capacities.
- **Battery priority:** if a DC island contains a battery and any other energised DC source (a TRU or a DC RAT output), the battery is treated as not discharging (demand 0). The battery supplies only when it is the island's sole source.

### 3.6 Pass / fail criteria

For every element that has a capacity (sources, TRUs, buses, contactors/ties if rated) and for every time band:

```
demand × (1 + safety_margin) ≤ capacity
```

- `safety_margin` is set in the JSON file (e.g. `0.10` for 10%). A global value is required; individual elements may override it.
- Elements with no capacity defined are unconstrained (they are not checked).
- An element failing any band is **overloaded**.
- A configuration **passes** if no element is overloaded and there is no configuration error.

### 3.7 Electrical quantities shown

For each energised bus, the tool reports per time band:

- **Voltage** (V) — the bus nominal voltage.
- **Power** (W, shown as kW when ≥ 1000 W).
- **Current** (A):
  - DC: `I = P / V`
  - AC: per-phase current, `I = P / (phases × V_phase)`, with power factor assumed 1.0 (loads are given in watts). `phases` defaults to 3.

---

## 4. Electrical system components

All components have a unique `id` and a human-readable `name`. Components marked **clickable** can be changed in interactive mode.

### 4.1 Engine generators (AC)

- One per engine. Any number of engines is supported (typically 2 or 4, up to ~8, no hard limit).
- Attributes: `engine` (engine number), nominal voltage, phases, capacity per band.
- State: `operative` / `failed`. **Clickable** (failing a generator represents an engine shutdown or generator loss).

### 4.2 APU generator (AC)

- One per aircraft (support zero or one).
- Same attributes and states as an engine generator. **Clickable.**

### 4.3 Emergency generator (RAT-driven)

- Driven by the ram air turbine.
- Can have an AC output, a DC output, or both (each output is a separate source connection with its own capacity).
- An AC output may feed an AC bus and/or a TRU feeding a DC bus; a DC output feeds a DC bus directly.
- State: `available` (deployed and running) / `unavailable` (stowed or failed). **Clickable.** Default is `unavailable` unless a scenario says otherwise.

### 4.4 Batteries (DC)

- Nominal voltage (typically 24–28 V), capacity per band (power).
- No endurance check.
- State: `operative` / `failed`. **Clickable.**

### 4.5 AC bus bars

- Types (descriptive tag, used for layout and display): `main` (typically one per generator, e.g. AC BUS 1, AC BUS 2), `essential`, `emergency`, `other`.
- Attributes: nominal voltage (e.g. 115 V), phases, optional capacity per band.

### 4.6 DC bus bars

- Types: `main`, `essential`, `emergency` / `battery`, `other`.
- Attributes: nominal voltage (typically 28 V), optional capacity per band.

### 4.7 TRUs (transformer rectifier units)

- Convert AC to DC (typically 28 V).
- Attributes: input AC bus, output DC bus, `efficiency` (0 < η ≤ 1), output capacity per band.
- Power is one-way: AC → DC.
- State: `operative` / `failed`. **Clickable.**

### 4.8 Contactors and bus ties

- A contactor exists **everywhere a source connects to a bus**: generator → bus, APU generator → bus, RAT output → bus, battery → bus, TRU input and output.
- **Bus tie contactors** connect two buses together (e.g. AC BUS 1 ↔ AC ESS BUS).
- A contactor connects exactly two nodes. Optional capacity per band.
- State: `closed` / `open`. **Clickable.**

### 4.9 Crew-switched battery loads

- The loads on the battery-fed DC bus are switched on by the flight crew (otherwise they would drain the battery on the ground).
- Model: a bus may have `crew_switch: true`. Its switch state is `on` / `off`; when `off`, its loads draw nothing (the bus itself may still be energised).
- At the start of every simulation (interactive session or scenario), the switch is **on**, unless a scenario explicitly sets it off. **Clickable.**

### 4.10 Circuit breakers

- One per load, lossless, implicit, not displayed, not clickable.

---

## 5. Definition file (JSON)

A single file holds everything. Units: power in watts, voltage in volts, margins and efficiencies as decimals.

### 5.1 Structure

```json
{
  "meta": {
    "aircraft": "Generic Twin",
    "revision": "A",
    "description": "Twin-engine transport, 2 IDGs, APU gen, RAT, 3 TRUs, 1 battery"
  },
  "settings": {
    "safety_margin": 0.10,
    "bands": {
      "transient":  { "label": "Transient" },
      "short_term": { "label": "5 s", "duration_s": 5 },
      "continuous": { "label": "Continuous" }
    }
  },
  "sources": [
    { "id": "GEN1", "name": "Generator 1", "kind": "engine_generator", "engine": 1,
      "output": "AC", "voltage": 115, "phases": 3,
      "capacity": { "transient": 135000, "short_term": 112500, "continuous": 90000 },
      "default_state": "operative" },
    { "id": "APUGEN", "name": "APU Generator", "kind": "apu_generator",
      "output": "AC", "voltage": 115, "phases": 3,
      "capacity": { "transient": 135000, "short_term": 112500, "continuous": 90000 },
      "default_state": "operative" },
    { "id": "RAT_AC", "name": "RAT Generator (AC)", "kind": "emergency_generator",
      "output": "AC", "voltage": 115, "phases": 3,
      "capacity": { "transient": 15000, "short_term": 12000, "continuous": 10000 },
      "default_state": "unavailable" },
    { "id": "BAT", "name": "Main Battery", "kind": "battery",
      "output": "DC", "voltage": 28,
      "capacity": { "transient": 6000, "short_term": 4500, "continuous": 3000 },
      "default_state": "operative" }
  ],
  "buses": [
    { "id": "AC1", "name": "AC BUS 1", "type": "AC", "role": "main", "voltage": 115, "phases": 3 },
    { "id": "ACESS", "name": "AC ESS BUS", "type": "AC", "role": "essential", "voltage": 115, "phases": 3 },
    { "id": "DCBAT", "name": "DC BAT BUS", "type": "DC", "role": "battery", "voltage": 28,
      "crew_switch": true }
  ],
  "trus": [
    { "id": "TRU1", "name": "TRU 1", "input_bus": "AC1", "output_bus": "DC1",
      "efficiency": 0.85,
      "capacity": { "transient": 9000, "short_term": 7500, "continuous": 5600 },
      "default_state": "operative" }
  ],
  "contactors": [
    { "id": "GLC1", "name": "Gen 1 Line Contactor", "kind": "source", "from": "GEN1", "to": "AC1",
      "default_state": "closed" },
    { "id": "BTC1", "name": "Bus Tie AC1–ACESS", "kind": "bus_tie", "from": "AC1", "to": "ACESS",
      "default_state": "closed" },
    { "id": "TRU1_IN", "name": "TRU 1 Input", "kind": "tru", "from": "AC1", "to": "TRU1",
      "default_state": "closed" },
    { "id": "TRU1_OUT", "name": "TRU 1 Output", "kind": "tru", "from": "TRU1", "to": "DC1",
      "default_state": "closed" }
  ],
  "loads": [
    { "id": "L001", "name": "Galley oven 1", "bus": "AC1",
      "power": { "transient": 6000, "short_term": 5200, "continuous": 5000 } },
    { "id": "L002", "name": "Standby attitude indicator", "bus": "DCBAT",
      "power": { "transient": 80, "short_term": 60, "continuous": 45 } }
  ],
  "scenarios": [
    { "id": "S01", "name": "Normal — all sources operative",
      "description": "Both IDGs on line, APU off", 
      "states": { "APUGEN": "failed" } },
    { "id": "S02", "name": "Engine 1 shutdown",
      "states": { "GEN1": "failed", "APUGEN": "failed" } },
    { "id": "S03", "name": "Total AC generator loss — RAT deployed",
      "states": { "GEN1": "failed", "GEN2": "failed", "APUGEN": "failed", "RAT_AC": "available" } }
  ]
}
```

### 5.2 Rules

- Optional per-element `"safety_margin"` overrides the global value for that element.
- `capacity` is optional on buses and contactors; required on sources and TRUs.
- A scenario's `states` lists only the components that differ from their `default_state`. Anything not listed uses its default.
- Unknown keys are ignored with a warning; missing required keys, duplicate ids, dangling references (e.g. a load on a bus that doesn't exist), a TRU connected DC→AC, or a contactor between incompatible nodes (AC↔DC) are errors.
- The validator returns all errors at once, each with the JSON path and a readable message.

### 5.3 Sample file to deliver

Build a complete, realistic sample for a **generic twin-engine transport**: 2 engine generators, 1 APU generator, RAT with AC output, AC BUS 1/2, AC ESS, DC BUS 1/2, DC ESS, DC BAT bus (crew-switched), 3 TRUs (one feeding DC ESS), 1 battery, all source/TRU contactors and bus ties, ~40–60 loads with plausible figures, and 10–15 scenarios (normal, each single generator loss, APU-only, generator + APU loss, TRU failures, RAT-only emergency, battery-only). Include at least one scenario designed to fail (overload) to demonstrate the report.

---

## 6. Tool functionality

### 6.1 Definition management

- List definition files found in a `definitions/` folder; also allow uploading one from the browser.
- On load, validate (§5.2). Show errors clearly and do not open an invalid file.
- Switching definition files resets the interactive view.

### 6.2 Interactive mode

**Schematic**

- The system is drawn automatically, no coordinates in the JSON.
- Layered layout, top to bottom:
  1. Sources (engine generators in engine order, APU, RAT, battery)
  2. Source contactors
  3. AC main buses, then AC essential/emergency buses
  4. TRUs (with input/output contactors)
  5. DC main, essential, emergency/battery buses
- Bus tie contactors are drawn between the buses they connect, horizontally where possible.
- Minimise line crossings and clutter (e.g. layered/Sugiyama-style layout with barycentre ordering, orthogonal connectors). Must stay readable with up to ~50 displayed items on a laptop screen. Pan and zoom supported.
- Icons drawn in SVG (generator circle with "G", battery symbol, TRU box, contactor symbol shown open/closed, bus bars as thick horizontal bars). Any small library may be used if it helps, but none is required.
- Individual loads and circuit breakers are **not** drawn.

**Colours**

| State | Colour |
|---|---|
| Energised | Green |
| De-energised | Dark grey (still visible) |
| Overloaded (any band) | Amber |
| Failed source / TRU | Dark grey with a failure mark (e.g. ✕) |

Contactors show their open/closed state graphically, in addition to colour.

**Bus labels**

- Shown **only on energised buses**: voltage (V), current (A), power (W or kW).
- A band selector (Transient / 5 s / Continuous, default Continuous) chooses which band's values are displayed.
- If a bus or element is overloaded in a band other than the one displayed, it is still amber, and the label indicates which band(s) failed.
- Hover (or tap) on any element shows a tooltip with all three bands: demand, demand with margin, capacity, and remaining margin.
- Sources and TRUs also show their load (and % of capacity) when energised.

**Interaction**

- Click a generator / APU generator / battery / TRU → toggle operative ↔ failed.
- Click the RAT → toggle available ↔ unavailable.
- Click any contactor or bus tie → toggle closed ↔ open.
- Click a crew-switched bus's switch → toggle on ↔ off.
- Every click recomputes the analysis and redraws instantly.
- **Reset** button returns all components to their default states.
- **Load scenario** dropdown applies a scenario's states to the schematic, so a batch result can be inspected visually.
- A status panel shows overall PASS / FAIL for the current configuration and lists every overload and configuration error (element, band, demand with margin, capacity).

### 6.3 Batch mode

- **Run all scenarios** button (front end) and a command-line equivalent, e.g. `python -m ela batch definitions/generic_twin.json`.
- Results table: scenario id, name, PASS/FAIL, worst element and band, smallest remaining margin, number of overloads, configuration errors.
- Expand a row to see every failing element and band.
- Click a row to open that scenario in interactive mode.
- Export results to CSV and JSON.
- CLI exit code is non-zero if any scenario fails (usable in automated checks).

---

## 7. Architecture and tech stack

### 7.1 Back end — Python

- Python 3.12+, **FastAPI**, **Pydantic** (definition schema and validation), Uvicorn.
- The analysis engine is a pure Python package with no web dependencies, so it can be tested and run from the CLI independently.
- The schematic layout is computed in the back end and returned as coordinates, keeping the front end simple.
- Tests with **pytest**: energisation, TRU efficiency, bus ties, source failures, AC paralleling detection, DC sharing, battery priority, safety margin, crew switch, validation errors, and every scenario in the sample file.

Suggested layout:

```
ela/
  model.py        # Pydantic schema
  validate.py
  engine.py       # energisation, propagation, checks
  layout.py       # schematic layout
  batch.py
  cli.py
  api.py          # FastAPI app
web/
  index.html
  app.js          # ES modules, no build step
  schematic.js
  batch.js
  styles.css
definitions/
  generic_twin.json
tests/
```

### 7.2 API (indicative)

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/definitions` | List available definition files |
| POST | `/api/definitions` | Upload a definition file (validated) |
| GET | `/api/definitions/{id}` | Definition + computed layout |
| POST | `/api/definitions/{id}/analyse` | Body: component states. Returns per-element energisation, demand, capacity, overloads, errors |
| POST | `/api/definitions/{id}/batch` | Run all scenarios, return results |
| GET | `/api/definitions/{id}/batch/export?format=csv\|json` | Export last batch results |

### 7.3 Front end — vanilla JavaScript

- Plain HTML, CSS and JavaScript (ES modules). No framework, no build step.
- Schematic rendered as **SVG**.
- Served as static files by the FastAPI app, so the whole tool starts with one command (e.g. `uvicorn ela.api:app`).

---

## 8. Deliverables

1. Analysis engine with unit tests.
2. FastAPI back end and CLI.
3. Vanilla JS front end (interactive and batch modes).
4. Sample definition file for a generic twin (§5.3).
5. README: installation, running, JSON format reference, and how to add a new aircraft.

---

## 9. Assumptions to confirm

These were not explicitly decided and are set to sensible defaults above. Adjust as needed before the build.

1. **AC current** is per-phase, power factor 1.0, 3-phase by default (§3.7).
2. **Source-feeding rules**: AC paralleling is an error; DC TRUs share in proportion to capacity; the battery supplies only when it is the sole source on its island (§3.5).
3. **Essential loads**: pass/fail is capacity-based only. Optionally, loads could carry an `essential` flag so a scenario also fails if any essential load is unpowered, which would directly check "minimum equipment for safe flight remains powered."
4. **Band selector** defaults to Continuous for the displayed bus values; amber shows an overload in any band.
5. **RAT default state** is unavailable (stowed) unless a scenario deploys it.
