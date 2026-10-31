# Test cases

Verification cases for `docs/requirements.md`, written independently of the requirements author. L2 cases verify one component: unit tests with pytest, FastAPI TestClient (httpx) for C-API, subprocess for C-CLI, and Playwright (Chromium, sync API, run from pytest against a uvicorn server started by a fixture) for C-WEBINT and C-WEBBAT. L1 cases are black-box through the CLI, API or browser. L0 cases are end-to-end acceptance on the sample definition and state its required properties, since its figures are written later. Each test function carries `@pytest.mark.tc("TC-...")`, one to one or many to one. All expected figures are hand-worked from the requirements and rulings, never taken from an implementation. Fixtures below are built from this text alone.

## Fixtures

### Conventions

- **Band triples.** `a/b/c` means `transient`/`short_term`/`continuous`, in W unless stated. One figure means the same value in all three bands.
- **Defaults for every fixture**, unless the fixture says otherwise. `meta` is `{"aircraft": "Test", "revision": "A"}`. `settings` is `{"safety_margin": 0.10}`. `name` equals `id`. `scenarios` is `[]`. `Gn` is `kind` `engine_generator`, `engine` n, `output` AC, `voltage` 115, `phases` 3, `default_state` `operative`. `APU` is `kind` `apu_generator`, `output` AC, `voltage` 115, `phases` 3, `default_state` `operative`. `RAT_AC` is `kind` `emergency_generator`, `output` AC, `voltage` 115, `phases` 3, `default_state` `unavailable`. `RAT_DC` is the same with `output` DC, `voltage` 28 and no `phases`. `BAT*` is `kind` `battery`, `output` DC, `voltage` 28, `default_state` `operative`. An AC bus is `type` AC, `role` main, `voltage` 115, `phases` 3. A DC bus is `type` DC, `role` main, `voltage` 28. Buses and contactors have no `capacity`. A TRU has `default_state` `operative`. A source or TRU with no stated capacity has cap 10000, a TRU with no stated efficiency has η 0.85, and a fixture listing no loads has `loads: []`.
- **Contactors.** `C_X` is a `source` contactor from source X to the stated bus, `default_state` `closed`. A TRU named X always has `X_IN` (`tru`, from `input_bus` to X) and `X_OUT` (`tru`, from X to `output_bus`), both `closed`. `Tab` is a `bus_tie`, `default_state` `closed` unless marked open.
- **Topology notation.** `G1 → AC1` means G1 joined to AC1 by `C_G1`. `TRU1: AC1 → DC1, η 0.85, cap x/y/z` gives `input_bus`, `output_bus`, `efficiency` and `capacity`. `L on AC1: x/y/z` is a load with id L on bus AC1.
- **Mutations.** `M: $.path = value` changes a copy of the fixture before the test. `M: del $.path` removes the key. Everything else is unchanged.
- **Tolerance.** Figures match within 1e-6 W, A or %, unless stated "exactly". Displayed values match after the display rounding.
- **Negative numbers.** All program output, including the UI, CLI and exports, writes a negative number with ASCII hyphen-minus (U+002D). Hand working in this file may use −, but quoted output uses `-`.
- **Warnings.** Under DD-025 a definition with no essential load always carries a warning at `$.loads`. Cases therefore check the warning they are about. A case asserting an empty warning list uses a fixture with one essential load.

### Names used by the cases

Under DD-024 these names are binding interface requirements, restated in L2-VAL-031, L2-ENG-068, L2-ENG-069, L2-BAT-010, L2-LAY-019, L2-API-025, L2-API-026, L2-WIN-053 and L2-WBT-013. The tests use them directly.

- **Validator.** `validate(doc)` in `ela.validate` gives `.errors`, `.warnings` (each with `path`, `message`) and `.definition` (`None` if rejected).
- **Engine.** `analyse(defn, states)` in `ela.engine` gives `R`, with `R.verdict`, `R.overloads` (entries `element`, `band`, `demand_with_margin`, `capacity`), `R.config_errors`, `R.unpowered` (entries `id`, `name`, `bus`), `R.warnings`, `R.worst` (`element`, `band`, `margin_pct`), `R.checked` (element ids) and `R.islands`. `R.el[id]` is the element record: `.state`, `.energised`, and per band `.demand`, `.with_margin`, `.capacity`, `.margin_w`, `.margin_pct`. A bus adds `.own`, `.voltage`, `.current`. A source or TRU adds `.load_pct`. A TRU adds `.input`, `.output`. `D(X)` is shorthand for `R.el[X].demand` as a triple.
- **Batch.** `run_batch(defn)` in `ela.batch` gives one result per scenario with `scenario_id`, `name`, `result`, `worst_element`, `worst_band`, `smallest_margin_pct`, `overloads`, `configuration_errors`, `unpowered_essential`, the detail lists `overload_details`, `error_messages`, `unpowered_details`, and `warnings`.
- **Layout.** `layout(defn)` in `ela.layout` gives `items` (`id`, `kind`, `x`, `y`, `width`, `height`, with `x`, `y` the top-left corner) and `connectors` (`from`, `to`, `points`).
- **HTTP.** The analyse body is `{"states": {...}}`, and uploads are multipart with field `file`.
- **Browser hooks.** `[data-id="X"]` is the SVG group of element X, with `data-state` holding its state. `[data-label="X"]` is its value label. A crew switch is the element `<bus>_switch`. The others are `#definition-select`, `#definition-upload`, `#band-select`, `#scenario-select`, `#reset`, `#status-verdict`, `#status-list`, `#tooltip`, `#message`, `#warnings`, `#schematic`, `#run-batch`, `#batch-table`, `#export-csv`, `#export-json`.

### Harness fixtures

- **H-DEFS.** A temporary folder set as `ELA_DEFINITIONS_DIR`, holding the fixtures a case names as `<fixture id in lower case>.json`, for example `fx_single.json`. It always holds a copy of `generic_twin.json`.
- **H-CLIENT.** FastAPI TestClient on `ela.api.app`, with H-DEFS set.
- **H-SERVER.** `uvicorn ela.api:app` started as a subprocess on a free port, with H-DEFS set, stopped at teardown.
- **H-PAGE.** A Playwright Chromium page at a 1366 × 768 px viewport, open on H-SERVER, with an `analyse` request log. Every browser case opens the named definition through `#definition-select`.
- **H-NOSOCKET.** A subprocess wrapper that replaces `socket.socket` with a class raising on `connect`, `bind` and `listen`, then runs the CLI through `runpy`.

### Small definitions

**FX-SINGLE.** G1 cap 20000/15000/10000 → AC1. TRU1: AC1 → DC1, η 0.85, cap 6000/5000/4000. LA on AC1: 2000/1500/1000. LD on DC1: 1700/1360/850.

| Quantity | Working | T / S / C |
| --- | --- | --- |
| DC1 demand, TRU1 output, `TRU1_OUT` | LD | 1700 / 1360 / 850 |
| TRU1 input, `TRU1_IN` | output ÷ 0.85 | 2000 / 1600 / 1000 |
| AC1 own | LA | 2000 / 1500 / 1000 |
| AC1 demand, G1, `C_G1` | own + input | 4000 / 3100 / 2000 |
| G1 with margin | × 1.10 | 4400 / 3410 / 2200 |
| G1 remaining | capacity − with margin | 15600 / 11590 / 7800 W, 78 / 77.27 / 78 % |
| TRU1 with margin | output × 1.10 | 1870 / 1496 / 935 |
| TRU1 remaining | capacity − with margin | 4130 / 3504 / 3065 W, 68.83 / 70.08 / 76.63 % |

**FX-SINGLE-E.** FX-SINGLE with LA `essential: true`. Valid, with an empty warning list.

**FX-CHAIN.** G1 cap 20000 → AC1. Ties T12 (AC1–AC2), T23 (AC2–AC3). L1 on AC1: 100. L2 on AC2: 200. L3 on AC3: 300. By node balance T23 = 300, T12 = 200 + 300 = 500, AC1 demand = G1 = 100 + 500 = 600, AC2 demand = 500, AC3 demand = 300.

**FX-RING.** G1 cap 20000 → AC1. Ties T12 (AC1–AC2), T13 (AC1–AC3), T23 (AC2–AC3). L1 on AC1: 100. L2 on AC2: 200. L3 on AC3: 300. Breadth-first from G1 reaches AC1, then AC2 by T12 and AC3 by T13, so T23 is left out. T12 = 200, T13 = 300, T23 = 0, AC1 demand = G1 = 600. Scenario M1 `{}`.

**FX-SRCBRIDGE.** G1 cap 10000 with two source contactors, C1A to AC1 and C1B to AC2. G2 cap 10000, `default_state` `failed` → AC1. LA on AC1: 300. LB on AC2: 500. With G2 failed, C1A = 300, C1B = 500, G1 = 800.

**FX-THROUGH.** G1 cap 20000 → AC1. Tie T12 (AC1–AC2). TRU1: AC1 → DC1, η 0.85, cap 6000/5000/4000. LA1 on AC1: 1200/1100/1000. LA2 on AC2: 700/600/500. LD on DC1: 1700/1360/850. TRU1 input 2000/1600/1000. AC1 demand 1200 + 2000 + 700 = 3900, 1100 + 1600 + 600 = 3300, 1000 + 1000 + 500 = 2500. AC1 own 1200/1100/1000.

**FX-TWO-TRU.** G1 cap 50000 → AC1. G2 cap 50000 → AC2. TRU1: AC1 → DC1, η 0.80, cap 9000/7000/6000. TRU2: AC2 → DC1, η 0.75, cap 3600/3200/3000. LD on DC1: 1800/1350/900. Continuous ratio 6000 : 3000 = 2 : 1, so TRU1 output 1200/900/600 and TRU2 output 600/450/300. Inputs 1500/1125/750 and 800/600/400.

**FX-TIE-DC.** As FX-TWO-TRU, but TRU2 outputs to DC2, with tie T_DC (DC1–DC2), LD1 on DC1: 800, LD2 on DC2: 100. Island demand 900, TRU1 600, TRU2 300.

**FX-TIE-EQ.** G1 cap 5000 → AC1. G2 cap 5000 → AC2. TRU_A: AC1 → DCA, η 0.80, cap 1000. TRU_B: AC2 → DCB, η 0.80, cap 1000. Tie T_DC (DCA–DCB). LDA on DCA: 300. LDB on DCB: 100.

**FX-BAT.** G1 cap 5000 → AC1. TRU1: AC1 → DC1, η 0.85, cap 3000. BAT cap 6000/4500/3000 → DCB. Tie T_B (DC1–DCB). LD on DC1: 340. LB on DCB: 510. Island demand 850.

**FX-BAT2.** BAT1 cap 6000/4500/3000 → DC1. BAT2 cap 2000/1500/1000 → DC1. L on DC1: 800.

**FX-TRU-RAT.** G1 cap 20000 → AC1. TRU1: AC1 → DC1, η 0.80, cap 9000/7000/6000. RAT_DC `output` DC, `voltage` 28, cap 1000/3000/3000, `default_state` `available` → DC1. BAT cap 6000/4500/3000 → DC1. L on DC1: 900.

**FX-RAT.** RAT_AC `output` AC, `voltage` 115, `phases` 3, cap 5000 → ACE (role `emergency`). RAT_DC `output` DC, `voltage` 28, cap 3000 → DCE (role `emergency`). LAE on ACE: 4500. LDE on DCE: 2700. Both outputs at 90 % of capacity, sum 7200 W.

**FX-PAR.** G1 cap 1000 → AC1. G2 cap 1000 → AC2. Tie T12 (AC1–AC2). TRU1: AC1 → DC1, η 0.80, cap 1000. LA1 on AC1: 1000. LA2 on AC2: 3000. LD on DC1: 400. TRU1 input 400 ÷ 0.80 = 500. AC1 demand 1000 + 500 = 1500, AC2 demand 3000.

**FX-ESS.** G1 cap 10000 → AC1. BAT cap 1000 → DCS (`crew_switch` true). LE1 on AC1: 100, essential. LE2 on AC1: 200, essential. LN on AC1: 300. LE3 on DCS: 50, essential.

**FX-CREW.** BAT cap 6000/4500/3000 → DCS (role `battery`, `crew_switch` true). Tie T_S (DCS–DCX). LS on DCS: 200/150/100. LX on DCX: 300/250/200.

**FX-MARGIN.** G1 cap 1100 → AC1. L1 on AC1: 1000. 1000 × 1.10 = 1100, exactly at the limit.

**FX-OVERRIDE.** G1 cap 1250, `safety_margin` 0.25 → AC1, which has capacity 1100. L1 on AC1: 1000. G1 with margin 1250, AC1 with margin 1100.

**FX-ZERO.** G1 cap 1000 → AC1, which has capacity 0. L1 on AC1: 1.

**FX-WORST.** `safety_margin` 0. G1, G2, G3 cap 1000 on untied AC1, AC2, AC3 with L1 600, L2 880, L3 750, giving remaining margin 40 %, 12 %, 25 %.

**FX-EMPTY.** G1 cap 1000 → AC1. G2 cap 1000, no contactor. Tie T12 (AC1–AC2), open. TRU1: AC1 → DC1, η 0.85, cap 1000. No loads.

**FX-ENG(n).** For k = 1 to n: Gk cap 10000, `engine` k → ACk, Lk on ACk: 1000. Buses are not tied.

**FX-4ENG.** FX-ENG(4) plus TRU1: AC1 → DC1, η 0.85, cap 5000, LD on DC1: 425, and scenarios S1 `{}`, S2 `{"G1": "failed"}`.

**FX-APU.** FX-SINGLE plus APU (`kind` `apu_generator`, AC, 115 V, cap 10000, `operative`) joined to AC1 by `C_APU`, `default_state` `open`.

**FX-ALLKINDS.** G1 cap 20000 → AC1. APU as in FX-APU. RAT_AC cap 5000 → ACE (role `essential`), `C_RAT_AC` `open`. RAT_DC cap 3000 → DC1, `C_RAT_DC` `open`. BAT cap 6000/4500/3000 → DCB (role `battery`, `crew_switch` true). Tie T1E (AC1–ACE). Tie T_DC (DC1–DCB). TRU1: AC1 → DC1, η 0.85, cap 5000. LA on AC1: 500. LE on ACE: 100. LD on DC1: 170. LB on DCB: 34.

**FX-BATCH.** G1, G2 cap 3000/2500/2000 → AC1, AC2. Ties T12 (AC1–AC2) open, capacity 1500; T13 (AC1–AC3) open, capacity 1500. LA1 on AC1: 1000/900/800, essential. LA2 on AC2: 1000/900/800. LX on AC3: 2000/1000/1200. Scenarios:

| Id | Name | `states` |
| --- | --- | --- |
| S1 | Normal | `{}` |
| S2 | G1 lost | `{"G1": "failed", "T12": "closed"}` |
| S3 | Paralleled | `{"T12": "closed"}` |
| S4 | Dark | `{"G1": "failed", "G2": "failed"}` |
| S5 | `Overload, tie to "AC3" — T13` | `{"T13": "closed"}` |

Hand results. S1: G1 = G2 = 1000/900/800, margin 1900 W 63.33 %, 1510 W 60.4 %, 1120 W 56 %, tied at 56 % so the lowest id wins. S2: G2 = 2000/1800/1600, with margin 2200/1980/1760, margin 26.67 %, 20.8 %, 12 %. T12 = 1000/900/800, margin 26.67 %, 34 %, 41.33 %. S3: paralleled, so nothing is checked, as both AC buses are unrated. S4: dead, LA1 unpowered. S5: G1 = 1000 + 2000 = 3000, 900 + 1000 = 1900, 800 + 1200 = 2000, with margin 3300/2090/2200 against 3000/2500/2000, so transient and continuous fail, at −10 %. T13 = 2000/1000/1200, with margin 2200/1100/1320 against 1500, so transient fails, at (1500 − 2200) ÷ 1500 = −46.67 %.

| Id | result | worst_element | worst_band | smallest_margin_pct | overloads | configuration_errors | unpowered_essential |
| --- | --- | --- | --- | --- | --- | --- | --- |
| S1 | PASS | G1 | continuous | 56.00 | 0 | 0 | 0 |
| S2 | PASS | G2 | continuous | 12.00 | 0 | 0 | 0 |
| S3 | FAIL | null | null | null | 0 | 1 | 0 |
| S4 | FAIL | null | null | null | 0 | 0 | 1 |
| S5 | FAIL | T13 | transient | -46.67 | 3 | 0 | 0 |

**FX-ALLPASS.** FX-BATCH with only scenarios S1 and S2.

**FX-BATCH12.** FX-BATCH with 12 scenarios, ids in this file order `Z01, A02, M03, B04, Y05, C06, X07, D08, W09, E10, V11, F12`, whose `states` cycle through S1 to S5.

**FX-ROLES.** G1, G2 → AC1, AC2. APU → AC1, `C_APU` open. RAT_AC → ACM. BAT → DCB. Buses AC1, AC2 (main), ACE (essential), ACM (emergency), ACO (other), DC1 (main), DCE (essential), DCM (emergency), DCB (battery), DCO (other). Ties T12 (AC1–AC2) open, T1E (AC1–ACE), TEM (ACE–ACM) open, TEO (ACE–ACO), T_DE (DC1–DCE), T_EM (DCE–DCM), T_EB (DCE–DCB), T_EO (DCE–DCO). TRU1: AC1 → DC1, η 0.85, cap 5000. All sources cap 10000.

**FX-REVERSE.** Sources declared in the order BAT, RAT_AC, APU, G2, G1, each with one contactor to its own bus.

**FX-CHAINS.** G1 → AC1, TRU1: AC1 → DC1. G2 → AC2, TRU2: AC2 → DC2. All arrays declared in reverse order, with G2 first.

**FX-CROSS.** Buses declared in the order AC2, AC1, DC1, DC2. G1 → AC1, G2 → AC2. TRU_A: AC1 → DC2. TRU_B: AC2 → DC1. In definition order the two TRU chains cross.

**FX-50.** For k = 1 to 6: Gk → ACk, TRUk: ACk → DCk. Ties T12, T23, T34, T45, T56 between adjacent AC buses, all open. BAT → DC6, which has `crew_switch` true. Count: 6 × 7 (G, C_G, AC, TRU_IN, TRU, TRU_OUT, DC) = 42, plus 5 ties = 47, plus BAT and C_BAT = 49, plus 1 crew switch = 50 items.

**FX-COLOURS.** G1 cap 100000 → AC1. G2 cap 100000 → AC2, which has capacity 100. G3 cap 100000, `default_state` `failed` → AC3. RAT_AC cap 5000 → ACE. Tie T13 (AC1–AC3), open. TRU1: AC1 → DC1, η 0.85, cap 5000. TRU2: AC3 → DC2, η 0.85, cap 5000. TRU3: AC1 → DC3, η 0.85, cap 5000, `default_state` `failed`. LA1 on AC1: 1000. LA2 on AC2: 1000/50/50. LD on DC1: 850. States shown: AC1 energised, AC2 overloaded in transient only (1100 > 100, 55 ≤ 100), AC3 de-energised, G3 and TRU3 failed, TRU2 de-energised but operative, RAT_AC unavailable.

**FX-TRAN.** G1, G2, G3 cap 100000 → AC1, AC2, AC3. G4 cap 1000 → AC4. AC1, AC2 capacity 1000. `C_G3` capacity 100. LT1 on AC1: 1000/500/100 (1100/550/110, fails transient). LT2 on AC2: 1000/950/100 (1100/1045/110, fails transient and short_term). LT3 on AC3: 500/50/50 (`C_G3` 550/55/55, fails transient). LT4 on AC4: 1000/1000/500 (G4 1100/1100/550, fails transient and short_term).

**FX-DISPLAY.** Five untied chains: G1 → AC1 with 999 W, G2 → AC2 with 1000 W, G3 → AC3 with 12340 W, G4 cap 90000 → AC4 with 45000 W, G5 → AC5 with 999.6 W. Sources other than G4 have cap 100000.

### Faulty documents

Each of these is a mutation of FX-SINGLE unless stated.

**FX-THREEERR.** A mutation of FX-SINGLE-E, with exactly three independent errors and no warning. `M: del $.loads[0].power.short_term`. `M: $.trus[0].efficiency = 1.5`. `M: $.loads[1].bus = "NOBUS"`. Expected paths `$.loads[0].power`, `$.trus[0].efficiency`, `$.loads[1].bus`.

**FX-FIVE.** `M: del $.meta.revision`. `M: $.loads[1].id = "LA"`. `M: $.loads[0].bus = "NOBUS"`. Swap `$.trus[0].input_bus` and `output_bus`. Add a `bus_tie` `TBAD` from AC1 to DC1.

**FX-MANY.** FX-THREEERR plus these seven further faults on the same document. `M: del $.settings.safety_margin`. `M: $.loads[0].power.transient = -1`. `M: $.buses[0].voltage = 0`. Add a third load with id `LA`. Add a `bus_tie` `TBAD` from AC1 to DC1. Add scenario `{"id": "S1", "name": "n", "states": {"GHOST": "failed", "G1": "closed"}}`.

**FX-WARN.** `M: $.zzz = 1`, an unknown top-level key.

**FX-MALFORMED.** These 20 parsed documents: (1) `[]`, (2) `{}`, (3) `null`, (4) `42`, (5) `"text"`, (6) `true`, (7) `[{}]`, (8) `{"meta": 1}`, (9) `{"sources": {}}`, and mutations of FX-SINGLE: (10) `$.sources = "x"`, (11) `$.buses = [1, 2]`, (12) `$.loads = [null]`, (13) `$.contactors = [{}]`, (14) `$.settings = []`, (15) `$.scenarios = {"a": 1}`, (16) `$.loads[0].power = 5`, (17) `$.sources[0].capacity = "big"`, (18) `$.scenarios = [{"id": "S", "name": "n", "states": []}]`, (19) `$.trus[0].efficiency = null`, (20) every top-level value set to `null`.

### The sample

**FX-SAMPLE.** `definitions/generic_twin.json` as delivered. Its figures are not known here, so cases use only properties required by the L2-SMP requirements. Engine generators are found by `kind` and `engine`, buses by the names in L2-SMP-003, never by assumed ids. A scenario's state for a component is its `states` entry, otherwise the component's default. Designed-to-fail scenarios are those with `designed to fail` in `description`. The recorded hand calculation is `tests/data/generic_twin_expected.json`, delivered under L2-SMP-027.

## Verification matrix

| ID | Verifies | Level | Method |
| --- | --- | --- | --- |
| TC-MOD-001 | L2-MOD-001 | L2 | Test |
| TC-MOD-002 | L2-MOD-002, L2-MOD-003 | L2 | Test |
| TC-MOD-003 | L2-MOD-004 | L2 | Test |
| TC-MOD-004 | L2-MOD-005 | L2 | Test |
| TC-MOD-005 | L2-MOD-006 | L2 | Test |
| TC-MOD-006 | L2-MOD-007, L2-MOD-008 | L2 | Test |
| TC-MOD-007 | L2-MOD-009 | L2 | Test |
| TC-MOD-008 | L2-MOD-010 | L2 | Test |
| TC-MOD-009 | L2-MOD-011, L2-MOD-013 | L2 | Test |
| TC-MOD-010 | L2-MOD-012 | L2 | Test |
| TC-MOD-011 | L2-MOD-014 | L2 | Test |
| TC-MOD-012 | L2-MOD-015 | L2 | Test |
| TC-MOD-013 | L2-MOD-016 | L2 | Test |
| TC-MOD-014 | L2-MOD-017, L2-MOD-018 | L2 | Test |
| TC-MOD-015 | L2-MOD-019 | L2 | Test |
| TC-MOD-016 | L2-MOD-020, L2-MOD-026 | L2 | Test |
| TC-MOD-017 | L2-MOD-021 | L2 | Test |
| TC-MOD-018 | L2-MOD-022 | L2 | Test |
| TC-MOD-019 | L2-MOD-023 | L2 | Test |
| TC-MOD-020 | L2-MOD-024 | L2 | Test |
| TC-MOD-021 | L2-MOD-025 | L2 | Test |
| TC-MOD-022 | L2-MOD-027, L2-MOD-028 | L2 | Test |
| TC-MOD-023 | L2-MOD-029, L2-MOD-030 | L2 | Test |
| TC-MOD-024 | L2-MOD-031, L2-MOD-032 | L2 | Test |
| TC-MOD-025 | L2-MOD-033 | L2 | Test |
| TC-VAL-001 | L2-VAL-001 | L2 | Test |
| TC-VAL-002 | L2-VAL-002 | L2 | Test |
| TC-VAL-003 | L2-VAL-002 | L2 | Test |
| TC-VAL-004 | L2-VAL-003 | L2 | Test |
| TC-VAL-005 | L2-VAL-004 | L2 | Test |
| TC-VAL-006 | L2-VAL-005 | L2 | Test |
| TC-VAL-007 | L2-VAL-006 | L2 | Test |
| TC-VAL-008 | L2-VAL-007 | L2 | Test |
| TC-VAL-009 | L2-VAL-008 | L2 | Test |
| TC-VAL-010 | L2-VAL-009 | L2 | Test |
| TC-VAL-011 | L2-VAL-010, L2-VAL-011 | L2 | Test |
| TC-VAL-012 | L2-VAL-012 | L2 | Test |
| TC-VAL-013 | L2-VAL-013 | L2 | Test |
| TC-VAL-014 | L2-VAL-014 | L2 | Test |
| TC-VAL-015 | L2-VAL-015 | L2 | Test |
| TC-VAL-016 | L2-VAL-016, L2-VAL-017 | L2 | Test |
| TC-VAL-017 | L2-VAL-018 | L2 | Test |
| TC-VAL-018 | L2-VAL-019 | L2 | Test |
| TC-VAL-019 | L2-VAL-020 | L2 | Test |
| TC-VAL-020 | L2-VAL-021, L2-VAL-022 | L2 | Test |
| TC-VAL-021 | L2-VAL-023 | L2 | Test |
| TC-VAL-022 | L2-VAL-023 | L2 | Test |
| TC-VAL-023 | L2-VAL-024 | L2 | Test |
| TC-VAL-024 | L2-VAL-025 | L2 | Test |
| TC-VAL-025 | L2-VAL-026 | L2 | Test |
| TC-VAL-026 | L2-VAL-027 | L2 | Test |
| TC-VAL-027 | L2-VAL-028 | L2 | Test |
| TC-VAL-028 | L2-VAL-029, L2-VAL-030 | L2 | Test |
| TC-VAL-029 | L2-VAL-020 | L2 | Test |
| TC-VAL-030 | L2-VAL-033 | L2 | Test |
| TC-VAL-031 | L2-VAL-032 | L2 | Test |
| TC-VAL-032 | L2-VAL-031 | L2 | Test |
| TC-ENG-001 | L2-ENG-001 | L2 | Test |
| TC-ENG-002 | L2-ENG-002 | L2 | Test |
| TC-ENG-003 | L2-ENG-003 | L2 | Test |
| TC-ENG-073 | L2-ENG-003 | L2 | Test |
| TC-ENG-004 | L2-ENG-004 | L2 | Test |
| TC-ENG-005 | L2-ENG-005, L2-ENG-006 | L2 | Test |
| TC-ENG-006 | L2-ENG-007 | L2 | Test |
| TC-ENG-007 | L2-ENG-008 | L2 | Test |
| TC-ENG-008 | L2-ENG-009 | L2 | Test |
| TC-ENG-009 | L2-ENG-010 | L2 | Test |
| TC-ENG-010 | L2-ENG-011, L2-ENG-015 | L2 | Test |
| TC-ENG-011 | L2-ENG-012 | L2 | Test |
| TC-ENG-012 | L2-ENG-013 | L2 | Test |
| TC-ENG-013 | L2-ENG-014 | L2 | Test |
| TC-ENG-014 | L2-ENG-016, L2-ENG-019 | L2 | Test |
| TC-ENG-015 | L2-ENG-016 | L2 | Test |
| TC-ENG-016 | L2-ENG-017, L2-ENG-018 | L2 | Test |
| TC-ENG-017 | L2-ENG-017, L2-ENG-046 | L2 | Test |
| TC-ENG-018 | L2-ENG-020 | L2 | Test |
| TC-ENG-019 | L2-ENG-021 | L2 | Test |
| TC-ENG-020 | L2-ENG-022 | L2 | Test |
| TC-ENG-021 | L2-ENG-021, L2-ENG-022 | L2 | Test |
| TC-ENG-022 | L2-ENG-023, L2-ENG-024 | L2 | Test |
| TC-ENG-023 | L2-ENG-023 | L2 | Test |
| TC-ENG-074 | L2-ENG-023 | L2 | Test |
| TC-ENG-024 | L2-ENG-025 | L2 | Test |
| TC-ENG-075 | L2-ENG-025 | L2 | Test |
| TC-ENG-025 | L2-ENG-023, L2-ENG-025 | L2 | Test |
| TC-ENG-026 | L2-ENG-026 | L2 | Test |
| TC-ENG-027 | L2-ENG-027 | L2 | Test |
| TC-ENG-028 | L2-ENG-028 | L2 | Test |
| TC-ENG-029 | L2-ENG-028 | L2 | Test |
| TC-ENG-030 | L2-ENG-028 | L2 | Test |
| TC-ENG-031 | L2-ENG-029, L2-ENG-030 | L2 | Test |
| TC-ENG-032 | L2-ENG-031 | L2 | Test |
| TC-ENG-033 | L2-ENG-032 | L2 | Test |
| TC-ENG-034 | L2-ENG-033 | L2 | Test |
| TC-ENG-035 | L2-ENG-033 | L2 | Test |
| TC-ENG-036 | L2-ENG-033 | L2 | Test |
| TC-ENG-037 | L2-ENG-034 | L2 | Test |
| TC-ENG-038 | L2-ENG-035, L2-ENG-037 | L2 | Test |
| TC-ENG-039 | L2-ENG-036 | L2 | Test |
| TC-ENG-040 | L2-ENG-038 | L2 | Test |
| TC-ENG-041 | L2-ENG-039 | L2 | Test |
| TC-ENG-042 | L2-ENG-040 | L2 | Test |
| TC-ENG-043 | L2-ENG-041 | L2 | Test |
| TC-ENG-044 | L2-ENG-041 | L2 | Test |
| TC-ENG-045 | L2-ENG-042 | L2 | Test |
| TC-ENG-046 | L2-ENG-043 | L2 | Test |
| TC-ENG-047 | L2-ENG-044 | L2 | Test |
| TC-ENG-048 | L2-ENG-045 | L2 | Test |
| TC-ENG-049 | L2-ENG-046 | L2 | Test |
| TC-ENG-050 | L2-ENG-047 | L2 | Test |
| TC-ENG-051 | L2-ENG-048 | L2 | Test |
| TC-ENG-052 | L2-ENG-049 | L2 | Test |
| TC-ENG-053 | L2-ENG-049 | L2 | Test |
| TC-ENG-054 | L2-ENG-050 | L2 | Test |
| TC-ENG-055 | L2-ENG-051 | L2 | Test |
| TC-ENG-056 | L2-ENG-052 | L2 | Test |
| TC-ENG-057 | L2-ENG-052 | L2 | Test |
| TC-ENG-058 | L2-ENG-053 | L2 | Test |
| TC-ENG-059 | L2-ENG-054 | L2 | Test |
| TC-ENG-060 | L2-ENG-055 | L2 | Test |
| TC-ENG-061 | L2-ENG-056 | L2 | Test |
| TC-ENG-062 | L2-ENG-057 | L2 | Test |
| TC-ENG-063 | L2-ENG-058 | L2 | Test |
| TC-ENG-064 | L2-ENG-059 | L2 | Test |
| TC-ENG-065 | L2-ENG-060 | L2 | Test |
| TC-ENG-076 | L2-ENG-069 | L2 | Test |
| TC-ENG-077 | L2-ENG-068 | L2 | Test |
| TC-ENG-066 | L2-ENG-061 | L2 | Test |
| TC-ENG-067 | L2-ENG-062 | L2 | Test |
| TC-ENG-068 | L2-ENG-063 | L2 | Test |
| TC-ENG-069 | L2-ENG-064 | L2 | Test |
| TC-ENG-070 | L2-ENG-065 | L2 | Test |
| TC-ENG-071 | L2-ENG-066 | L2 | Test |
| TC-ENG-072 | L2-ENG-067 | L2 | Test |
| TC-SMP-001 | L2-SMP-001 | L2 | Test |
| TC-SMP-002 | L2-SMP-002 | L2 | Test |
| TC-SMP-003 | L2-SMP-003, L2-SMP-004 | L2 | Test |
| TC-SMP-004 | L2-SMP-005 | L2 | Test |
| TC-SMP-005 | L2-SMP-006 | L2 | Test |
| TC-SMP-006 | L2-SMP-007, L2-SMP-008, L2-SMP-012 | L2 | Test |
| TC-SMP-007 | L2-SMP-009 | L2 | Test |
| TC-SMP-008 | L2-SMP-010, L2-SMP-011 | L2 | Test |
| TC-SMP-009 | L2-SMP-013 | L2 | Test |
| TC-SMP-010 | L2-SMP-014 | L2 | Test |
| TC-SMP-011 | L2-SMP-015 | L2 | Test |
| TC-SMP-012 | L2-SMP-016 | L2 | Test |
| TC-SMP-013 | L2-SMP-017 | L2 | Test |
| TC-SMP-014 | L2-SMP-018 | L2 | Test |
| TC-SMP-015 | L2-SMP-019 | L2 | Test |
| TC-SMP-016 | L2-SMP-020 | L2 | Test |
| TC-SMP-017 | L2-SMP-021 | L2 | Test |
| TC-SMP-018 | L2-SMP-022 | L2 | Test |
| TC-SMP-019 | L2-SMP-023, L2-SMP-024 | L2 | Test |
| TC-SMP-020 | L2-SMP-025 | L2 | Test |
| TC-SMP-021 | L2-SMP-026 | L2 | Test |
| TC-SMP-022 | L2-SMP-027 | L2 | Test |
| TC-BAT-001 | L2-BAT-001 | L2 | Test |
| TC-BAT-002 | L2-BAT-002 | L2 | Test |
| TC-BAT-003 | L2-BAT-003 | L2 | Test |
| TC-BAT-004 | L2-BAT-004 | L2 | Test |
| TC-BAT-005 | L2-BAT-005 | L2 | Test |
| TC-BAT-006 | L2-BAT-006 | L2 | Test |
| TC-BAT-011 | L2-BAT-010 | L2 | Test |
| TC-BAT-007 | L2-BAT-007 | L2 | Test |
| TC-BAT-008 | L2-BAT-007 | L2 | Test |
| TC-BAT-009 | L2-BAT-008 | L2 | Test |
| TC-BAT-010 | L2-BAT-009 | L2 | Test |
| TC-CLI-001 | L2-CLI-001 | L2 | Test |
| TC-CLI-002 | L2-CLI-002 | L2 | Test |
| TC-CLI-003 | L2-CLI-003, L2-CLI-004 | L2 | Test |
| TC-CLI-004 | L2-CLI-005 | L2 | Test |
| TC-CLI-005 | L2-CLI-006 | L2 | Test |
| TC-CLI-006 | L2-CLI-007 | L2 | Test |
| TC-CLI-007 | L2-CLI-008 | L2 | Test |
| TC-CLI-008 | L2-CLI-009 | L2 | Test |
| TC-CLI-009 | L2-CLI-010 | L2 | Test |
| TC-CLI-010 | L2-CLI-011 | L2 | Test |
| TC-CLI-011 | L2-CLI-012, L2-CLI-013 | L2 | Test |
| TC-LAY-001 | L2-LAY-001 | L2 | Test |
| TC-LAY-017 | L2-LAY-019 | L2 | Test |
| TC-LAY-002 | L2-LAY-002 | L2 | Test |
| TC-LAY-003 | L2-LAY-003 | L2 | Test |
| TC-LAY-004 | L2-LAY-004 | L2 | Test |
| TC-LAY-005 | L2-LAY-005 | L2 | Test |
| TC-LAY-006 | L2-LAY-006 | L2 | Test |
| TC-LAY-007 | L2-LAY-007 | L2 | Test |
| TC-LAY-008 | L2-LAY-008 | L2 | Test |
| TC-LAY-009 | L2-LAY-009 | L2 | Test |
| TC-LAY-010 | L2-LAY-010, L2-LAY-011 | L2 | Test |
| TC-LAY-011 | L2-LAY-012 | L2 | Test |
| TC-LAY-012 | L2-LAY-013 | L2 | Test |
| TC-LAY-013 | L2-LAY-014 | L2 | Test |
| TC-LAY-014 | L2-LAY-015 | L2 | Test |
| TC-LAY-015 | L2-LAY-016, L2-LAY-017 | L2 | Test |
| TC-LAY-016 | L2-LAY-018 | L2 | Test |
| TC-LAY-018 | L2-LAY-018 | L2 | Test |
| TC-API-001 | L2-API-001 | L2 | Test |
| TC-API-002 | L2-API-002 | L2 | Test |
| TC-API-003 | L2-API-003 | L2 | Test |
| TC-API-004 | L2-API-004 | L2 | Test |
| TC-API-005 | L2-API-004 | L2 | Test |
| TC-API-006 | L2-API-005, L2-API-006 | L2 | Test |
| TC-API-022 | L2-API-026 | L2 | Test |
| TC-API-023 | L2-API-025 | L2 | Test |
| TC-API-007 | L2-API-007 | L2 | Test |
| TC-API-008 | L2-API-008 | L2 | Test |
| TC-API-009 | L2-API-009 | L2 | Test |
| TC-API-010 | L2-API-010 | L2 | Test |
| TC-API-011 | L2-API-011 | L2 | Test |
| TC-API-012 | L2-API-012 | L2 | Test |
| TC-API-013 | L2-API-013 | L2 | Test |
| TC-API-014 | L2-API-014 | L2 | Test |
| TC-API-015 | L2-API-015 | L2 | Test |
| TC-API-016 | L2-API-016 | L2 | Test |
| TC-API-017 | L2-API-017, L2-API-018 | L2 | Test |
| TC-API-018 | L2-API-019, L2-API-020 | L2 | Test |
| TC-API-019 | L2-API-021, L2-API-022 | L2 | Test |
| TC-API-020 | L2-API-023 | L2 | Test |
| TC-API-021 | L2-API-024 | L2 | Test |
| TC-WIN-001 | L2-WIN-001 | L2 | Test |
| TC-WIN-002 | L2-WIN-002 | L2 | Test |
| TC-WIN-003 | L2-WIN-003 | L2 | Test |
| TC-WIN-004 | L2-WIN-004 | L2 | Test |
| TC-WIN-005 | L2-WIN-005 | L2 | Test |
| TC-WIN-006 | L2-WIN-006 | L2 | Test |
| TC-WIN-007 | L2-WIN-007 | L2 | Test |
| TC-WIN-008 | L2-WIN-008 | L2 | Test |
| TC-WIN-009 | L2-WIN-009 | L2 | Test |
| TC-WIN-010 | L2-WIN-010 | L2 | Test |
| TC-WIN-011 | L2-WIN-011 | L2 | Test |
| TC-WIN-012 | L2-WIN-012 | L2 | Test |
| TC-WIN-013 | L2-WIN-013, L2-WIN-014 | L2 | Test |
| TC-WIN-014 | L2-WIN-015 | L2 | Test |
| TC-WIN-015 | L2-WIN-016 | L2 | Test |
| TC-WIN-016 | L2-WIN-017 | L2 | Test |
| TC-WIN-017 | L2-WIN-018 | L2 | Test |
| TC-WIN-018 | L2-WIN-019 | L2 | Test |
| TC-WIN-019 | L2-WIN-020 | L2 | Test |
| TC-WIN-020 | L2-WIN-021 | L2 | Test |
| TC-WIN-021 | L2-WIN-022, L2-WIN-023 | L2 | Test |
| TC-WIN-022 | L2-WIN-024 | L2 | Test |
| TC-WIN-023 | L2-WIN-025 | L2 | Test |
| TC-WIN-024 | L2-WIN-026 | L2 | Test |
| TC-WIN-025 | L2-WIN-027 | L2 | Test |
| TC-WIN-026 | L2-WIN-028, L2-WIN-029 | L2 | Test |
| TC-WIN-027 | L2-WIN-030 | L2 | Test |
| TC-WIN-028 | L2-WIN-031 | L2 | Test |
| TC-WIN-029 | L2-WIN-032, L2-WIN-033, L2-WIN-034 | L2 | Test |
| TC-WIN-030 | L2-WIN-035 | L2 | Test |
| TC-WIN-031 | L2-WIN-036 | L2 | Test |
| TC-WIN-032 | L2-WIN-037 | L2 | Test |
| TC-WIN-033 | L2-WIN-038 | L2 | Test |
| TC-WIN-034 | L2-WIN-039 | L2 | Test |
| TC-WIN-035 | L2-WIN-040 | L2 | Test |
| TC-WIN-036 | L2-WIN-041, L2-WIN-042 | L2 | Test |
| TC-WIN-046 | L2-WIN-042 | L2 | Test |
| TC-WIN-037 | L2-WIN-043, L2-WIN-044 | L2 | Test |
| TC-WIN-038 | L2-WIN-045 | L2 | Test |
| TC-WIN-047 | L2-WIN-045 | L2 | Test |
| TC-WIN-039 | L2-WIN-046 | L2 | Test |
| TC-WIN-040 | L2-WIN-047 | L2 | Test |
| TC-WIN-041 | L2-WIN-048 | L2 | Inspection |
| TC-WIN-042 | L2-WIN-049 | L2 | Inspection |
| TC-WIN-043 | L2-WIN-050 | L2 | Test |
| TC-WIN-044 | L2-WIN-051 | L2 | Test |
| TC-WIN-045 | L2-WIN-052 | L2 | Test |
| TC-WIN-048 | L2-WIN-053 | L2 | Test |
| TC-WBT-001 | L2-WBT-001 | L2 | Test |
| TC-WBT-002 | L2-WBT-002 | L2 | Test |
| TC-WBT-003 | L2-WBT-003 | L2 | Test |
| TC-WBT-004 | L2-WBT-004 | L2 | Test |
| TC-WBT-005 | L2-WBT-005 | L2 | Test |
| TC-WBT-006 | L2-WBT-006 | L2 | Test |
| TC-WBT-007 | L2-WBT-007 | L2 | Test |
| TC-WBT-008 | L2-WBT-008 | L2 | Test |
| TC-WBT-009 | L2-WBT-009 | L2 | Test |
| TC-WBT-010 | L2-WBT-010, L2-WBT-011 | L2 | Test |
| TC-WBT-011 | L2-WBT-012 | L2 | Test |
| TC-WBT-012 | L2-WBT-013 | L2 | Test |
| TC-DOC-001 | L2-DOC-001 | L2 | Test |
| TC-DOC-002 | L2-DOC-002 | L2 | Test |
| TC-DOC-003 | L2-DOC-003 | L2 | Test |
| TC-DOC-004 | L2-DOC-004 | L2 | Test |
| TC-DOC-005 | L2-DOC-005, L2-DOC-006 | L2 | Test |
| TC-DOC-006 | L2-DOC-007 | L2 | Test |
| TC-SYS-001 | L1-ELA-001 | L1 | Test |
| TC-SYS-002 | L1-ELA-002 | L1 | Test |
| TC-SYS-003 | L1-ELA-003, L1-ELA-004 | L1 | Test |
| TC-SYS-004 | L1-ELA-005 | L1 | Test |
| TC-SYS-005 | L1-ELA-006, L1-ELA-008 | L1 | Test |
| TC-SYS-006 | L1-ELA-007 | L1 | Test |
| TC-SYS-007 | L1-ELA-009 | L1 | Test |
| TC-SYS-008 | L1-ELA-010 | L1 | Test |
| TC-SYS-009 | L1-ELA-011, L1-ELA-012 | L1 | Test |
| TC-SYS-010 | L1-ELA-013, L1-ELA-014, L1-ELA-015 | L1 | Test |
| TC-SYS-011 | L1-ELA-016, L1-ELA-017 | L1 | Test |
| TC-SYS-012 | L1-ELA-018, L1-ELA-019 | L1 | Test |
| TC-SYS-013 | L1-ELA-020 | L1 | Test |
| TC-SYS-014 | L1-ELA-021 | L1 | Test |
| TC-SYS-015 | L1-ELA-022 | L1 | Test |
| TC-SYS-016 | L1-ELA-023 | L1 | Test |
| TC-SYS-017 | L1-ELA-024, L1-ELA-025, L1-ELA-026 | L1 | Test |
| TC-SYS-018 | L1-ELA-027, L1-ELA-028 | L1 | Test |
| TC-SYS-019 | L1-ELA-029, L1-ELA-030 | L1 | Test |
| TC-SYS-020 | L1-ELA-031 | L1 | Test |
| TC-SYS-021 | L1-ELA-032, L1-ELA-034 | L1 | Test |
| TC-SYS-022 | L1-ELA-033, L1-ELA-035 | L1 | Test |
| TC-SYS-023 | L1-ELA-036 | L1 | Test |
| TC-SYS-024 | L1-ELA-037, L1-ELA-038 | L1 | Test |
| TC-SYS-025 | L1-ELA-039 | L1 | Test |
| TC-SYS-026 | L1-ELA-040, L1-ELA-042 | L1 | Test |
| TC-SYS-027 | L1-ELA-041 | L1 | Test |
| TC-SYS-028 | L1-ELA-043 | L1 | Test |
| TC-SYS-029 | L1-ELA-044, L1-ELA-045 | L1 | Test |
| TC-SYS-030 | L1-ELA-046, L1-ELA-047 | L1 | Test |
| TC-SYS-031 | L1-ELA-048 | L1 | Test |
| TC-SYS-032 | L1-ELA-049 | L1 | Test |
| TC-SYS-033 | L1-ELA-051 | L1 | Test |
| TC-SYS-045 | L1-ELA-050 | L1 | Test |
| TC-SYS-034 | L1-ELA-052 | L1 | Test |
| TC-SYS-035 | L1-ELA-053 | L1 | Test |
| TC-SYS-036 | L1-ELA-054, L1-ELA-055 | L1 | Test |
| TC-SYS-037 | L1-ELA-056, L1-ELA-057 | L1 | Test |
| TC-SYS-038 | L1-ELA-058 | L1 | Test |
| TC-SYS-039 | L1-ELA-059 | L1 | Test |
| TC-SYS-040 | L1-ELA-060, L1-ELA-061 | L1 | Test |
| TC-SYS-041 | L1-ELA-062 | L1 | Inspection |
| TC-SYS-042 | L1-ELA-063 | L1 | Test |
| TC-SYS-043 | L1-ELA-064 | L1 | Test |
| TC-SYS-044 | L1-ELA-065, L1-ELA-066 | L1 | Test |
| TC-ACC-001 | L0-ELA-001 | L0 | Test |
| TC-ACC-002 | L0-ELA-002 | L0 | Test |
| TC-ACC-003 | L0-ELA-003 | L0 | Test |
| TC-ACC-004 | L0-ELA-004 | L0 | Test |
| TC-ACC-005 | L0-ELA-005 | L0 | Test |
| TC-ACC-006 | L0-ELA-006 | L0 | Test |
| TC-ACC-007 | L0-ELA-007 | L0 | Test |
| TC-ACC-008 | L0-ELA-008 | L0 | Test |
| TC-ACC-009 | L0-ELA-009 | L0 | Test |

## Test cases

### C-MODEL

#### TC-MOD-001 — Top-level keys are required

- **Fixture:** FX-SINGLE
- **Steps:** Remove each of `meta`, `settings`, `sources`, `buses`, `trus`, `contactors`, `loads`, `scenarios` in turn and validate. Then validate the unmodified fixture, and a copy with `trus` empty and TRU1's two contactors removed.
- **Expected:** Each removal is rejected with an error at `$` naming that key. The unmodified fixture and the copy with an empty `trus` list are accepted.

#### TC-MOD-002 — Meta keys, required and optional

- **Fixture:** FX-SINGLE
- **Steps:** Remove `meta.aircraft`, then `meta.revision`. Separately set `meta.description` to `"x"`, then remove it.
- **Expected:** The first two are rejected. With and without `meta.description` the fixture is accepted with no unknown-key warning.

#### TC-MOD-003 — Values are held with no unit conversion

- **Fixture:** FX-SINGLE. M: `$.sources[0].capacity.transient = 135000`, `$.sources[0].voltage = 115`, `$.settings.safety_margin = 0.10`, `$.trus[0].efficiency = 0.85`
- **Steps:** Parse and read the values back from the model.
- **Expected:** Exactly 135000, 115, 0.10 and 0.85.

#### TC-MOD-004 — Global safety margin is required

- **Fixture:** FX-SINGLE
- **Steps:** Remove `settings.safety_margin`. Then set it to `true`, `"0.10"`, NaN, then `0.10`.
- **Expected:** The first is rejected with an error at `$.settings` naming `safety_margin`. `true`, `"0.10"` and NaN are each rejected. `0.10` is accepted.

#### TC-MOD-005 — Power and capacity need all three bands

- **Fixture:** FX-SINGLE
- **Steps:** For each of the 3 bands, remove it from `$.loads[0].power`, then from `$.sources[0].capacity`.
- **Expected:** All 6 mutations are rejected. The unmodified fixture is accepted.

#### TC-MOD-006 — Band labels and duration_s are optional

- **Fixture:** FX-SINGLE
- **Steps:** Parse with no `settings.bands`. Parse with `settings.bands.transient = {"label": "Peak"}` and the other two band entries absent. Compare `analyse(defn, {})` with and without `settings.bands.short_term = {"label": "5 s", "duration_s": 5}`.
- **Expected:** First: labels `Transient`, `5 s`, `Continuous`. Second: `Peak`, `5 s`, `Continuous`. Third: no unknown-key warning with `duration_s`, and the two results are equal.

#### TC-MOD-007 — Every element needs id and name

- **Fixture:** FX-SINGLE
- **Steps:** Remove `id`, then `name`, from one element of each of `sources`, `buses`, `trus`, `contactors`, `loads`.
- **Expected:** All 10 mutations give at least one error at that element's path naming the key.

#### TC-MOD-008 — Source kinds

- **Fixture:** FX-ALLKINDS
- **Steps:** Validate as is, which uses all 4 `kind` values. Then `M: $.sources[0].kind = "fuel_cell"`.
- **Expected:** The first is accepted. The second is rejected at `$.sources[0].kind`.

#### TC-MOD-009 — Source attributes, with RAT outputs as separate entries

- **Fixture:** FX-RAT with both outputs, and FX-SINGLE
- **Steps:** On FX-SINGLE remove `output`, `voltage`, `capacity` in turn from G1. Parse FX-RAT and read both sources.
- **Expected:** Each removal is rejected. FX-RAT parses as 2 sources, with `output` AC and DC, capacities 5000 and 3000, and independent `default_state` values.

#### TC-MOD-010 — Engine number is required only on engine generators

- **Fixture:** FX-APU
- **Steps:** `M: del $.sources[0].engine`. Separately validate the APU source, which has no `engine`. Also try `M: $.sources[0].engine = 1.5`.
- **Expected:** The first and third are rejected. The unmodified FX-APU is accepted.

#### TC-MOD-011 — default_state on generators and batteries

- **Fixture:** FX-ALLKINDS
- **Steps:** `M: del` G1 `default_state`. `M:` BAT `default_state = "failed"`. `M:` APU `default_state = "available"`.
- **Expected:** Rejected, accepted, rejected.

#### TC-MOD-012 — Emergency generator default state

- **Fixture:** FX-RAT
- **Steps:** Parse with `default_state` absent on RAT_AC. Parse with `operative`. Parse with `available`, then analyse with `{}`.
- **Expected:** `unavailable`. Rejected. `available` and honoured, with ACE energised.

#### TC-MOD-013 — Phases default to 3

- **Fixture:** FX-SINGLE
- **Steps:** `M: del` `phases` on AC1. Then `M:` `phases = 1`. Then `M: del` `phases` on G1. Then `M:` DC1 gains `phases` 3.
- **Expected:** AC1 parses with 3, then 1. G1 parses with 3. DC1 gets one unknown-key warning naming `phases`.

#### TC-MOD-014 — Bus type and role values

- **Fixture:** FX-ROLES
- **Steps:** Remove `type`, `role`, `voltage` in turn from AC1. `M:` AC1 `type = "HVDC"`, `role = "battery"`, then `role = "spare"`. `M:` DC1 `role = "spare"`.
- **Expected:** All are rejected. Unmodified FX-ROLES, holding every listed role on its bus type, is accepted.

#### TC-MOD-015 — Capacity is optional on buses and contactors

- **Fixture:** FX-SINGLE
- **Steps:** Parse as is. Then add a full `capacity` to AC1 and to `C_G1`.
- **Expected:** Capacity is absent in the first case and present in the second, with an empty error list in both.

#### TC-MOD-016 — Optional booleans crew_switch and essential

- **Fixture:** FX-ESS
- **Steps:** Parse and read `crew_switch` on AC1 and DCS, and `essential` on LN and LE1.
- **Expected:** False and true, and false and true.

#### TC-MOD-017 — TRU keys

- **Fixture:** FX-SINGLE
- **Steps:** Remove `input_bus`, `output_bus`, `efficiency`, `capacity`, `default_state` in turn from TRU1. Then `M: $.trus[0].default_state = "closed"`.
- **Expected:** All 6 mutations are rejected.

#### TC-MOD-018 — Contactor keys

- **Fixture:** FX-SINGLE
- **Steps:** Remove `kind`, `from`, `to`, `default_state` in turn from `C_G1`. Set `to` to `["AC1", "DC1"]`. Set `default_state` to `on`. Separately swap `from` and `to` on `TRU1_IN`.
- **Expected:** The first 6 mutations are rejected. The swap is accepted, as a `tru` contactor's role comes from the bus it joins.

#### TC-MOD-019 — A source connects only through a contactor

- **Fixture:** FX-EMPTY. M: G2 gains `"bus": "AC2"`
- **Steps:** Validate and analyse with `{}`.
- **Expected:** One unknown-key warning at the path of G2's `bus`. AC2 stays de-energised.

#### TC-MOD-020 — safety_margin accepted on each element kind

- **Fixture:** FX-SINGLE
- **Steps:** Set `safety_margin` 0.25 on G1, TRU1, AC1 and `C_G1`.
- **Expected:** No unknown-key warning, and each model holds 0.25.

#### TC-MOD-021 — Load bus and power

- **Fixture:** FX-SINGLE
- **Steps:** Remove `bus`, then `power`, from LA. Set `bus` to `["AC1", "DC1"]`.
- **Expected:** All 3 mutations are rejected.

#### TC-MOD-022 — Scenario keys

- **Fixture:** FX-SINGLE with scenario `{"id": "S1", "name": "n", "states": {}}`
- **Steps:** Remove `id`, `name`, `states` in turn. Add `description`, then remove it.
- **Expected:** The 3 removals are rejected. With and without `description` it is accepted with no unknown-key warning, and empty `states` is accepted.

#### TC-MOD-023 — No coordinate or circuit breaker keys

- **Fixture:** FX-SINGLE
- **Steps:** Read the model's generated JSON schema. Then `M:` AC1 gains `"x": 10`.
- **Expected:** No property named `x`, `y`, `position` or `coordinates`, and no property or definition name containing `breaker`. The mutation gives one unknown-key warning naming `x`.

#### TC-MOD-024 — No endurance or flight-phase keys

- **Fixture:** FX-BAT, FX-SINGLE
- **Steps:** `M:` BAT gains `amp_hours` 40. `M:` LA gains `flight_phase` `cruise`. Compare each `analyse(defn, {})` with the unmodified result.
- **Expected:** One unknown-key warning in each case, and results equal to the unmodified ones.

#### TC-MOD-025 — Pydantic schema module

- **Fixture:** None
- **Steps:** Import `ela.model`.
- **Expected:** `ela/model.py` exists and its definition model is a subclass of `pydantic.BaseModel`.

### C-VALID

#### TC-VAL-001 — Malformed documents return errors and raise nothing

- **Fixture:** FX-MALFORMED
- **Steps:** Call `validate` on each of the 20 documents.
- **Expected:** Each returns a non-empty error list and raises nothing.

#### TC-VAL-002 — Five seeded faults are reported in one call

- **Fixture:** FX-FIVE
- **Steps:** Call `validate` once.
- **Expected:** At least one error for each of the 5 faults, at `$.meta`, at the repeated load's id, at `$.loads[0].bus`, at `$.trus[0]` input and output paths, and at `TBAD`.

#### TC-VAL-003 — One definition holding ten errors reports them together

- **Fixture:** FX-MANY
- **Steps:** Call `validate` once.
- **Expected:** At least 10 errors with paths covering all 10 faults, including `$.settings`, `$.loads[0].power.transient`, `$.loads[0].power`, `$.buses[0].voltage`, `$.scenarios[0].states.GHOST` and `$.scenarios[0].states.G1`. `.definition` is `None`.

#### TC-VAL-004 — Errors and warnings carry a rooted path and message

- **Fixture:** FX-SINGLE plus 2 extra loads on AC1, the fourth load being `M: $.loads[3].bus = "NOBUS"`. Then FX-WARN.
- **Steps:** Validate both.
- **Expected:** First: error path exactly `$.loads[3].bus`, with `NOBUS` in the message. Second: a warning at exactly `$.zzz`, with a non-empty message.

#### TC-VAL-005 — A definition is returned only when there are no errors

- **Fixture:** FX-THREEERR, FX-WARN
- **Steps:** Validate both.
- **Expected:** FX-THREEERR gives `.definition` `None`. FX-WARN gives a definition, an empty error list and the `$.zzz` warning.

#### TC-VAL-006 — Validator module

- **Fixture:** None
- **Steps:** Import `ela.validate`.
- **Expected:** `ela/validate.py` exists and exposes the entry point.

#### TC-VAL-007 — Every validator condition has a test

- **Fixture:** None
- **Steps:** Collect `pytest tests --collect-only -m "not meta"`. Map test marks to cases and cases to requirements. Separately run that selection in a subprocess.
- **Expected:** Each of L2-VAL-007 to L2-VAL-030, L2-VAL-032 and L2-VAL-033 has at least one collected test, and the selection passes. The meta marker stops this case running itself.

#### TC-VAL-008 — One missing key gives one error at the parent path

- **Fixture:** FX-ALLKINDS with no scenarios referencing its ids
- **Steps:** Parametrise over each required key of each collection, plus `meta` and `settings` keys. Remove it and validate.
- **Expected:** For each key other than `id`: exactly one error, at the path of the parent object, naming the key. For each `id`: at least one such error, and any others only for references it breaks.

#### TC-VAL-009 — Wrong types and values outside the enumeration

- **Fixture:** FX-SINGLE
- **Steps:** Apply in turn: `$.trus[0].efficiency = "0.85"` (a numeric string, which lax parsing would coerce), `$.sources[0].kind = "fuel_cell"`, `$.settings.safety_margin = true`, `$.buses[0].crew_switch = "yes"`, `$.loads[0].power.transient = NaN`, `$.loads[0].power.transient = Infinity`.
- **Expected:** Each gives exactly one error at that key's path.

#### TC-VAL-010 — Duplicate ids across collections

- **Fixture:** FX-SINGLE
- **Steps:** `M:` TRU1 `id` = `AC1`, updating its references. Separately add two scenarios with id `S1`. Separately add a scenario with id `AC1`.
- **Expected:** One error for the bus and TRU pair. One error for the repeated scenario id. No error for a scenario sharing a bus id.

#### TC-VAL-011 — Missing band and missing capacity

- **Fixture:** FX-SINGLE
- **Steps:** `M: del $.loads[0].power.short_term`. Separately remove `capacity` from G1 and TRU1. Separately add then remove `capacity` on AC1 and `C_G1`.
- **Expected:** One error at `$.loads[0].power` naming `short_term`. Exactly 2 errors for the source and TRU. None for the bus and contactor.

#### TC-VAL-012 — Negative power and capacity

- **Fixture:** FX-SINGLE
- **Steps:** `M: $.loads[0].power.transient = -1`. Then `= 0`. Then `M: $.sources[0].capacity.continuous = -1`.
- **Expected:** One error, none, one error.

#### TC-VAL-013 — Band ordering is not enforced

- **Fixture:** FX-SINGLE-E. M: `$.loads[0].power = {"transient": 10, "short_term": 20, "continuous": 30}`, `$.sources[0].capacity = {"transient": 5000, "short_term": 20000, "continuous": 30000}`
- **Steps:** Validate.
- **Expected:** Empty error list and empty warning list.

#### TC-VAL-014 — Efficiency limits

- **Fixture:** FX-SINGLE
- **Steps:** Set `$.trus[0].efficiency` to 0, −0.1, 1.01, then 1.0 and 0.01.
- **Expected:** One error each for the first three. None for the last two, so 1.0 is included and 0 is excluded.

#### TC-VAL-015 — Value ranges

- **Fixture:** FX-SINGLE
- **Steps:** Set `$.buses[0].voltage = 0`, `$.sources[0].voltage = 0`, `$.buses[0].phases = 0`, `$.settings.safety_margin = -0.1`, `$.sources[0].safety_margin = -0.1`, then `$.settings.safety_margin = 0`.
- **Expected:** One error each for the first 5, including the per-element margin. None for margin 0.

#### TC-VAL-016 — One APU and one generator per engine

- **Fixture:** FX-SINGLE, FX-APU, FX-ENG(8)
- **Steps:** Validate FX-SINGLE (no APU) and FX-APU (one APU). Validate FX-APU with a second APU source and contactor. Validate FX-ENG(8), then with `M: $.sources[1].engine = 1`.
- **Expected:** No error, no error, one error. No error on engines 1 to 8, then one error.

#### TC-VAL-017 — Dangling references

- **Fixture:** FX-SINGLE
- **Steps:** Put `NOBUS` in `loads[0].bus`, `trus[0].input_bus`, `trus[0].output_bus`, `contactors[0].from`, `contactors[0].to`. Separately set `contactors[0].to` to the load id `LA`.
- **Expected:** At least one error at each of the 5 paths. A contactor end naming a load is also an error, because a load is not a node.

#### TC-VAL-018 — Reversed TRU

- **Fixture:** FX-SINGLE
- **Steps:** Swap `input_bus` and `output_bus` on TRU1, leaving contactors as they are. Validate the unswapped fixture too.
- **Expected:** Errors at both paths. None on the unswapped fixture.

#### TC-VAL-019 — AC to DC contactors

- **Fixture:** FX-BAT
- **Steps:** Add `bus_tie` TBAD (AC1–DC1). Separately `M:` `C_BAT` `to = "AC1"`. Validate the unmodified fixture.
- **Expected:** One error at TBAD. One error at `C_BAT`. None on the unmodified fixture's TRU contactors.

#### TC-VAL-020 — Contactor endpoints must suit its kind and differ

- **Fixture:** FX-SINGLE
- **Steps:** Add `bus_tie` X1 from G1 to AC1. Separately add `tru` X2 from AC1 to AC1b, with AC1b an extra AC bus. Separately add `source` X3 from AC1 to AC1b. Separately add `bus_tie` X4 from AC1 to AC1.
- **Expected:** One error for each, at that contactor.

#### TC-VAL-021 — TRU contactor count

- **Fixture:** FX-SINGLE
- **Steps:** (a) Remove `TRU1_IN`. (b) Add a second `tru` contactor from TRU1 to DC1. (c) Add a second `tru` contactor from TRU1 to DC2, a new DC bus. (d) Add a second input contactor from AC1.
- **Expected:** At least one error naming TRU1 in each.

#### TC-VAL-022 — RAT feeds a TRU only through a dedicated bus

- **Fixture:** FX-RAT without RAT_DC. M: TRU2 added with `TRU2_IN` from ACE, output DCE. Then a second copy where `TRU2_IN` is `from` RAT_AC.
- **Steps:** Validate both.
- **Expected:** The first gives no error. The second gives exactly one error, at `TRU2_IN`, reported once for L2-VAL-021 and L2-VAL-023 together.

#### TC-VAL-023 — Unknown states key

- **Fixture:** FX-ESS plus scenario S with `states` `{"GHOST": "failed", "LE1": "failed", "AC1": "off"}`
- **Steps:** Validate.
- **Expected:** Exactly 3 errors at `$.scenarios[0].states.GHOST`, `.LE1` and `.AC1`.

#### TC-VAL-024 — Unknown or cross-family state values

- **Fixture:** FX-ALLKINDS
- **Steps:** Add one scenario per entry. Valid: G1, TRU1, BAT, APU `operative` and `failed`; RAT_AC `available` and `unavailable`; T1E `closed` and `open`; DCB `on` and `off`. Invalid: G1 `closed`, RAT_AC `operative`, T1E `on`, DCB `closed`, G1 `broken`.
- **Expected:** No error for each valid entry. One error at the key's path for each of the 5 invalid entries.

#### TC-VAL-025 — The states check is one shared callable

- **Fixture:** FX-SINGLE
- **Steps:** Call the shared check with `{"GHOST": "failed", "G1": "closed"}`. Put the same object in a scenario and validate.
- **Expected:** The callable returns 2 errors. Scenario validation returns the same 2 errors, with the scenario path prefix.

#### TC-VAL-026 — Unknown keys warn and do not fail

- **Fixture:** FX-WARN. M: AC1 gains `"foo": 1`
- **Steps:** Validate.
- **Expected:** Exactly 2 unknown-key warnings, naming `zzz` and `foo`, and an empty error list.

#### TC-VAL-027 — Voltage mismatch across a contactor warns

- **Fixture:** FX-CHAIN. M: AC2 `voltage = 200`
- **Steps:** Validate. Then, on FX-SINGLE, `M:` G1 `voltage = 200`.
- **Expected:** First: one voltage warning for each of the 2 ties touching AC2, and no error. Second: one voltage warning at `C_G1`, and no error.

#### TC-VAL-028 — Unconnected sources and buses warn

- **Fixture:** FX-EMPTY, FX-SINGLE, FX-BAT
- **Steps:** Validate FX-EMPTY. On FX-SINGLE add AC9 with no contactor. Separately add AC8 reachable only through an open tie from AC1. On FX-BAT add AC7 feeding a new TRU7 to DCB, with no AC source.
- **Expected:** One no-contactor warning at G2's path and no error. One no-feed warning for AC9 and no error. No no-feed warning for AC8. One no-feed warning for AC7, because a TRU passes nothing from DC to AC.

#### TC-VAL-029 — TRU contactor role comes from the bus it joins

- **Fixture:** FX-SINGLE
- **Steps:** Swap `from` and `to` on `TRU1_IN`. Separately swap them on `TRU1_OUT`. Separately swap them on both.
- **Expected:** No error in any of the 3, under the AC to DC, kind or contactor-count rules.

#### TC-VAL-030 — Source output must suit its kind

- **Fixture:** FX-ALLKINDS, FX-RAT
- **Steps:** `M:` BAT `output = "AC"`. Separately G1 `output = "DC"`. Separately APU `output = "DC"`. Validate FX-RAT, which has an emergency generator of each `output`.
- **Expected:** Each mutation gives exactly one error at that source's `output` path. FX-RAT gives none. An error at the source's contactor under L2-VAL-020 is a separate fault and is not counted here.

#### TC-VAL-031 — No essential load warns at $.loads

- **Fixture:** FX-SINGLE, FX-EMPTY, FX-SINGLE-E
- **Steps:** Validate each.
- **Expected:** FX-SINGLE and FX-EMPTY: one warning at exactly `$.loads`, no error and a usable definition. FX-SINGLE-E: an empty warning list.

#### TC-VAL-032 — validate entry point and result fields

- **Fixture:** FX-SINGLE-E, FX-THREEERR
- **Steps:** Call `ela.validate.validate` on each.
- **Expected:** FX-SINGLE-E: empty `errors` and a `definition`. FX-THREEERR: `errors` entries each holding `path` and `message`, and `definition` is `None`.

### C-ENGINE

#### TC-ENG-001 — State map over defaults

- **Fixture:** FX-ALLKINDS
- **Steps:** `analyse(defn, {"G1": "failed"})`.
- **Expected:** `R.el[G1].state` is `failed`, and every other element's state equals its `default_state`, with `C_APU` open and RAT_AC `unavailable`.

#### TC-ENG-002 — Crew switch default

- **Fixture:** FX-CREW
- **Steps:** Analyse with `{}`, then `{"DCS": "off"}`.
- **Expected:** `R.el[DCS].state` is `on`, then `off`.

#### TC-ENG-003 — Only live sources are energised

- **Fixture:** FX-SINGLE, FX-RAT
- **Steps:** FX-SINGLE with `{"G1": "failed"}`. FX-RAT with `{}`. FX-RAT with `{"RAT_AC": "available"}`.
- **Expected:** G1 and AC1 de-energised. RAT_AC and ACE de-energised. RAT_AC and ACE energised, RAT_DC and DCE still de-energised.

#### TC-ENG-073 — A live source is energised with its contactors open

- **Fixture:** FX-APU, FX-RAT
- **Steps:** FX-APU with `{}`, `{"APU": "failed"}`, `{"G1": "failed"}`. FX-RAT with `{"RAT_AC": "available", "C_RAT_AC": "open"}`.
- **Expected:** APU energised with `C_APU` open, then de-energised, then energised with AC1 dead. RAT_AC energised with ACE dead.

#### TC-ENG-004 — Bus energised by a closed path

- **Fixture:** FX-CHAIN
- **Steps:** Analyse with `{}`. Then `{"T23": "open"}`. Then `{"T12": "open"}`. Then `{"C_G1": "open"}`.
- **Expected:** All three energised. AC1, AC2 only. AC1 only. None.

#### TC-ENG-005 — Contactors are bidirectional when closed and block when open

- **Fixture:** FX-CHAIN, then a copy with `from` and `to` swapped on T12. FX-SINGLE with `from` and `to` swapped on `TRU1_IN`
- **Steps:** Analyse both with `{}` and with `{"T12": "open"}`. Repeat with `C_G1` joined to AC3 instead of AC1. Analyse the FX-SINGLE copy with `{}`.
- **Expected:** Closed: identical energisation in both copies and from either end. Open: the far bus de-energised from either end. FX-SINGLE: `TRU1_IN` stays the input, with D(`TRU1_IN`) = 2000/1600/1000 and TRU1 energised.

#### TC-ENG-006 — TRU energisation truth table

- **Fixture:** FX-SINGLE
- **Steps:** All 8 combinations of TRU1 `operative`/`failed`, G1 `operative`/`failed`, `TRU1_IN` `closed`/`open`. Then the single true combination with `TRU1_OUT` `open`.
- **Expected:** TRU1 energised only for operative, live, closed. It stays energised with `TRU1_OUT` open.

#### TC-ENG-007 — Energisation does not pass from DC to AC

- **Fixture:** FX-BAT
- **Steps:** Analyse with `{"G1": "failed"}`.
- **Expected:** DC1 and DCB energised by BAT. TRU1 and AC1 de-energised with both TRU contactors closed.

#### TC-ENG-008 — A failed source does not bridge buses

- **Fixture:** FX-SRCBRIDGE
- **Steps:** Analyse with `{"G1": "failed", "G2": "operative"}`.
- **Expected:** AC1 energised by G2. AC2 de-energised.

#### TC-ENG-009 — Contactor energisation

- **Fixture:** FX-CHAIN
- **Steps:** Analyse with `{"T23": "open"}`, then with `{"C_G1": "open"}`. Add a second live source G2 → AC3 and analyse with `{"T23": "open"}`.
- **Expected:** T12 closed with live ends is energised. T12 with two dead ends is not. T23 open with two live ends is not.

#### TC-ENG-010 — Own-load power is a lossless sum

- **Fixture:** G1 cap 2000 → AC1. L1 on AC1: 100. L2 on AC1: 250. Separately FX-MARGIN
- **Steps:** Analyse with `{}`.
- **Expected:** `R.el[AC1].own` = 350, and for FX-MARGIN exactly 1000.

#### TC-ENG-011 — Dead bus counts no load

- **Fixture:** FX-MARGIN
- **Steps:** Analyse with `{"C_G1": "open"}`.
- **Expected:** `R.el[AC1].own` = 0/0/0, and `.demand` is null in all 3 bands.

#### TC-ENG-012 — Crew switch off zeroes own loads only

- **Fixture:** FX-CREW
- **Steps:** Analyse with `{}`, then `{"DCS": "off"}`.
- **Expected:** On: DCS own 200/150/100, demand 500/400/300 (own + LX), BAT 500/400/300. Off: DCS energised, own 0/0/0, demand 300/250/200, BAT 300/250/200, and DCX own unchanged at 300/250/200.

#### TC-ENG-013 — Load power is unchanged across sample scenarios

- **Fixture:** FX-SAMPLE
- **Steps:** For every scenario and every bus energised with no crew switch off, compare `R.el[bus].own` with the sum of `power` of its loads in the file.
- **Expected:** Equal in all three bands, so each bus's own-load power is identical across those scenarios.

#### TC-ENG-014 — TRU loss chain in all three bands

- **Fixture:** FX-SINGLE
- **Steps:** Analyse with `{}`.
- **Expected:** `R.el[TRU1].output` = 1700/1360/850. `.input` = 1700 ÷ 0.85 = 2000, 1360 ÷ 0.85 = 1600, 850 ÷ 0.85 = 1000. D(G1) = 2000 + 2000 = 4000, 1500 + 1600 = 3100, 1000 + 1000 = 2000.

#### TC-ENG-015 — Efficiency of exactly 1.0

- **Fixture:** FX-SINGLE. M: `$.trus[0].efficiency = 1.0`
- **Steps:** Analyse with `{}`.
- **Expected:** TRU1 input = output = 1700/1360/850. D(G1) = 3700/2860/1850.

#### TC-ENG-016 — Throughput on a feeding bus with own loads reported separately

- **Fixture:** FX-THROUGH
- **Steps:** Analyse with `{}`.
- **Expected:** D(AC1) = 3900/3300/2500, which is own + TRU input + T12 flow. `R.el[AC1].own` = 1200/1100/1000. D(AC2) = own = 700/600/500. TRU input is counted once, though `TRU1_IN` is also a closed contactor leaving the bus.

#### TC-ENG-017 — A feeding bus overloads on throughput, not own loads

- **Fixture:** FX-THROUGH. M: AC1 capacity 4000
- **Steps:** Analyse with `{}`.
- **Expected:** With margin 3900 × 1.1 = 4290 > 4000, 3300 × 1.1 = 3630, 2500 × 1.1 = 2750. AC1 overloaded in transient alone. Own load × 1.1 = 1320 would pass. Remaining −290 W (−7.25 %), 370 W (9.25 %), 1250 W (31.25 %).

#### TC-ENG-018 — Islands are split at TRUs

- **Fixture:** FX-SINGLE plus G2 cap 5000 → AC2
- **Steps:** Analyse with `{}`, then with `{"G2": "failed"}`.
- **Expected:** First: 3 islands: {G1, AC1}, {G2, AC2}, {DC1}. DC1 is not in the island of AC1. Second: AC2 is in an island with no source.

#### TC-ENG-019 — Tie flow from a source at one end

- **Fixture:** FX-CHAIN, FX-THROUGH
- **Steps:** Analyse FX-CHAIN with `{}`. Analyse FX-THROUGH with `{}`, then with TRU1 and `TRU1_IN` moved to AC2.
- **Expected:** FX-CHAIN: D(T12) = 200 + 300 = 500, D(T23) = 300, D(AC1) = D(G1) = 600, D(AC2) = 500, D(AC3) = 300. FX-THROUGH: D(T12) = 700/600/500. Moved: D(T12) = 700 + 2000 = 2700, 600 + 1600 = 2200, 500 + 1000 = 1500, with TRU input in the cut-set, and D(G1) = 3900/3300/2500 in both.

#### TC-ENG-020 — Tie with equal TRUs at both ends

- **Fixture:** FX-TIE-EQ
- **Steps:** Analyse with `{}`. Then swap the ids TRU_A and TRU_B, so the tree root moves to the other bus.
- **Expected:** Island demand 300 + 100 = 400, so each TRU carries 200 and draws 200 ÷ 0.80 = 250. D(T_DC) = |100 − 200| = 100 in both runs. D(DCA) = 300, D(DCB) = 100 + 100 = 200, D(G1) = D(G2) = 250.

#### TC-ENG-021 — Tie with unequal TRUs and flow toward the root

- **Fixture:** FX-TIE-DC
- **Steps:** Analyse with `{}`. Then `M:` LD1 = 300, LD2 = 600.
- **Expected:** First: TRU1 600, TRU2 300. Side away from root is DC2 and TRU2, net 100 − 300 = −200, so D(T_DC) = 200. D(DC1) = 800, D(DC2) = 100 + 200 = 300. Second: net 600 − 300 = 300, so D(T_DC) = 300. D(DC1) = 300 + 300 = 600, D(DC2) = 600. All flows are non-negative.

#### TC-ENG-022 — Spanning tree of a ring from the lowest source

- **Fixture:** FX-RING
- **Steps:** Analyse with `{}`. Then with `C_G1` joined to AC2 instead. Then reverse every JSON array of the first copy.
- **Expected:** First: tree edges `C_G1`, T12, T13. D(T12) = 200, D(T13) = 300, D(T23) = 0/0/0, D(G1) = 600. Second: AC2's neighbours in id order are AC1 and AC3, so T13 is left out. D(T12) = 100, D(T23) = 300, D(T13) = 0, D(AC2) = 200 + 100 + 300 = 600. Third: equal to the first.

#### TC-ENG-023 — Parallel ties between the same two buses

- **Fixture:** G1 cap 20000 → AC1. Ties TA and TB both AC1–AC2. L2 on AC2: 200
- **Steps:** Analyse with `{}`. Then swap the declaration order of TA and TB.
- **Expected:** In both runs TA, the lower contactor id, carries 200 and TB carries 0, and the warning names TB.

#### TC-ENG-074 — Neighbours are ordered by code point

- **Fixture:** G1 cap 20000 → B1. Ties TA (B1–B10), TB (B1–B2), TC (B10–BX), TD (B2–BX). L on BX: 100
- **Steps:** Analyse with `{}`.
- **Expected:** `B10` sorts before `B2` by code point, so BX is reached through B10. D(TA) = D(TC) = 100, D(TB) = D(TD) = 0, and the warning names TD. Numeric order would keep TD instead.

#### TC-ENG-024 — Meshed island warning

- **Fixture:** FX-RING, then FX-CHAIN
- **Steps:** Analyse each with `{}`.
- **Expected:** FX-RING: one `meshed_island` warning naming T23, verdict PASS. FX-CHAIN: no such warning. `R.overloads` and verdict do not depend on the warning.

#### TC-ENG-075 — No mesh warning on dead or paralleled rings

- **Fixture:** FX-RING, then FX-RING plus G2 cap 20000 → AC3
- **Steps:** Analyse FX-RING with `{"G1": "failed"}` and `{"C_G1": "open"}`. Analyse the second definition with `{}`.
- **Expected:** No `meshed_island` warning in any. On the dead ring AC1, AC2 and AC3 are in one island with no source. The second has one error containing "AC sources paralleled", naming G1 and G2.

#### TC-ENG-025 — Loop through a source with two contactors

- **Fixture:** FX-SRCBRIDGE plus tie T_AB (AC1–AC2)
- **Steps:** Analyse with `{}`, in which G2 is failed.
- **Expected:** Breadth-first from G1 keeps C1A and C1B. T_AB is left out and named in the warning. D(C1A) = 300, D(C1B) = 500, D(T_AB) = 0.

#### TC-ENG-026 — Contactor demand on TRU feeds and split sources

- **Fixture:** FX-SINGLE with LA removed and LD = 850, then FX-SRCBRIDGE
- **Steps:** Analyse each with `{}`.
- **Expected:** FX-SINGLE: D(`TRU1_OUT`) = 850, D(`TRU1_IN`) = 850 ÷ 0.85 = 1000, D(`C_G1`) = 1000. FX-SRCBRIDGE: D(C1A) = 300, D(C1B) = 500, D(G1) = 800.

#### TC-ENG-027 — Energised TRU with open output feeds nothing

- **Fixture:** FX-SINGLE
- **Steps:** Analyse with `{"TRU1_OUT": "open"}`.
- **Expected:** TRU1 energised. Input and output 0/0/0. DC1 de-energised. D(G1) = own of AC1 = 2000/1500/1000. D(`TRU1_IN`) = 0.

#### TC-ENG-028 — Paralleled generators give one named error

- **Fixture:** FX-PAR
- **Steps:** Analyse with `{}`.
- **Expected:** One entry in `R.config_errors`, containing "AC sources paralleled", G1 and G2. Verdict FAIL.

#### TC-ENG-029 — Available RAT output closed onto a live bus

- **Fixture:** FX-RAT without RAT_DC. Plus G1 cap 5000 → ACE
- **Steps:** Analyse with `{"RAT_AC": "available"}`, then with `{}`.
- **Expected:** First: one error containing "AC sources paralleled", naming RAT_AC and G1. Second: none, because RAT_AC is `unavailable`.

#### TC-ENG-030 — Not paralleled when a source is isolated or failed

- **Fixture:** FX-APU, FX-PAR
- **Steps:** FX-APU with `{}`, where APU is operative with `C_APU` open. FX-PAR with `{"G2": "failed"}`. FX-PAR with `{"C_G2": "open"}`.
- **Expected:** `R.config_errors` is empty in all three.

#### TC-ENG-031 — Paralleled island figures

- **Fixture:** FX-PAR
- **Steps:** Analyse with `{}`.
- **Expected:** AC1, AC2 energised. `.own` = 1000 and 3000. D(AC1) = 1000 + 500 = 1500, D(AC2) = 3000, with no tie flow counted.

#### TC-ENG-032 — Paralleled sources and contactors carry no demand

- **Fixture:** FX-PAR
- **Steps:** Analyse with `{}`.
- **Expected:** G1, G2, `C_G1`, `C_G2`, T12 and `TRU1_IN` have null demand and are absent from `R.checked`. `R.overloads` is empty, though 4000 W of loads exceeds 1000 W per source.

#### TC-ENG-033 — DC downstream of a paralleled island

- **Fixture:** FX-PAR
- **Steps:** Analyse with `{}`, then with `{"T12": "open"}`.
- **Expected:** Both: D(DC1) = 400, TRU1 output = 400, TRU1 checked, D(`TRU1_OUT`) = 400. TRU1 input is 500, as it enters AC1 demand.

#### TC-ENG-034 — Two TRUs share by continuous capacity in all bands

- **Fixture:** FX-TWO-TRU
- **Steps:** Analyse with `{}`.
- **Expected:** TRU1 output 1200/900/600, TRU2 output 600/450/300, in the continuous 2 : 1 ratio even in transient, where capacity is 2.5 : 1. Inputs 1200 ÷ 0.8 = 1500, 900 ÷ 0.8 = 1125, 600 ÷ 0.8 = 750, and 600 ÷ 0.75 = 800, 450 ÷ 0.75 = 600, 300 ÷ 0.75 = 400. D(G1) = 1500/1125/750, D(G2) = 800/600/400.

#### TC-ENG-035 — TRU and DC RAT output share, with the battery silent

- **Fixture:** FX-TRU-RAT
- **Steps:** Analyse with `{}`.
- **Expected:** Continuous 6000 : 3000, so TRU1 600 and RAT_DC 300 in every band, even with transient capacities 9000 : 1000. D(BAT) = 0/0/0. D(G1) = 600 ÷ 0.8 = 750.

#### TC-ENG-036 — Empty island and zero demand share cleanly

- **Fixture:** FX-EMPTY, and FX-TWO-TRU with LD at 0
- **Steps:** Analyse each with `{}`.
- **Expected:** No exception. FX-EMPTY: D(G1) = D(AC1) = D(TRU1) = D(DC1) = 0, DC1 current 0, G1 margin 100 %, AC2 de-energised, verdict PASS. FX-TWO-TRU: both TRUs at 0.

#### TC-ENG-037 — Zero total capacity splits equally

- **Fixture:** FX-TWO-TRU. M: both TRU capacities 0/0/0, LD 900
- **Steps:** Analyse with `{}`.
- **Expected:** Each TRU carries 900 ÷ 2 = 450, with no division error. Both are overloaded.

#### TC-ENG-038 — Battery priority on and off

- **Fixture:** FX-BAT, then BAT cap 6000/4500/3000 → DC1 with L on DC1: 500
- **Steps:** Analyse FX-BAT with `{}`, then `{"TRU1": "failed"}`. Analyse the second definition with `{}`.
- **Expected:** On: D(BAT) = 0/0/0, TRU1 output 340 + 510 = 850, input 850 ÷ 0.85 = 1000, D(G1) = 1000, D(T_B) = 510, D(DC1) = 850, D(DCB) = 510. Off: D(BAT) = 850, D(`C_BAT`) = 850, D(T_B) = 340, D(DCB) = 850, D(DC1) = 340, D(G1) = 0. Second definition: D(BAT) = 500.

#### TC-ENG-039 — What counts as feeding the island

- **Fixture:** FX-BAT
- **Steps:** Analyse with `{"TRU1": "failed"}`, `{"G1": "failed"}`, `{"TRU1_IN": "open"}`, `{"TRU1_OUT": "open"}`.
- **Expected:** D(BAT) = 850 in each. In the last, TRU1 is still energised and BAT still takes all the demand.

#### TC-ENG-040 — Two sole batteries share by continuous capacity

- **Fixture:** FX-BAT2
- **Steps:** Analyse with `{}`. Then `{"BAT2": "failed"}`. Then add G1 cap 5000 → AC1 and TRU1: AC1 → DC1, η 0.85, cap 3000, and analyse with `{}`.
- **Expected:** 800 × 3000 ÷ 4000 = 600 and 800 × 1000 ÷ 4000 = 200. Then BAT1 800 alone. With the TRU feeding, both 0.

#### TC-ENG-041 — No negative battery demand

- **Fixture:** FX-SAMPLE, FX-BAT
- **Steps:** Analyse every sample scenario and FX-BAT with `{}`.
- **Expected:** Every battery's demand is at least 0 in all three bands.

#### TC-ENG-042 — RAT outputs have no combined limit

- **Fixture:** FX-RAT
- **Steps:** Analyse with `{"RAT_AC": "available", "RAT_DC": "available"}`.
- **Expected:** 4500 × 1.1 = 4950 ≤ 5000 and 2700 × 1.1 = 2970 ≤ 3000. No overload, though 4500 + 2700 = 7200 exceeds each capacity.

#### TC-ENG-043 — Margin exactly at the limit

- **Fixture:** FX-MARGIN
- **Steps:** Analyse as is. Then `M:` L1 = 1001. Then `M:` G1 cap 1099. Then, for each band in turn, set G1 capacity in only that band to 1099.
- **Expected:** 1100 ≤ 1100, not overloaded, remaining 0 W and 0 %. 1101.1 > 1100, overloaded. 1100 > 1099, overloaded. Per band: overloaded in that band alone.

#### TC-ENG-044 — Equality survives binary rounding

- **Fixture:** FX-MARGIN. M: L1 = 3000, G1 cap 3300. Then G1 cap 3299.9999995, cap 3299.99999, cap 3299
- **Steps:** Analyse each.
- **Expected:** 3000 × 1.10 = 3300, so at cap 3300 G1 is not overloaded, with remaining 0 W. In IEEE doubles `3000 * 1.1` is 3300.0000000000005, so a bare `<=` fails this case. At cap 3299.9999995 the excess is 5e-7 W, within 1e-6 W, so it is not overloaded. At cap 3299.99999 the excess is 1e-5 W, and at cap 3299 it is 1 W, so both are overloaded.

#### TC-ENG-045 — Which elements are checked

- **Fixture:** FX-BATCH, FX-BAT
- **Steps:** FX-BATCH with `{"G1": "failed"}`. FX-BAT with `{}`.
- **Expected:** First: G1 absent, G2 present, T12 absent (open), and AC1 absent (no capacity). Second: BAT present at 0 W with remaining 100 %, because zero demand counts as checked.

#### TC-ENG-046 — Per-element margin override

- **Fixture:** FX-OVERRIDE
- **Steps:** Analyse as is. Then `M:` G1 cap 1249. Then `M:` G1 `safety_margin` 0, cap 1000, AC1 capacity 1100.
- **Expected:** First: G1 with margin 1250, AC1 with margin 1100, no overload. Second: G1 overloaded. Third: G1 with margin 1000, not overloaded, which proves 0 overrides the global 0.10 rather than falling back to it.

#### TC-ENG-047 — Element with no capacity is unchecked

- **Fixture:** FX-MARGIN. M: L1 = 1000000, G1 cap 2000000
- **Steps:** Analyse with `{}`.
- **Expected:** AC1 absent from `R.checked`, with no overload. Capacity, remaining W and remaining % are null.

#### TC-ENG-048 — One failing band overloads the element

- **Fixture:** FX-TRAN variant with AC1 load 500/1000/100
- **Steps:** Analyse with `{}`.
- **Expected:** AC1 overloaded. Its overload entries list `short_term` alone (1100 > 1000, and 550 and 110 pass).

#### TC-ENG-049 — TRU is checked on output power

- **Fixture:** FX-SINGLE. M: LA removed, LD 850, TRU1 capacity 900, `settings.safety_margin` 0
- **Steps:** Analyse with `{}`.
- **Expected:** 850 ≤ 900, not overloaded, though input is 1000 > 900.

#### TC-ENG-050 — Remaining margin

- **Fixture:** FX-MARGIN with G1 cap 2000, then FX-SINGLE
- **Steps:** Analyse FX-MARGIN with L1 = 1000, then L1 = 2000. Analyse FX-SINGLE with `{}`.
- **Expected:** 2000 − 1000 × 1.1 = 900 W, 900 ÷ 2000 = 45 %. 2000 − 2000 × 1.1 = −200 W, −10 %. FX-SINGLE: G1 15600/11590/7800 W and 78/77.27/78 %, TRU1 4130/3504/3065 W and 68.83/70.08/76.63 %, with TRU1 measured on output.

#### TC-ENG-051 — Zero capacity

- **Fixture:** FX-ZERO
- **Steps:** Analyse as is. Then `M:` L1 = 0.
- **Expected:** −100 %, overloaded (1.1 > 0). Then 0 %, not overloaded (0 ≤ 0). No division error.

#### TC-ENG-052 — Worst element by percentage

- **Fixture:** FX-WORST
- **Steps:** Analyse with `{}`.
- **Expected:** `R.worst` is G2, band transient, 12 %. All bands tie, so transient is chosen by the band order.

#### TC-ENG-053 — Worst element ties resolve by id, then band

- **Fixture:** FX-WORST with G1 and G2 both at 88 % demand and G3 at 75 %. Then a copy with margin 0.10, G4 cap 1000 at 900 and G5 cap 3000 at 2700. Then that copy with G5 at 2700.1
- **Steps:** Analyse all three.
- **Expected:** First: G1, transient. Second: both elements are at 1000 − 990 = 10 W of 1000 and 3000 − 2970 = 30 W of 3000, both exactly 1 %, so G4 wins. Unrounded doubles give 0.9999999999999886 and 0.9999999999999848, which differ by under 1e-6 % and so are tied. Third: 3000 − 2970.11 = 29.89 W, 0.9963 %, a real difference, so G5 wins.

#### TC-ENG-054 — Nothing checked gives null

- **Fixture:** FX-ESS
- **Steps:** Analyse with `{"G1": "failed", "BAT": "failed"}`.
- **Expected:** `R.worst` is null for element, band and margin. `R.checked` is empty.

#### TC-ENG-055 — Verdict truth table

- **Fixture:** FX-BATCH
- **Steps:** Analyse with the `states` of S1, S5, S3 and S4.
- **Expected:** PASS, FAIL, FAIL, FAIL, for clean, overloaded, paralleled, unpowered essential.

#### TC-ENG-056 — The essential-load failure

- **Fixture:** FX-ESS
- **Steps:** Analyse with `{}`. Then `{"G1": "failed"}`. Then `{"G1": "failed", "DCS": "off"}`. Then `{"G1": "failed", "BAT": "failed", "DCS": "off"}`.
- **Expected:** None. LE1, LE2. LE1, LE2, LE3, each with id, name and bus, and LN never. In the last, LE3 is listed once though its bus is both dead and off. Verdict PASS, then FAIL for the other three, with zero overloads in all.

#### TC-ENG-057 — Total loss fails only through essential loads

- **Fixture:** FX-ESS, then a copy with no load essential
- **Steps:** Analyse each with `{"G1": "failed", "BAT": "failed"}`.
- **Expected:** First: FAIL with 3 unpowered. Second: PASS with nothing checked. That second result is what DD-001 exists to prevent for definitions that do flag essential loads.

#### TC-ENG-058 — Overload entries

- **Fixture:** FX-TRAN
- **Steps:** Analyse with `{}`.
- **Expected:** AC2 gives 2 entries: transient 1100 against 1000, short_term 1045 against 1000. G4 gives 2 entries: 1100 and 1100 against 1000. `C_G3` gives transient 550 against 100. AC1 gives transient 1100 against 1000. 6 entries in all.

#### TC-ENG-059 — Result record for every element

- **Fixture:** FX-SAMPLE
- **Steps:** Analyse with `{}`.
- **Expected:** Every source, bus, TRU and contactor has `.energised`, and `.demand`, `.with_margin`, `.capacity`, `.margin_w`, `.margin_pct` for all 3 bands. Capacity and both remaining-margin fields are null where no capacity is defined. `.with_margin` stays a number on an energised element with no capacity. `.demand` is null on each de-energised element, and `.own` is a number on every bus.

#### TC-ENG-060 — Load percentage of capacity

- **Fixture:** FX-SINGLE, FX-DISPLAY, and FX-EMPTY with G1 cap 0
- **Steps:** Analyse each with `{}`. Analyse FX-SINGLE with `{"G1": "failed"}`.
- **Expected:** G1 20/20.67/20 %, TRU1 28.33/27.2/21.25 %. G4 45000 ÷ 90000 = 50 % exactly. Null for the zero-capacity G1, with no division error. Null for failed G1, as its demand is null.

#### TC-ENG-061 — Bus voltage is nominal at any demand

- **Fixture:** FX-CREW, with DCS at `voltage` 28
- **Steps:** Analyse with `{"DCS": "off"}` and LX = 0, then with LX = 5000.
- **Expected:** DCS `.voltage` is 28 in both.

#### TC-ENG-062 — DC current uses throughput

- **Fixture:** BAT cap 5000 → DC1. L on DC1: 2800. Then FX-CREW with `{}`
- **Steps:** Analyse.
- **Expected:** 2800 ÷ 28 = 100 A. FX-CREW DCS continuous: 300 ÷ 28 = 10.714 A, using demand 300, not own 100.

#### TC-ENG-063 — AC current uses throughput per phase

- **Fixture:** G1 cap 5000 → AC1. L on AC1: 3450. Then `phases` 1 with L = 1150. Then FX-THROUGH
- **Steps:** Analyse.
- **Expected:** 3450 ÷ (3 × 115) = 10 A. 1150 ÷ (1 × 115) = 10 A. FX-THROUGH AC1 continuous 2500 ÷ 345 = 7.246 A, using demand, not own.

#### TC-ENG-064 — No electrical quantities on a dead bus

- **Fixture:** FX-MARGIN
- **Steps:** Analyse with `{"G1": "failed"}`.
- **Expected:** AC1 `.voltage`, `.demand` and `.current` are null in all 3 bands. `.own` is 0/0/0.

#### TC-ENG-065 — One analysis entry point

- **Fixture:** FX-SAMPLE
- **Steps:** For every scenario compare `analyse(defn, scenario.states)` with the matching `run_batch` result.
- **Expected:** Equal in verdict, worst element and band, margin, and all counts.

#### TC-ENG-076 — Element record fields by kind

- **Fixture:** FX-SINGLE
- **Steps:** Analyse with `{}`. Read the attribute names of `el[G1]`, `el[AC1]`, `el[TRU1]`, `el[C_G1]`.
- **Expected:** All hold exactly `state`, `energised`, `demand`, `with_margin`, `capacity`, `margin_w`, `margin_pct`, plus: G1 `load_pct`; AC1 `own`, `voltage`, `current`; TRU1 `load_pct`, `input`, `output`; `C_G1` nothing more.

#### TC-ENG-077 — analyse entry point and result fields

- **Fixture:** FX-BATCH
- **Steps:** Call `ela.engine.analyse` with the S5, S3 and S4 states.
- **Expected:** Each result has `verdict`, `overloads`, `config_errors`, `unpowered`, `warnings`, `worst`, `checked`, `islands`, `el`. S5 overload entries hold `element`, `band`, `demand_with_margin`, `capacity`, and `worst` holds `element`, `band`, `margin_pct`. S4 `unpowered` entries hold `id`, `name`, `bus`. S3 `config_errors` is non-empty.

#### TC-ENG-066 — No time input

- **Fixture:** FX-SINGLE
- **Steps:** Inspect `inspect.signature(analyse)`. Call twice with equal input.
- **Expected:** Two parameters, definition and state map. Equal output.

#### TC-ENG-067 — Inputs are not modified

- **Fixture:** FX-BATCH
- **Steps:** Deep-copy the definition and state map. Call `analyse` with S5 states. Compare.
- **Expected:** Both equal their deep copies.

#### TC-ENG-068 — No automatic reconfiguration

- **Fixture:** FX-BATCH
- **Steps:** Analyse with `{"G1": "failed"}`.
- **Expected:** Each contactor's state equals its default, with T12 still open and AC1 still de-energised though AC2 is live.

#### TC-ENG-069 — No load shedding

- **Fixture:** FX-BATCH
- **Steps:** Analyse with the S5 states.
- **Expected:** AC1 own 1000/900/800, AC2 own 1000/900/800, AC3 own 2000/1000/1200, with G1 overloaded.

#### TC-ENG-070 — No endurance quantity

- **Fixture:** FX-BAT2
- **Steps:** Serialise `analyse(defn, {})` to JSON and walk its keys.
- **Expected:** No key contains `endurance`, `amp_hour` or `depletion`.

#### TC-ENG-071 — Engine has no web dependency

- **Fixture:** None
- **Steps:** In a fresh subprocess, import `ela.engine` and read `sys.modules`.
- **Expected:** `ela/engine.py` exists, and `fastapi`, `starlette`, `uvicorn` are absent.

#### TC-ENG-072 — Engine topics have tests

- **Fixture:** None
- **Steps:** From the collected tests with marks, map each of the 9 topics to the requirements that define it. Run `pytest tests -m "not meta"` in a subprocess.
- **Expected:** At least one collected test per topic, and the selection passes.

### C-SAMPLE

#### TC-SMP-001 — Sample path and validity

- **Fixture:** FX-SAMPLE
- **Steps:** Validate the file.
- **Expected:** It exists, the error list is empty, and `meta.aircraft` contains `twin` in any case.

#### TC-SMP-002 — Sample sources

- **Fixture:** FX-SAMPLE
- **Steps:** Count `sources` by `kind` and `output`.
- **Expected:** 2 `engine_generator`, 1 `apu_generator`, at least 1 `emergency_generator` with `output` AC, 1 `battery`.

#### TC-SMP-003 — Sample buses and crew switch

- **Fixture:** FX-SAMPLE
- **Steps:** Search bus `name` values for AC BUS 1, AC BUS 2, AC ESS, DC BUS 1, DC BUS 2, DC ESS, DC BAT.
- **Expected:** Each is contained in exactly one bus, of the expected `type`. The DC BAT bus has `crew_switch` true.

#### TC-SMP-004 — Sample TRUs

- **Fixture:** FX-SAMPLE
- **Steps:** Read `trus`.
- **Expected:** Exactly 3 entries, and exactly one has the DC ESS bus as `output_bus`.

#### TC-SMP-005 — Sample contactors

- **Fixture:** FX-SAMPLE
- **Steps:** Inspect `contactors`.
- **Expected:** Each source has at least one `source` contactor. Each TRU has one input and one output contactor. A `bus_tie` joins AC BUS 1 and AC BUS 2. A `bus_tie` joins an AC main bus and AC ESS. DC ESS and DC BAT are each an end of a `bus_tie`.

#### TC-SMP-006 — Sample load and scenario counts and band pattern

- **Fixture:** FX-SAMPLE
- **Steps:** Count `loads` and `scenarios`, and compare band values.
- **Expected:** 40 ≤ loads ≤ 60. 10 ≤ scenarios ≤ 15. `transient ≥ short_term ≥ continuous > 0` for every load.

#### TC-SMP-007 — A load on every named bus

- **Fixture:** FX-SAMPLE
- **Steps:** Collect `loads[].bus`.
- **Expected:** Each of the 7 named buses appears.

#### TC-SMP-008 — Sample essential loads reachable on battery only

- **Fixture:** FX-SAMPLE
- **Steps:** List loads with `essential` true. Analyse the battery-only scenario found by L2-SMP-019's condition.
- **Expected:** At least one, and at least one is on the DC BAT bus. The bus of each is energised in that scenario, and every AC bus is de-energised.

#### TC-SMP-009 — Normal scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Find scenarios with both engine generators live and all emergency generator outputs not live. Analyse them.
- **Expected:** At least one has verdict PASS.

#### TC-SMP-010 — Each single generator loss

- **Fixture:** FX-SAMPLE
- **Steps:** Find scenarios by generator state, using the `engine` number and not an assumed id.
- **Expected:** One has engine 1 failed and engine 2 live. Another has engine 2 failed and engine 1 live.

#### TC-SMP-011 — APU-only scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Find a scenario with both engine generators failed and the APU live. Analyse it.
- **Expected:** The APU generator has non-zero demand in all bands, and no emergency output is live.

#### TC-SMP-012 — One generator plus APU loss

- **Fixture:** FX-SAMPLE
- **Steps:** Read each scenario's states with defaults applied.
- **Expected:** At least one scenario has the APU and exactly one engine generator `failed`.

#### TC-SMP-013 — Each TRU fails somewhere

- **Fixture:** FX-SAMPLE
- **Steps:** Read `states` of all scenarios.
- **Expected:** Each of the 3 TRU ids has the value `failed` in some scenario.

#### TC-SMP-014 — RAT-only scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Find a scenario with engine and APU generators failed and an emergency output `available`. Analyse it.
- **Expected:** That output has non-zero demand, and at least one AC bus is energised.

#### TC-SMP-015 — Battery-only scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Find a scenario with engine and APU generators failed and no emergency output available. Analyse it.
- **Expected:** The battery has non-zero demand, and every AC bus is de-energised.

#### TC-SMP-016 — Designed overload scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Analyse every designed-to-fail scenario.
- **Expected:** At least one has FAIL, at least one overload and no configuration error.

#### TC-SMP-017 — Designed essential-load scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Analyse every designed-to-fail scenario.
- **Expected:** At least one has FAIL, at least one unpowered essential load, zero overloads and no configuration error.

#### TC-SMP-018 — Failures are exactly the designed ones

- **Fixture:** FX-SAMPLE
- **Steps:** Run all scenarios.
- **Expected:** Every scenario lacking the marker gives PASS. Every scenario with the marker gives FAIL.

#### TC-SMP-019 — Sample default configuration

- **Fixture:** FX-SAMPLE
- **Steps:** Analyse with `{}`.
- **Expected:** PASS, no configuration error, no "AC sources paralleled" text, and each emergency output `unavailable`.

#### TC-SMP-020 — Scenarios list the contactor changes they need

- **Fixture:** FX-SAMPLE
- **Steps:** Take the RAT-only scenario. Analyse it. Separately analyse a copy with its contactor entries removed.
- **Expected:** `states` lists at least one contactor, and an AC bus is energised. The copy has a different result, so the entries are needed.

#### TC-SMP-021 — Scenarios list only differences

- **Fixture:** FX-SAMPLE
- **Steps:** For each `states` entry compare with the component's default, taking `on` for a crew switch.
- **Expected:** No entry equals the default.

#### TC-SMP-022 — A hand-calculated test per sample scenario

- **Fixture:** FX-SAMPLE
- **Steps:** Read `tests/data/generic_twin_expected.json`. Collect tests. Run `pytest tests -m "not meta"` in a subprocess.
- **Expected:** Every scenario id has a recorded verdict and source demands, a collected test parametrised on that id, and a pass. The file holds no unknown scenario id.

### C-BATCH

#### TC-BAT-001 — One result per scenario in file order

- **Fixture:** FX-BATCH12
- **Steps:** `run_batch(defn)`.
- **Expected:** 12 results with ids in the order `Z01, A02, M03, B04, Y05, C06, X07, D08, W09, E10, V11, F12`, not sorted.

#### TC-BAT-002 — Scenarios are independent

- **Fixture:** FX-BATCH
- **Steps:** Run, then reverse `scenarios` and run again.
- **Expected:** Each scenario's result is equal in both, with G1 failed in S2 not carrying into S3.

#### TC-BAT-003 — Summary fields

- **Fixture:** FX-BATCH
- **Steps:** Run.
- **Expected:** All 9 fields of all 5 scenarios equal the FX-BATCH result table, with `overloads` 3 on S5 counting entries.

#### TC-BAT-004 — Detail lists

- **Fixture:** FX-BATCH, FX-RING
- **Steps:** Run.
- **Expected:** S5 `overload_details`: (G1, transient), (G1, continuous), (T13, transient). S3 `error_messages` has one message containing "AC sources paralleled". S4 `unpowered_details` names LA1. S1 lists and `warnings` are all empty. FX-RING M1 `warnings` holds a `meshed_island` warning naming T23.

#### TC-BAT-005 — Batch uses the engine result

- **Fixture:** FX-BATCH
- **Steps:** Compare each result with `analyse` for the same states. Then monkeypatch `analyse` to record calls and run.
- **Expected:** Equal verdict, overloads and worst element. One call per scenario.

#### TC-BAT-006 — Batch has no web dependency

- **Fixture:** None
- **Steps:** In a fresh subprocess, import `ela.batch` and read `sys.modules`.
- **Expected:** `ela/batch.py` exists, and `fastapi`, `starlette`, `uvicorn` are absent.

#### TC-BAT-011 — run_batch entry point and result fields

- **Fixture:** FX-BATCH with only scenario S1
- **Steps:** Call `ela.batch.run_batch`.
- **Expected:** One result holding `scenario_id`, `name`, `result`, `worst_element`, `worst_band`, `smallest_margin_pct`, `overloads`, `configuration_errors`, `unpowered_essential`, `overload_details`, `error_messages`, `unpowered_details`, `warnings`.

#### TC-BAT-007 — CSV shape

- **Fixture:** FX-BATCH12
- **Steps:** Serialise to CSV and parse with `csv.reader`.
- **Expected:** 13 rows. Header exactly `scenario_id, name, result, worst_element, worst_band, smallest_margin_pct, overloads, configuration_errors, unpowered_essential`.

#### TC-BAT-008 — CSV keeps commas, quotes and non-ASCII in names

- **Fixture:** FX-BATCH
- **Steps:** Serialise to CSV, write as UTF-8, read back with `csv.reader`.
- **Expected:** S5 name round-trips exactly, `Overload, tie to "AC3" — T13`, with 9 cells in its row and no blank rows between records. Its `smallest_margin_pct` starts with ASCII `-`.

#### TC-BAT-009 — JSON holds every field and detail

- **Fixture:** FX-BATCH
- **Steps:** Serialise to JSON and parse.
- **Expected:** For every scenario, the 9 summary fields, the 3 detail lists and `warnings`, with values as in the FX-BATCH table. `smallest_margin_pct` on S5 is a JSON number.

#### TC-BAT-010 — Null worst values in exports

- **Fixture:** FX-BATCH
- **Steps:** Serialise S3 and S4 to CSV and JSON.
- **Expected:** `worst_element`, `worst_band` and `smallest_margin_pct` are empty CSV cells, and JSON `null`.

### C-CLI

#### TC-CLI-001 — Both command forms

- **Fixture:** FX-SAMPLE
- **Steps:** Run `python -m ela batch definitions/generic_twin.json` and `ela batch definitions/generic_twin.json`.
- **Expected:** Identical standard output, and the same exit code.

#### TC-CLI-002 — Tab-separated scenario lines, warnings on standard error

- **Fixture:** FX-BATCH, FX-RING
- **Steps:** Run `ela batch` on FX-BATCH, splitting each standard output line on tabs. Run it on FX-RING and read standard error.
- **Expected:** FX-BATCH: 5 lines of 9 tab-separated fields in column order, with values from the FX-BATCH table. S2 reads `S2`, `G1 lost`, `PASS`, `G2`, `continuous`, `12`, `0`, `0`, `0`. S3 and S4 show `—` for worst element, band and margin. S5 keeps its comma and quotes in one field, and its margin is `-46.67`, with ASCII hyphen-minus. Percentages have at most 2 decimals. FX-RING: one line on standard output, and standard error holds one line with `meshed_island` naming T23.

#### TC-CLI-003 — Export options

- **Fixture:** FX-BATCH
- **Steps:** Run with `--csv out.csv --json out.json`, in a temporary folder.
- **Expected:** Both files are created and are equal to the batch runner's CSV and JSON serialisations.

#### TC-CLI-004 — CLI modules

- **Fixture:** None
- **Steps:** Check the files. Run `python -m ela --help`.
- **Expected:** `ela/cli.py` and `ela/__main__.py` exist. The command exits 0 and names `batch`.

#### TC-CLI-005 — Runs with no server and opens no listening port

- **Fixture:** FX-BATCH, H-NOSOCKET
- **Steps:** Confirm no server is running, and run the CLI through H-NOSOCKET.
- **Expected:** The run completes with its normal output and exit code 1, so no `bind` or `listen` was attempted.

#### TC-CLI-006 — Exit code 0

- **Fixture:** FX-ALLPASS
- **Steps:** Run `ela batch`.
- **Expected:** Exit code 0.

#### TC-CLI-007 — Exit code 1

- **Fixture:** FX-SAMPLE, FX-BATCH
- **Steps:** Run `ela batch` on each.
- **Expected:** Exit code 1 for both.

#### TC-CLI-008 — Exit code 2

- **Fixture:** FX-THREEERR
- **Steps:** Run on the fixture, on a missing path, on a file holding `{not json`, with no path argument, and with an unknown option.
- **Expected:** Exit code 2 in all 5, and no traceback on standard error.

#### TC-CLI-009 — Validation errors on standard error

- **Fixture:** FX-THREEERR, with one unknown top-level key added
- **Steps:** Run `ela batch`.
- **Expected:** Exactly 3 lines on standard error, each holding its path (`$.loads[0].power`, `$.trus[0].efficiency`, `$.loads[1].bus`) and a message. The unknown-key warning is not printed. No scenario lines on standard output.

#### TC-CLI-010 — Warnings do not stop a run

- **Fixture:** FX-ALLPASS plus `$.zzz = 1`
- **Steps:** Run `ela batch`.
- **Expected:** The warning naming `zzz` is on standard error, scenario lines are on standard output, and the exit code is 0.

#### TC-CLI-011 — Runtime and dependency management

- **Fixture:** None
- **Steps:** Parse `pyproject.toml`. Run `uv sync --locked`.
- **Expected:** `requires-python` is `>=3.12`. `pyproject.toml` and `uv.lock` exist, and the command exits 0.

### C-LAYOUT

#### TC-LAY-001 — Layout depends on the definition alone

- **Fixture:** FX-SINGLE
- **Steps:** Inspect the signature of `layout`. Compare `layout` before and after `M: $.sources[0].default_state = "failed"`.
- **Expected:** One parameter. Identical coordinates.

#### TC-LAY-017 — layout entry point and item fields

- **Fixture:** FX-MARGIN, H-PAGE
- **Steps:** Call `ela.layout.layout`. Open the definition and undo the view transform on the AC1 bar's on-screen top edge.
- **Expected:** `items` hold `id`, `kind`, `x`, `y`, `width`, `height`. `connectors` hold `from`, `to`, `points`. The AC1 bar's drawn top edge equals its `y` within 1 px.

#### TC-LAY-002 — One item per displayed element

- **Fixture:** FX-SAMPLE
- **Steps:** Compare item ids with element ids.
- **Expected:** Item ids are exactly the ids of the sources, contactors, buses and TRUs, plus `<bus>_switch` for each crew-switched bus. Each has `x`, `y`, `width`, `height`. Each switch box touches or lies within 16 px of its bar.

#### TC-LAY-003 — Layer order

- **Fixture:** FX-SAMPLE, FX-ROLES
- **Steps:** Group items as sources, source contactors, AC main buses, other AC buses, TRUs, DC buses. Compare `y`.
- **Expected:** In both fixtures, by the top-left `y`, the largest `y` of each group is below the smallest `y` of the next. FX-ROLES places ACO with ACE and ACM.

#### TC-LAY-004 — TRU contactors above and below

- **Fixture:** FX-SAMPLE
- **Steps:** For each TRU compare `y`.
- **Expected:** input contactor `y` < TRU `y` < output contactor `y`.

#### TC-LAY-005 — DC bus role order

- **Fixture:** FX-SAMPLE, FX-ROLES
- **Steps:** Compare `y` of DC buses.
- **Expected:** Sample: DC BUS 1 ≤ DC ESS ≤ DC BAT. FX-ROLES: DC1 ≤ DCE ≤ each of DCM, DCB, DCO.

#### TC-LAY-006 — Source layer order

- **Fixture:** FX-REVERSE
- **Steps:** Read `x` of the source items.
- **Expected:** G1 < G2 < APU < RAT_AC < BAT.

#### TC-LAY-007 — Any number of engines

- **Fixture:** FX-ENG(2), FX-ENG(4), FX-ENG(8), FX-ENG(12)
- **Steps:** `layout` each.
- **Expected:** One item per generator and no two boxes overlapping.

#### TC-LAY-008 — No load or breaker items

- **Fixture:** FX-SAMPLE
- **Steps:** Compare item ids and kinds with load ids.
- **Expected:** No item id is a load id, and no kind is `load` or `breaker`.

#### TC-LAY-009 — Layout has no web dependency

- **Fixture:** None
- **Steps:** In a fresh subprocess, import `ela.layout` and read `sys.modules`.
- **Expected:** `ela/layout.py` exists, and `fastapi`, `starlette`, `uvicorn` are absent.

#### TC-LAY-010 — Connectors join the right items orthogonally

- **Fixture:** FX-SAMPLE
- **Steps:** For each contactor, find connectors to its `from` and `to` items. Check each point pair.
- **Expected:** Both exist. Each polyline starts and ends on those items' bounds. Each consecutive pair shares `x` or `y`.

#### TC-LAY-011 — Same-layer tie stays level

- **Fixture:** FX-BATCH
- **Steps:** Compare T12 with AC1 and AC2.
- **Expected:** T12's centre `y` equals the bars' centre `y`, and its `x` lies between them.

#### TC-LAY-012 — Cross-layer tie sits between its buses

- **Fixture:** FX-ROLES, FX-SAMPLE
- **Steps:** Compare T1E with AC1 and ACE, then any sample tie between an AC main bus and AC ESS.
- **Expected:** The contactor's `y` lies between the two buses' `y`.

#### TC-LAY-013 — Barycentre does not add crossings

- **Fixture:** FX-SAMPLE, FX-CROSS, FX-ENG(4), FX-50
- **Steps:** Count straight-line inversions between adjacent layers, for the returned layout and for the same layers in definition order, with the source layer in its fixed order in both counts.
- **Expected:** Returned count ≤ definition-order count in all 4. FX-CROSS: returned count 0, definition-order count at least 1.

#### TC-LAY-014 — Independent chains do not cross

- **Fixture:** FX-CHAINS
- **Steps:** Intersect all connector segments from different chains.
- **Expected:** Zero crossings.

#### TC-LAY-015 — No overlaps and no connector through an item

- **Fixture:** FX-SAMPLE, FX-50
- **Steps:** Test all item pairs, then all connector segments against non-end items.
- **Expected:** No overlap, with a crew switch touching its own bar not counting, and no connector crosses a non-end item.

#### TC-LAY-016 — Item size at fit scale

- **Fixture:** FX-50
- **Steps:** Compute the scale that fits the layout's extents in a 1000 × 560 px drawing area, as min(1000 ÷ extent width, 560 ÷ extent height), and apply it to non-bus items.
- **Expected:** 50 items, and every non-bus width and height is at least 16 px.

#### TC-LAY-018 — Item size holds in the real drawing area

- **Fixture:** H-PAGE, FX-50
- **Steps:** Open at the initial view. Measure `#schematic`, and read each non-bus item's rendered size.
- **Expected:** `#schematic` measures at least 1000 × 560 px, and every non-bus item's rendered width and height are at least 16 px.

### C-API

#### TC-API-001 — List definitions by file stem

- **Fixture:** H-CLIENT, H-DEFS holding `generic_twin.json`, `other.json`, `notes.txt` and an unparsable `raw.json`
- **Steps:** `GET /api/definitions`.
- **Expected:** 200, holding `generic_twin`, `other` and `raw`, and not `notes`. The `raw` entry has `aircraft` and `revision` null.

#### TC-API-002 — Definition with layout and warnings

- **Fixture:** H-CLIENT, H-DEFS with FX-SAMPLE and FX-WARN
- **Steps:** `GET /api/definitions/generic_twin` and `/fx_warn`.
- **Expected:** 200 with definition, layout items and connectors, and a warning list. FX-WARN's list has the `$.zzz` warning.

#### TC-API-003 — Invalid stored file is refused with all errors

- **Fixture:** H-CLIENT, H-DEFS with FX-THREEERR and a file `raw.json` holding `{not json`
- **Steps:** `GET /api/definitions/fx_threeerr`, then `/raw`.
- **Expected:** First: 422, 3 errors each with path and message, and no layout in the body. Second: 422 with an error at `$`.

#### TC-API-004 — Unknown id gives 404 on every route

- **Fixture:** H-CLIENT, H-DEFS
- **Steps:** `GET`, `POST analyse`, `POST batch`, `GET batch/export?format=csv` on `nosuch`.
- **Expected:** 404 on all four.

#### TC-API-005 — Path traversal in the id

- **Fixture:** H-CLIENT, H-DEFS, with a valid definition stored one folder above H-DEFS
- **Steps:** `GET /api/definitions/..%2Foutside`, then `/..%5Coutside`, then `/%2e%2e%2foutside`.
- **Expected:** 404 or another 4xx on all, and the outside file's content appears in no response.

#### TC-API-006 — Valid upload is stored and answered 201

- **Fixture:** H-CLIENT, H-DEFS. Upload FX-WARN as `new_def.json`
- **Steps:** `POST /api/definitions`, then `GET /api/definitions`.
- **Expected:** 201, body holding id `new_def` and the `$.zzz` warning. `new_def.json` exists in H-DEFS, and `new_def` is listed.

#### TC-API-022 — Definitions folder comes from ELA_DEFINITIONS_DIR

- **Fixture:** `uvicorn ela.api:app` subprocess, a temporary folder holding FX-SINGLE
- **Steps:** Hash the repository `definitions/` folder. Start with `ELA_DEFINITIONS_DIR` set to the temporary folder, list, and upload FX-WARN. Stop. Hash again. Start with the variable unset, from a working directory outside the repository, and list.
- **Expected:** With the variable set: the list holds `fx_single` and not `generic_twin`, and the upload lands in the temporary folder. `definitions/` hash unchanged. With it unset: the list holds `generic_twin`.

#### TC-API-023 — Analyse body and upload field names

- **Fixture:** H-CLIENT, H-DEFS with FX-SINGLE. Upload FX-SINGLE as `field_test.json`
- **Steps:** `POST .../fx_single/analyse` with `{"states": {"G1": "failed"}}`. `POST /api/definitions` as multipart with field `file`.
- **Expected:** 200 with G1 `failed` in the response. 201.

#### TC-API-007 — Invalid upload stores nothing

- **Fixture:** H-CLIENT, H-DEFS. Upload FX-THREEERR, then a file holding `{not json`, as `bad.json`
- **Steps:** `POST /api/definitions` for each. List the folder.
- **Expected:** FX-THREEERR: 422 with 3 errors, each with path and message. Unparsable file: 422 with an error at `$`. Folder listing unchanged after both.

#### TC-API-008 — Path-traversal, empty and reserved file names on upload

- **Fixture:** H-CLIENT, H-DEFS. Upload FX-SINGLE under each of `../../evil name.json`, `..\..\evil2.json`, `/abs/evil3.json`, then `.json`, `../.json`, `nul.json`, `NUL.json`, `con.json`, `COM1.json`, `lpt9.json`
- **Steps:** `POST /api/definitions` for each. List H-DEFS and its parent.
- **Expected:** The first three give 201, stored as `evil_name.json`, `evil2.json` and `evil3.json`, each matching `^[A-Za-z0-9_-]+\.json$` inside H-DEFS. The rest give 422, with empty or Windows-reserved stems in any case, and store nothing. Nothing is written outside H-DEFS.

#### TC-API-009 — Name collisions

- **Fixture:** H-CLIENT, H-DEFS. FX-SINGLE named `generic_twin.json`, then `GENERIC_TWIN.json`, then FX-THREEERR named `generic_twin.json`, then `a b.json` followed by `a_b.json`
- **Steps:** `POST` each. Compare the stored `generic_twin.json` bytes.
- **Expected:** 409, and 409 again by case-insensitive comparison, with bytes unchanged. 422, as validation comes first. 201 then 409, as both sanitise to `a_b.json`.

#### TC-API-010 — Analyse returns the engine result

- **Fixture:** H-CLIENT, H-DEFS with FX-BATCH
- **Steps:** `POST .../fx_batch/analyse` with `{"states": {"G1": "failed", "T12": "closed"}}`.
- **Expected:** 200, body equal to the serialised `analyse` result. D(G2) = 2000/1800/1600.

#### TC-API-011 — Analyse response fields

- **Fixture:** H-CLIENT, H-DEFS with FX-BATCH
- **Steps:** `POST analyse` with the S5 states, then with the S4 states.
- **Expected:** S5: per-element energisation, demand, capacity, verdict FAIL, 3 overloads, empty errors. S4: 1 unpowered load. Each named field is present in both, with `warnings` a list.

#### TC-API-012 — Bad analyse body

- **Fixture:** H-CLIENT, H-DEFS with FX-SINGLE
- **Steps:** `POST analyse` with `{"GHOST": "failed"}` in `states`. Then with `{"G1": "closed"}`.
- **Expected:** 422 in both, each with a path and message.

#### TC-API-013 — Analyse is stateless

- **Fixture:** H-CLIENT, H-DEFS with FX-BATCH
- **Steps:** `POST analyse` with `{"G1": "failed"}`, then with `{}`. Compare the second with a fresh client's first call.
- **Expected:** Equal. G1 energised, S1 figures.

#### TC-API-014 — Batch route

- **Fixture:** H-CLIENT, H-DEFS with FX-SAMPLE
- **Steps:** `POST .../generic_twin/batch`.
- **Expected:** 200, equal to `run_batch` serialised.

#### TC-API-015 — Last batch results by definition, in memory only

- **Fixture:** H-SERVER, H-DEFS with FX-BATCH and FX-ALLPASS
- **Steps:** Run batch on both, and export JSON for each. Restart the server and export again.
- **Expected:** Each export holds its own definition's 5 and 2 scenarios. 404 after restart.

#### TC-API-016 — Export formats

- **Fixture:** H-CLIENT, H-DEFS with FX-BATCH, after a batch
- **Steps:** `GET .../batch/export?format=csv`, then `format=json`.
- **Expected:** 200 with bodies equal to the batch runner's serialisations. Content types `text/csv` and `application/json`.

#### TC-API-017 — Export refusals

- **Fixture:** H-CLIENT, H-DEFS with FX-BATCH
- **Steps:** Export `csv` and `json` before a run. Run, then export `xml`, then export with no `format`.
- **Expected:** 404 twice. 422 twice.

#### TC-API-018 — FastAPI app serves the front end

- **Fixture:** H-CLIENT
- **Steps:** Import `ela.api`. `GET /`, `/app.js`, `/schematic.js`, `/batch.js`, `/styles.css`.
- **Expected:** `ela.api.app` is a `fastapi.FastAPI`. `/` returns `web/index.html`. Each other file is 200 with the file's content.

#### TC-API-019 — One command, loopback only

- **Fixture:** Plain `uvicorn ela.api:app` subprocess with no host option
- **Steps:** `GET /` and `/api/definitions` on 127.0.0.1. Try TCP to the machine's first non-loopback address. List the process's listening sockets through `netstat`.
- **Expected:** 200 on both. The non-loopback connection is refused. The only listening address is 127.0.0.1.

#### TC-API-020 — No authentication

- **Fixture:** H-CLIENT
- **Steps:** Call every route in `app.routes` with no credentials.
- **Expected:** No response is 401 or 403.

#### TC-API-021 — No route edits a definition

- **Fixture:** H-CLIENT
- **Steps:** List `app.routes` under `/api`.
- **Expected:** Exactly the 6 of `docs/spec.md` §7.2, and none uses `PUT`, `PATCH` or `DELETE`.

### C-WEBINT

#### TC-WIN-001 — Definition list

- **Fixture:** H-PAGE, H-DEFS with FX-SAMPLE and FX-SINGLE
- **Steps:** Read `#definition-select`. Add FX-ALLPASS to the folder and reload. Choose `generic_twin`.
- **Expected:** Both ids are listed, `fx_allpass` appears after the reload, and `#schematic` draws its items.

#### TC-WIN-002 — Upload control

- **Fixture:** H-PAGE, file FX-SINGLE as `up1.json`
- **Steps:** Set `#definition-upload`. Record navigations.
- **Expected:** One `POST /api/definitions`, `up1` appears in `#definition-select`, with no page navigation.

#### TC-WIN-003 — Upload conflict message

- **Fixture:** H-PAGE, file FX-SINGLE as `generic_twin.json`
- **Steps:** Upload it.
- **Expected:** `#message` contains `generic_twin.json`, and the option list is unchanged.

#### TC-WIN-004 — Validation errors are listed

- **Fixture:** H-PAGE, H-DEFS with FX-THREEERR
- **Steps:** Select `fx_threeerr`. Separately upload FX-THREEERR as `bad.json`.
- **Expected:** 3 visible entries each time, each with its path and message.

#### TC-WIN-005 — No schematic for a rejected definition

- **Fixture:** H-PAGE, H-DEFS with FX-THREEERR and FX-SINGLE
- **Steps:** Select `fx_single`, then `fx_threeerr`.
- **Expected:** `#schematic` holds no `[data-id="G1"]`, and `#status-verdict` is empty.

#### TC-WIN-006 — Warnings are displayed

- **Fixture:** H-PAGE, H-DEFS with FX-WARN
- **Steps:** Select `fx_warn`.
- **Expected:** The schematic is drawn, and `#warnings` shows `$.zzz` and a message.

#### TC-WIN-007 — Opens at defaults

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Select `generic_twin` and read the `analyse` log.
- **Expected:** The body's `states` is empty, and the DC BAT switch shows `on`.

#### TC-WIN-008 — Switching definition resets the view

- **Fixture:** H-PAGE, FX-BATCH, FX-SINGLE
- **Steps:** Open FX-BATCH, click G1, choose the 5 s band, pan. Select FX-SINGLE, then FX-BATCH again.
- **Expected:** Default states, Continuous, no scenario selected and the initial view, both times.

#### TC-WIN-009 — SVG at API coordinates

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Read the layout from `GET /api/definitions/generic_twin`. For each item, read `getBoundingClientRect` and undo the view transform.
- **Expected:** `#schematic` is an `svg`, and each position equals the layout within 1 px.

#### TC-WIN-010 — Icons by kind

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Inspect the SVG of one element per kind.
- **Expected:** Generators hold a `circle` and text `G`. Battery, TRU and bus use distinct symbols. Each bus bar is wider than tall.

#### TC-WIN-011 — Crew switch symbol

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Read the geometry of `[data-id="<bus>_switch"]` for the DC BAT bus on `on` and `off`. Search other buses.
- **Expected:** Geometry differs, and no other bus has a switch.

#### TC-WIN-012 — No load or breaker drawn

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Search the SVG for each load id and name.
- **Expected:** No element id or text equals any.

#### TC-WIN-013 — Pan and zoom

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Drag 100 px right on empty canvas. Wheel in, then out.
- **Expected:** An item moves 100 px ± 1 px. Its on-screen size increases, then decreases.

#### TC-WIN-014 — A drag is not a click

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Drag 100 px starting on a generator and ending on empty canvas. Drag 100 px starting on empty canvas and ending on a generator. Press on the generator and release 3 px away.
- **Expected:** No analyse request and no state change for both drags. The 3 px press and release toggles the generator, with one analyse request.

#### TC-WIN-015 — Readable at 1366 × 768

- **Fixture:** H-PAGE, H-DEFS with FX-50
- **Steps:** Select `fx_50`. Measure `#schematic`. Read boxes and text sizes at the initial view.
- **Expected:** `#schematic` measures at least 1000 × 560 px. Every item's box lies inside it. Every `text` is at least 10 px high.

#### TC-WIN-016 — Green when energised

- **Fixture:** H-PAGE, FX-COLOURS
- **Steps:** Read computed colour of AC1, G1, TRU1 and `C_G1`.
- **Expected:** Hue 90° to 150° for each.

#### TC-WIN-017 — Dark grey when de-energised

- **Fixture:** H-PAGE, FX-COLOURS
- **Steps:** Read computed colour of AC3 and T13, and the background.
- **Expected:** Saturation at most 15 %, and contrast at least 3:1 against the background.

#### TC-WIN-018 — Amber in any band

- **Fixture:** H-PAGE, FX-COLOURS
- **Steps:** Read AC2's computed colour under each of the 3 bands.
- **Expected:** Hue 30° to 50° all three times, though only transient fails.

#### TC-WIN-019 — Failure mark

- **Fixture:** H-PAGE, FX-COLOURS
- **Steps:** Inspect G3, TRU3, TRU2, RAT_AC.
- **Expected:** G3 and TRU3 are dark grey with a visible mark. TRU2 and RAT_AC have no mark.

#### TC-WIN-020 — Contactor state by shape

- **Fixture:** H-PAGE, FX-COLOURS
- **Steps:** Read T13's path geometry when open, click it, and read again.
- **Expected:** The `d` geometry differs, regardless of colour.

#### TC-WIN-021 — Bus labels show throughput and only on live buses

- **Fixture:** H-PAGE, H-DEFS with FX-THROUGH
- **Steps:** Read `[data-label]` of AC1, AC2, DC1 in Continuous. Then click G1.
- **Expected:** AC1: 115 V, 7.25 A, 2.50 kW (demand 2500 W, not own 1000 W). DC1: 28 V, 30.36 A, 850 W. After the click, no bus shows a value label.

#### TC-WIN-022 — Band selector

- **Fixture:** H-PAGE, FX-SINGLE, then FX-SINGLE with label `Peak` on `transient`
- **Steps:** Read `#band-select`. Choose Transient. Read the log.
- **Expected:** Options Transient, 5 s, Continuous, with Continuous selected. AC1 shows 4.00 kW. No analyse request is sent. The second copy lists `Peak`.

#### TC-WIN-023 — Power display threshold

- **Fixture:** H-PAGE, H-DEFS with FX-DISPLAY
- **Steps:** Read the label power on AC1, AC2, AC3, AC5.
- **Expected:** `999 W`, `1.00 kW`, `12.34 kW`, `1.00 kW`. The last is 999.6 W, which would otherwise show as `1000 W`, so the threshold applies after rounding.

#### TC-WIN-024 — Failed bands are named on the label

- **Fixture:** H-PAGE, H-DEFS with FX-TRAN
- **Steps:** Read AC2's label under Continuous, then Transient. Read AC1 under Transient. Read the labels of G4 and `C_G3` under Continuous.
- **Expected:** AC2 names Transient and 5 s, then 5 s alone. AC1 names no other band, as only the shown band failed. G4 names Transient and 5 s. `C_G3` has a label only because it is overloaded, naming Transient. Bands are named by their labels, as DD-010 gives them.

#### TC-WIN-025 — Tooltip values

- **Fixture:** H-PAGE, FX-TRAN
- **Steps:** Hover AC1, then `C_G1`.
- **Expected:** AC1: 12 values equal to the analyse response. Remaining margin is shown in W with its percentage, transient reading `-100 W` and `-10 %` with ASCII hyphen-minus. `C_G1`: its demand, with `no capacity` in place of capacity and margin.

#### TC-WIN-026 — Hover opens the tooltip with name and role

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Hover one source, bus, TRU, contactor and crew switch. Hover AC ESS and compare with the analyse response.
- **Expected:** Each opens that element's `#tooltip`. AC ESS shows its name, `essential` and its own-load power in each band.

#### TC-WIN-027 — Touch tap

- **Fixture:** H-PAGE in a `has_touch` context, FX-SAMPLE
- **Steps:** Tap a bus. Tap a contactor.
- **Expected:** The bus tooltip opens, with no state change. The contactor toggles, and its tooltip opens showing the new state.

#### TC-WIN-028 — Source and TRU load

- **Fixture:** H-PAGE, FX-DISPLAY, FX-SINGLE, FX-COLOURS
- **Steps:** Read G4's label on FX-DISPLAY. On FX-SINGLE choose the Transient band and read TRU1's label. Read G3's label on FX-COLOURS.
- **Expected:** G4 shows `45.00 kW` and `50 %`. TRU1 at 28.33 % shows `1.70 kW` and `28.33 %`. G3, failed, shows neither.

#### TC-WIN-029 — Toggle sources, TRUs and contactors

- **Fixture:** H-PAGE, FX-ALLKINDS
- **Steps:** Click G1, APU, BAT, TRU1 twice each. Click RAT_AC twice. Click `C_G1`, `TRU1_IN` and T1E twice each.
- **Expected:** `data-state` goes `failed`, `operative`. RAT_AC goes `available`, `unavailable`, with RAT_DC staying `unavailable`. Contactors go `open`, `closed`.

#### TC-WIN-030 — Toggle crew switch

- **Fixture:** H-PAGE, FX-ALLKINDS
- **Steps:** Hover DCB and read its tooltip. Click `DCB_switch`, then read the tooltip. Click again, then read it.
- **Expected:** Tooltip own-load power 34 W in each band. Then `off` with own-load power 0 W. Then `on` with 34 W.

#### TC-WIN-031 — Bus bars are not clickable

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Click each bus bar away from any switch symbol.
- **Expected:** No analyse request.

#### TC-WIN-032 — One analyse per click

- **Fixture:** H-PAGE, FX-SINGLE
- **Steps:** Click G1 and wait for network idle.
- **Expected:** Exactly one request with `{"states": {"G1": "failed"}}`, and AC1 is dark grey with no further input.

#### TC-WIN-033 — Click to redraw within a second

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Click 20 times across generators and contactors, timing click to completed redraw.
- **Expected:** Slowest ≤ 1000 ms.

#### TC-WIN-034 — No editing controls

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Search for inputs other than the file, band and selection controls. Hash the file, click 20 elements, hash again.
- **Expected:** None found. Hash unchanged.

#### TC-WIN-035 — Reset keeps the band and clears the scenario

- **Fixture:** H-PAGE, FX-ALLKINDS with scenario R1 `{"G1": "failed"}`
- **Steps:** Fail G1, open T1E, switch DCB off, choose the 5 s band, press `#reset`. Then select R1, press `#reset`.
- **Expected:** After each Reset, every `data-state` and the verdict equal a fresh open, including `DCB_switch` `on`. `#band-select` stays on 5 s with labels in that band, and `#scenario-select` shows no scenario.

#### TC-WIN-036 — Load scenario

- **Fixture:** H-PAGE, FX-BATCH
- **Steps:** Read `#scenario-select`. Click G2 to fail it, and choose S5.
- **Expected:** 5 entries by name. G2 is `operative` again, as S5 does not list it. Verdict FAIL as in the batch, and T13 is `closed`.

#### TC-WIN-046 — A schematic click clears a stale scenario selection

- **Fixture:** H-PAGE, FX-BATCH
- **Steps:** Choose S5. Click the AC1 bus bar. Click T12. Read the state of T13. Choose S5 again.
- **Expected:** The bar click changes no state, and S5 stays selected. The T12 click leaves no scenario selected, with T12 and T13 both `closed`. Choosing S5 again selects it and returns T12 to `open`.

#### TC-WIN-037 — Status panel verdict and overloads

- **Fixture:** H-PAGE, FX-BATCH, FX-SAMPLE
- **Steps:** Read `#status-verdict` at FX-BATCH default. Choose S5. Then the sample default, then a designed-to-fail scenario.
- **Expected:** PASS, then FAIL with 3 entries, each with element, band, demand with margin and capacity: G1 `Transient` 3300 / 3000, G1 `Continuous` 2200 / 2000, T13 `Transient` 2200 / 1500, each band shown by its label. Sample PASS, then FAIL.

#### TC-WIN-038 — Status panel configuration error

- **Fixture:** H-PAGE, FX-BATCH
- **Steps:** Click T12 to close it.
- **Expected:** FAIL, and `#status-list` has a message containing "AC sources paralleled".

#### TC-WIN-047 — Status panel paralleling on the sample

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Open at default, with both engine generators live. Click the `bus_tie` joining AC BUS 1 and AC BUS 2 to close it.
- **Expected:** FAIL, and `#status-list` has a message containing "AC sources paralleled".

#### TC-WIN-039 — Status panel essential loads

- **Fixture:** H-PAGE, FX-ESS, FX-SAMPLE
- **Steps:** On FX-ESS click G1 to fail it, then click `DCS_switch` to off. On the sample click the DC BAT bus's switch to off.
- **Expected:** FX-ESS: LE1 and LE2, then LE1, LE2 and LE3, listed by name. Sample: each essential load on the DC BAT bus is listed by name.

#### TC-WIN-040 — Status panel mesh warning

- **Fixture:** H-PAGE, H-DEFS with FX-RING
- **Steps:** Open `fx_ring`.
- **Expected:** The panel shows `meshed_island` naming T23, and the verdict stays PASS.

#### TC-WIN-041 — No framework

- **Fixture:** None
- **Steps:** Automated scan of `web/*` for `react`, `vue`, `angular`, `svelte`, and for `<script src>` to any external host.
- **Expected:** No match.

#### TC-WIN-042 — ES modules with no build step

- **Fixture:** None
- **Steps:** Automated check of `web/index.html` and a recursive search of the repository, excluding `.venv`.
- **Expected:** `app.js` is loaded with `type="module"`. No `package.json`, `webpack`, `vite`, `rollup`, `esbuild` or `tsconfig` file exists. `web/` has no `package.json`.

#### TC-WIN-043 — Front-end files

- **Fixture:** H-SERVER
- **Steps:** Check the 4 files on disk, and `GET` each.
- **Expected:** All exist, and all are served with 200.

#### TC-WIN-044 — Interactive front end has browser tests

- **Fixture:** None
- **Steps:** Map each C-WEBINT requirement on page behaviour to its collected tests. Run `pytest tests -m "e2e and not meta"` in a subprocess.
- **Expected:** Each has at least one `e2e` test, and the selection passes. L2-WIN-048 to L2-WIN-052 are not page behaviour and are excluded. L2-WIN-053 is included.

#### TC-WIN-045 — Playwright is dev-only

- **Fixture:** None
- **Steps:** Parse `pyproject.toml`. Search `web/`.
- **Expected:** No `playwright` in `[project].dependencies`, and it is in `[dependency-groups].dev`. No file in `web/` mentions it.

#### TC-WIN-048 — Published DOM hooks

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Open the sample. Count each id. Walk the layout items.
- **Expected:** `definition-select`, `definition-upload`, `band-select`, `scenario-select`, `reset`, `status-verdict`, `status-list`, `tooltip`, `message`, `warnings` and `schematic` each exist exactly once. Each layout item has a `[data-id]` group with a `data-state` attribute. Each energised bus has a `[data-label]`.

### C-WEBBAT

#### TC-WBT-001 — Run all scenarios

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Press `#run-batch`.
- **Expected:** One `POST .../fx_batch/batch`, and the table is filled with 5 rows.

#### TC-WBT-002 — Results table

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run. Read all cells.
- **Expected:** Every cell equals the FX-BATCH table, including `56`, `12` and `-46.67`. All program output, including negative numbers in the UI, CLI and exports, uses ASCII hyphen-minus, so the last is U+002D and not U+2212.

#### TC-WBT-003 — Empty marker for null worst values

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run. Read rows S3 and S4.
- **Expected:** `—` in the worst element, band and margin cells, and no `null` or `undefined` text.

#### TC-WBT-004 — Table cleared on definition switch

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH and FX-SINGLE
- **Steps:** Run, then select FX-SINGLE.
- **Expected:** No result rows.

#### TC-WBT-005 — batch.js is an ES module

- **Fixture:** H-PAGE
- **Steps:** Read network log. Scan `web/batch.js`.
- **Expected:** `/batch.js` loads with 200 through an `import`, not a classic script tag, with no framework reference.

#### TC-WBT-006 — Batch front end has browser tests

- **Fixture:** None
- **Steps:** Map each C-WEBBAT requirement on page behaviour to its collected tests. Run `pytest tests -m "e2e and not meta"` in a subprocess.
- **Expected:** Each has at least one `e2e` test, and the selection passes.

#### TC-WBT-007 — Expanded detail

- **Fixture:** H-PAGE, FX-BATCH, FX-RING
- **Steps:** Run FX-BATCH. Expand S5, S3, S4. Run FX-RING and expand M1.
- **Expected:** S5 lists the 3 element-band pairs. S3 lists the "AC sources paralleled" message. S4 lists LA1. M1 lists its `meshed_island` warning naming T23.

#### TC-WBT-008 — Expand control is separate

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run, expand S5, and read the analyse log and `#scenario-select`.
- **Expected:** Detail shows, no analyse request is sent, and no scenario is selected.

#### TC-WBT-009 — Row opens the scenario

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run. Click the S5 row outside the expand control.
- **Expected:** The schematic is shown with S5 selected and verdict FAIL.

#### TC-WBT-010 — Export downloads

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run. Activate `#export-csv` and `#export-json`, capturing downloads.
- **Expected:** Both contents equal the API's exports.

#### TC-WBT-011 — Export disabled before a run

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH and FX-SINGLE
- **Steps:** Read both controls. Run. Read again. Select FX-SINGLE. Read again. Select FX-BATCH again. Read again.
- **Expected:** Disabled, enabled, disabled, disabled, as the table shows no results on returning.

#### TC-WBT-012 — Published batch DOM hooks

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Open the sample. Count each id.
- **Expected:** `run-batch`, `batch-table`, `export-csv` and `export-json` each exist exactly once.

### C-DOCS

#### TC-DOC-001 — Installation section

- **Fixture:** Fresh clone in a temporary folder
- **Steps:** Find the installation heading in `README.md`. Run its fenced commands.
- **Expected:** The heading exists, its commands use `uv`, and each exits 0.

#### TC-DOC-002 — Running section

- **Fixture:** Fresh clone, after the installation steps
- **Steps:** Run the fenced start command. Fetch the address given.
- **Expected:** The section holds `uvicorn ela.api:app`, and the address answers 200 with the page.

#### TC-DOC-003 — Batch command reference

- **Fixture:** None
- **Steps:** Parse the running section.
- **Expected:** It holds `ela batch`, `--csv`, `--json`, and exit codes 0, 1, 2 with each meaning.

#### TC-DOC-004 — JSON format reference

- **Fixture:** None
- **Steps:** Collect every property name from the model's JSON schema. Search the reference section.
- **Expected:** All are present, and the section states watts, volts and decimals.

#### TC-DOC-005 — Band meanings and ordering

- **Fixture:** None
- **Steps:** Search the reference section.
- **Expected:** `transient` with inrush peak, `short_term` with first 5 seconds, `continuous` with steady state. It states the tool does not enforce `transient ≥ short_term ≥ continuous`.

#### TC-DOC-006 — Adding an aircraft

- **Fixture:** None
- **Steps:** Find the section.
- **Expected:** It exists, and names the `definitions/` folder and the validation step.

### L1 system tests

#### TC-SYS-001 — One file is the only input

- **Fixture:** H-DEFS holding only FX-SAMPLE, H-SERVER, then CLI
- **Steps:** `POST .../generic_twin/batch`. Run `ela batch` on a copy of the file in an empty temporary folder.
- **Expected:** Results for all scenarios from both, with no other data file read.

#### TC-SYS-002 — Units through the API

- **Fixture:** H-CLIENT, FX-MARGIN. M: G1 cap 2000
- **Steps:** `POST analyse` with empty states.
- **Expected:** AC1 demand 1000 W, and G1 demand with margin 1000 × 1.10 = 1100 W.

#### TC-SYS-003 — Engine count has no limit and the APU is optional

- **Fixture:** FX-ENG(2), FX-ENG(4), FX-ENG(8), FX-ENG(12), FX-SINGLE, FX-APU, each with one scenario `{}`
- **Steps:** Run `ela batch` on each, and `GET` and analyse each through the API.
- **Expected:** Exit code 0, and 200 responses, for all six.

#### TC-SYS-004 — Every component kind and state

- **Fixture:** H-CLIENT, FX-ALLKINDS
- **Steps:** Analyse once with each listed state of each stateful element, one element at a time.
- **Expected:** 200 each time, and the response's state for that element equals the state sent.

#### TC-SYS-005 — Invalid definitions are not analysed or opened

- **Fixture:** FX-SINGLE with `M: $.loads[0].bus = "NOBUS"`, stored as `fx_bad.json`. H-PAGE
- **Steps:** Run `ela batch`. `POST analyse` through the API. Select `fx_bad` in the browser.
- **Expected:** CLI exit 2 with no scenario lines. API 422 with no analysis result. The browser shows the errors and draws no schematic.

#### TC-SYS-006 — All errors in one response

- **Fixture:** FX-FIVE, FX-MANY
- **Steps:** Upload each through the API.
- **Expected:** 422 once each, with at least one error per fault, each with a locating path and a non-empty message.

#### TC-SYS-007 — Warnings do not block

- **Fixture:** H-PAGE, H-DEFS with FX-WARN
- **Steps:** Select `fx_warn`.
- **Expected:** The definition opens, and the warning naming `zzz` is displayed.

#### TC-SYS-008 — Bad state in scenario and in request

- **Fixture:** FX-SINGLE
- **Steps:** Add scenario with `{"GHOST": "failed"}` and upload. Then, on a valid copy, `POST analyse` with `{"GHOST": "failed"}` and with `{"G1": "closed"}`.
- **Expected:** Upload 422 at `$.scenarios[0].states.GHOST`. Analyse 422 for both.

#### TC-SYS-009 — Bands are separate and need no ordering

- **Fixture:** H-CLIENT, FX-SINGLE-E. M: LA = 100/200/300
- **Steps:** `POST analyse` with empty states.
- **Expected:** Accepted with an empty warning list. AC1 demand 100 + 2000 = 2100, 200 + 1600 = 1800, 300 + 1000 = 1300, three different results.

#### TC-SYS-010 — Energisation by path through ties and TRUs

- **Fixture:** H-CLIENT, FX-CHAIN, FX-BAT
- **Steps:** On FX-CHAIN analyse `{"G1": "failed"}`, then `{}`, then `{"T12": "open"}`. Repeat with G1 at the AC3 end. On FX-BAT analyse `{"G1": "failed"}`.
- **Expected:** All dead, then all live, then only the source side live. From AC3, T12 open leaves AC1 dead. FX-BAT: DC1 energised, AC1 de-energised.

#### TC-SYS-011 — Load counting and crew switch start state

- **Fixture:** H-CLIENT, FX-CREW, with one scenario not listing DCS and one setting it `off`
- **Steps:** Analyse `{}`, `{"DCS": "off"}`, `{"BAT": "failed"}`. Run the batch.
- **Expected:** DCS own 200/150/100, 0, 0. Default switch state `on`. The two scenario results show `on` and `off`.

#### TC-SYS-012 — Throughput and upstream propagation

- **Fixture:** H-CLIENT. FX-CHAIN with AC3, T23 and L3 removed, L1 = 1000, L2 = 500. FX-SINGLE with LA removed, LD = 850
- **Steps:** `POST analyse` on each.
- **Expected:** FX-CHAIN: AC1 demand 1000 + 500 = 1500, own-load power 1000. FX-SINGLE: G1 demand 850 ÷ 0.85 = 1000 W.

#### TC-SYS-013 — DC sharing through the API

- **Fixture:** H-CLIENT, FX-TWO-TRU. M: LD = 900
- **Steps:** `POST analyse`.
- **Expected:** TRU1 600 W and TRU2 300 W in each band.

#### TC-SYS-014 — Battery priority through the API

- **Fixture:** H-CLIENT, FX-BAT
- **Steps:** Analyse `{}`, then `{"TRU1": "failed"}`.
- **Expected:** BAT 0, then 850.

#### TC-SYS-015 — Paralleling fails the configuration

- **Fixture:** H-CLIENT, FX-BATCH
- **Steps:** Analyse with `{"T12": "closed"}`.
- **Expected:** FAIL, with a configuration error containing "AC sources paralleled".

#### TC-SYS-016 — Mesh warning through the API

- **Fixture:** H-CLIENT, FX-RING
- **Steps:** `POST analyse`. Then run `ela batch`.
- **Expected:** The analyse response has a warning naming T23. The CLI run's standard error has a `meshed_island` line naming T23.

#### TC-SYS-017 — Capacity check through the API

- **Fixture:** H-CLIENT, FX-MARGIN, FX-OVERRIDE, and FX-OVERRIDE with AC1 capacity removed
- **Steps:** Analyse FX-MARGIN at cap 1100, at cap 1099, and at L1 = 3000, cap 3300. Analyse both FX-OVERRIDE copies.
- **Expected:** Not overloaded, overloaded, not overloaded. G1 with margin 1.25 × 1000 = 1250, AC1 with margin 1.10 × 1000 = 1100. In the second copy AC1 is not overloaded.

#### TC-SYS-018 — Verdict conditions and essential loads

- **Fixture:** H-CLIENT, FX-BATCH, FX-ESS
- **Steps:** `POST batch` on FX-BATCH. Analyse FX-ESS with `{"G1": "failed", "DCS": "off"}`.
- **Expected:** S1 PASS, S5 FAIL by overload, S3 FAIL by error, S4 FAIL by essential load. FX-ESS: FAIL with LE1, LE2 and LE3 listed by name.

#### TC-SYS-019 — Remaining margin and worst element

- **Fixture:** H-CLIENT, FX-BATCH, and FX-MARGIN with G1 cap 2000
- **Steps:** Analyse FX-MARGIN. Run batch on FX-BATCH.
- **Expected:** G1 remaining 900 W and 45 %. S2 worst G2 continuous 12 %. S5 worst T13 transient at `-46.67`.

#### TC-SYS-020 — Voltage, power and current

- **Fixture:** H-CLIENT, BAT cap 5000 → DC1 with L 2800 W, and G1 cap 5000 → AC1 with L 3450 W
- **Steps:** `POST analyse` on each.
- **Expected:** 28 V, 2800 W, 100 A. 115 V, 3450 W, 3450 ÷ (3 × 115) = 10 A per phase.

#### TC-SYS-021 — Static results with no time or endurance quantity

- **Fixture:** H-CLIENT, FX-BATCH, FX-BAT2
- **Steps:** Repeat one analyse request on FX-BATCH 3 times. Read the analyse route's request schema from `/openapi.json`. Analyse FX-BAT2 and walk the JSON.
- **Expected:** Identical bodies. No request field named for time, duration or step. No amp-hour, endurance or depletion key or text.

#### TC-SYS-022 — No reconfiguration or shedding, and fixed load power

- **Fixture:** H-CLIENT, FX-BATCH
- **Steps:** Analyse `{"G1": "failed"}`. Analyse the S5 states. Run the batch.
- **Expected:** AC1 stays de-energised. S5 bus own figures equal their load sums. AC2 own is 1000/900/800 in every scenario where AC2 is energised.

#### TC-SYS-023 — Sample has passing and failing scenarios

- **Fixture:** FX-SAMPLE
- **Steps:** Run `ela batch --json out.json`.
- **Expected:** No validation error, at least one PASS and at least one FAIL.

#### TC-SYS-024 — Definition list and browser upload

- **Fixture:** H-PAGE, H-DEFS
- **Steps:** Copy FX-SINGLE and a file `notes.txt` into the folder and reload. Upload FX-WARN as `up.json`, then open `up`.
- **Expected:** `fx_single` is listed, `notes` is not, `up` is listed without reload, and its schematic opens.

#### TC-SYS-025 — Definition switch resets state

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH and FX-SAMPLE
- **Steps:** Open FX-BATCH, fail G1, select the sample.
- **Expected:** The sample shows every component at default, and verdict PASS.

#### TC-SYS-026 — Automatic layered schematic

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Read on-screen positions. Search the SVG for load ids and names.
- **Expected:** Sources above buses, AC buses above TRUs, TRUs above DC buses. The file holds no coordinates. No load or breaker is drawn.

#### TC-SYS-027 — Fifty items on a laptop screen

- **Fixture:** H-PAGE, H-DEFS with FX-50
- **Steps:** Open at 1366 × 768. Check boxes. Drag, then wheel.
- **Expected:** All 50 items are inside the viewport with no overlap. The view changes on pan and on zoom.

#### TC-SYS-028 — Colours on one configuration

- **Fixture:** H-PAGE, H-DEFS with FX-COLOURS
- **Steps:** Open and read computed colours and marks.
- **Expected:** AC1 green, AC3 dark grey, AC2 amber, G3 dark grey with a mark.

#### TC-SYS-029 — Labels by band and failed-band note

- **Fixture:** H-PAGE, H-DEFS with FX-TRAN
- **Steps:** Read labels at default. Change band. Fail G2.
- **Expected:** Continuous by default, with V, A and W on energised buses. Values change with the band. AC1 stays amber and names Transient under Continuous. AC2 shows no value label once dead.

#### TC-SYS-030 — Tooltip and supply load

- **Fixture:** H-PAGE, H-DEFS with FX-DISPLAY and FX-TRAN
- **Steps:** Hover AC1 on FX-TRAN and compare with the response. Read G4 on FX-DISPLAY.
- **Expected:** 12 values equal the analysis result, with remaining margin in W with its percentage. G4 shows 45000 W as `45.00 kW` and `50 %`.

#### TC-SYS-031 — Every clickable kind toggles

- **Fixture:** H-PAGE, H-DEFS with FX-ALLKINDS
- **Steps:** Click G1, APU, BAT, TRU1, RAT_AC, `C_G1`, T1E and DCB's switch, twice each.
- **Expected:** One click changes each state, and a second restores it.

#### TC-SYS-032 — Recompute on click within a second

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Make 20 clicks, with no other action, timing each.
- **Expected:** Each click updates the display, and the slowest takes at most 1 second.

#### TC-SYS-033 — Load scenario matches the batch

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run the batch through the API. Select each scenario.
- **Expected:** Each scenario's verdict and bus values equal the batch and analyse results.

#### TC-SYS-045 — Reset restores defaults, keeps the band and clears the scenario

- **Fixture:** H-PAGE, FX-BATCH
- **Steps:** Click G1, choose the 5 s band, press Reset. Then select S5, press Reset.
- **Expected:** After each Reset, the component states and verdict equal a fresh open, the band stays 5 s, and no scenario is selected.

#### TC-SYS-034 — Status panel overall

- **Fixture:** H-PAGE, FX-BATCH with LA2 also essential
- **Steps:** Open at default. Then fail G2 with T13 closed.
- **Expected:** PASS with an empty list. Then FAIL listing the overloads of G1 and T13 and the unpowered LA2.

#### TC-SYS-035 — No editing in the UI

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Search for edit controls. Hash the file. Click, select a scenario, run a batch. Hash again.
- **Expected:** No such control. Hash unchanged.

#### TC-SYS-036 — Browser and CLI runs agree

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH and FX-SAMPLE, CLI on the same files
- **Steps:** Press Run all scenarios. Run `ela batch --json out.json`. Compare.
- **Expected:** Results for every scenario, equal sets of values. FX-BATCH values equal its hand table, with overloads counted as element-band entries. The sample's fields equal `tests/data/generic_twin_expected.json`.

#### TC-SYS-037 — Drill down and open from a batch row

- **Fixture:** H-PAGE, H-DEFS with FX-BATCH
- **Steps:** Run. Expand S5. Click the S5 row.
- **Expected:** 3 failing element-band pairs are listed. The schematic shows S5 with verdict FAIL.

#### TC-SYS-038 — Exports parse and match

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Run. Download both exports. Parse them and compare with the table.
- **Expected:** Both parse and hold the displayed values.

#### TC-SYS-039 — Exit codes through the command line

- **Fixture:** FX-ALLPASS, FX-SAMPLE, FX-THREEERR
- **Steps:** Run `ela batch` on each.
- **Expected:** 0, 1, 2.

#### TC-SYS-040 — One command, local, no login

- **Fixture:** Clean subprocess with the documented command
- **Steps:** Point a browser at the tool with no credentials. Try a non-loopback address.
- **Expected:** The working interface appears with no front-end server. Requests with no credentials succeed. The non-loopback connection is refused.

#### TC-SYS-041 — No front-end build step

- **Fixture:** H-SERVER
- **Steps:** Automated search of the repository for bundler and transpiler configuration. Compare each served front-end file with `web/`.
- **Expected:** None found. Served bytes equal the source files.

#### TC-SYS-042 — Analysis with no server or network

- **Fixture:** FX-BATCH, H-NOSOCKET
- **Steps:** Run the CLI with no server running.
- **Expected:** The run completes with results and exit code 1.

#### TC-SYS-043 — README topics

- **Fixture:** None
- **Steps:** Read `README.md` headings.
- **Expected:** One section each for installation, running, JSON format, adding an aircraft.

#### TC-SYS-044 — Delivered test suite covers the named topics

- **Fixture:** None
- **Steps:** Run `pytest tests -m "not meta"` in a subprocess, with Playwright against the running tool. Map collected tests to the named topics and to sample scenario ids.
- **Expected:** It passes, with at least one test per topic and per scenario, and a real browser ran.

### L0 acceptance tests

#### TC-ACC-001 — Every planned configuration gets a verdict

- **Fixture:** FX-SAMPLE
- **Steps:** Run `ela batch --json out.json`.
- **Expected:** One PASS or FAIL per scenario. Each equals the hand-calculated verdict recorded in `tests/data/generic_twin_expected.json`. The sample's normal, generator-loss, APU-only, RAT-only and battery-only scenarios all appear.

#### TC-ACC-002 — Same tool, different aircraft

- **Fixture:** FX-SAMPLE, FX-4ENG
- **Steps:** With no tool change, open both through the API and run both through the CLI.
- **Expected:** Both load and analyse. FX-4ENG gives 4 generators and 2 scenario results.

#### TC-ACC-003 — Results follow the summation method

- **Fixture:** FX-SAMPLE
- **Steps:** For every scenario and band with no paralleled island, check power balance. Compare with `tests/data/generic_twin_expected.json`.
- **Expected:** Sum of live source demand = sum of bus own power + sum of (TRU input − output), within 1 W. Every checked element obeys `demand × (1 + margin) ≤ capacity` exactly when it is not listed as overloaded. All recorded demands and capacities match within 1 W.

#### TC-ACC-004 — Exploring a failure on the schematic

- **Fixture:** H-PAGE, FX-SAMPLE
- **Steps:** Open the sample. Click the engine 1 generator. Read the displayed energisation and bus values.
- **Expected:** The display changes after the click, and equals the result recorded for that configuration in `tests/data/generic_twin_expected.json`.

#### TC-ACC-005 — Batch reports exactly the failing scenarios

- **Fixture:** FX-SAMPLE
- **Steps:** Run the browser batch.
- **Expected:** Every scenario is listed. The FAIL set is exactly those recorded as failing in `tests/data/generic_twin_expected.json`, which is the designed-to-fail set, and it holds at least one overload failure.

#### TC-ACC-006 — Loss of essential loads is reported

- **Fixture:** FX-SAMPLE
- **Steps:** Analyse every designed-to-fail scenario with no overload.
- **Expected:** At least one exists, reported FAIL with each unpowered essential load named.

#### TC-ACC-007 — README alone gets an engineer running

- **Fixture:** Fresh clone, README only
- **Steps:** Run the README's fenced commands in order. Open the address in Playwright, open the sample, and run all scenarios.
- **Expected:** The tool starts, the sample's schematic is drawn, and the batch completes.

#### TC-ACC-008 — Worked example passes and fails

- **Fixture:** FX-SAMPLE
- **Steps:** Run the batch.
- **Expected:** At least one PASS, at least one FAIL by overload, and at least one FAIL by essential load.

#### TC-ACC-009 — Automated evidence runs clean

- **Fixture:** None
- **Steps:** Run `pytest tests -m "not meta"` twice in a subprocess.
- **Expected:** Both runs finish with no failing test and the same collected test ids.
