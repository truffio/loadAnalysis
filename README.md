# Electrical Load Analysis (ELA) tool

The ELA tool checks an aircraft electrical system in every planned configuration, including failures such as an engine shutdown. For each configuration it adds up the power demand in three time bands, compares it with the capacity of every source and distribution element, and reports PASS or FAIL. It follows the summation method of MIL-E-7016F (civil counterpart ASTM F2490). It is a simple static sum. It is not a circuit or time-domain simulation.

The aircraft is not built into the tool. One JSON file describes the architecture, the loads and the scenarios to check. A complete example for a generic twin-engine transport is in `definitions/generic_twin.json`.

The tool has two uses:

- **Interactive.** A web page draws the system as a schematic. Click a generator, TRU, battery, contactor or crew switch to change its state and see the result at once.
- **Batch.** Run every scenario of a file and list the ones that fail. This works from the web page and from the command line.

The specification is `docs/spec.md`. The rulings that depart from it or fill gaps in it are in `docs/decisions.md` and are cited below as DD-nnn. Requirements, test cases and their trace are in `docs/requirements.md`, `docs/test-cases.md` and `docs/traceability.md`.

## Installation

You need [uv](https://docs.astral.sh/uv/getting-started/installation/). uv installs Python 3.12 or later for you if the machine has none. Check that uv is available:

```sh
uv --version
```

Then, in the repository root, install the tool and its dependencies into a local `.venv`:

```sh
uv sync
```

Nothing else is needed to run the tool. The test suite also needs a browser, see [Running the tests](#running-the-tests).

## Running

### Start the web interface

One command starts the whole tool. The server also serves the web page, so there is no separate front-end server and no build step:

```sh
uv run uvicorn ela.api:app
```

Open <http://127.0.0.1:8000> in a browser. Choose a definition in the first drop-down list. The sample is `generic_twin`.

The server listens on `127.0.0.1` only, so it can be reached from the same machine and from nowhere else. There is no login. To use another port, add `--port 8080`. Stop the server with Ctrl+C.

The server reads definitions from the `definitions/` folder in the repository root. To read another folder, set the environment variable `ELA_DEFINITIONS_DIR` to its path before you start the server.

In the web page:

- The **Definition** list shows every `*.json` file in the folder. The file name without `.json` is the definition id. **Upload** adds a file from your computer. It is checked first. If it has errors, they are listed and the file is not stored. A name already in use is refused.
- An invalid definition is never drawn. Its errors are listed with their JSON paths.
- Drag the drawing to pan it and use the mouse wheel to zoom.
- Click a source, TRU or contactor to change its state. Click the switch on a crew-switched bus to turn its loads on or off. Click the RAT to deploy or stow it. Bus bars are not clickable.
- **Reset** returns every component to its default state. The **Scenario** list applies a scenario to the schematic.
- The **Band** list chooses which band the bus labels show: Transient, 5 s or Continuous (the default).
- Hover over any element for a tooltip with the demand, the demand with margin, the capacity and the remaining margin in all three bands.
- The status panel shows PASS or FAIL for what is on screen and lists each overload, each configuration error and each unpowered essential load.
- **Run all scenarios** runs the whole file and shows a results table. Expand a row for its failing elements. Click a row to open that scenario on the schematic. **Export CSV** and **Export JSON** save the results.

The colours are: green for energised, dark grey for de-energised, amber for overloaded in any band, and dark grey with a cross for a failed source or TRU. Contactors also show open or closed by shape.

### Batch from the command line

```sh
uv run ela batch definitions/generic_twin.json
```

`uv run python -m ela batch ...` does the same. The command runs every scenario and prints one line per scenario on standard output, with tab-separated columns:

1. scenario id
2. scenario name
3. PASS or FAIL
4. worst element
5. worst band
6. smallest remaining margin, in percent
7. number of overloads (element and band pairs)
8. number of configuration errors
9. number of unpowered essential loads

A column with no value shows an em dash. Errors and warnings go to standard error. The analysis runs in the same process. It needs no server and no network.

To save the results, add `--csv` and `--json`. Each takes the path of the file to write:

```sh
uv run ela batch definitions/generic_twin.json --csv results.csv --json results.json
```

The CSV has the nine columns above. The JSON has the same nine fields for each scenario and also the lists of overloads, error messages, unpowered loads and warnings at full precision.

Exit codes:

| Code | Meaning |
| --- | --- |
| 0 | Every scenario passes. |
| 1 | At least one scenario fails. |
| 2 | The definition is invalid, the file cannot be read or is not JSON, or the command is used wrongly. |

For an invalid definition, every error is printed on standard error with its JSON path, and no scenario is run. The sample deliberately contains failing scenarios, so the command above exits with 1.

### HTTP API

The web page uses these routes, and you can call them from scripts. Errors are `{"errors": [{"path", "message"}], "warnings": [...]}`.

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/api/definitions` | List the definitions. |
| POST | `/api/definitions` | Upload a definition (multipart field `file`). 201 when stored, 422 when invalid, 409 when the name is taken. |
| GET | `/api/definitions/{id}` | The definition with its schematic layout. |
| POST | `/api/definitions/{id}/analyse` | Body `{"states": {...}}`. Returns the analysis of that configuration. |
| POST | `/api/definitions/{id}/batch` | Run every scenario. |
| GET | `/api/definitions/{id}/batch/export?format=csv` or `json` | The last batch results of that definition. 404 before any run. |

## How the analysis works

For each configuration the tool does this, once per time band:

1. **Energisation.** A component is energised if a path leads to it from an operative source through closed contactors and energised TRUs. A failed source supplies nothing. TRUs pass power from AC to DC only.
2. **Loads.** Loads are always on. A load draws power when its bus is energised. A crew-switched bus whose switch is off passes no load, but the bus can still be energised.
3. **Demand.** Demand flows upstream from each bus to the source feeding it. Across a TRU the input power is the output power divided by the efficiency.
4. **Source rules.** Two AC sources joined by closed contactors are paralleled. That is a configuration error and the scenario fails. TRUs and DC RAT outputs that feed the same DC island share its demand in proportion to their continuous capacity. A battery supplies only when it is the only source on its island.
5. **Check.** For every element that has a capacity and every band, `demand × (1 + safety_margin) ≤ capacity`. An element with no capacity is not checked. A failing band is an overload. The remaining margin is `capacity − demand × (1 + safety_margin)`, in watts and as a percentage of capacity. The smallest percentage in a configuration names its worst element.
6. **Current.** DC current is `P / V`. AC current is per phase, `P / (phases × V)`, with power factor 1.0. For an AC bus `voltage` is the phase voltage.

A configuration passes when there is no overload, no configuration error and no unpowered essential load.

Two rules depart from the specification (`docs/spec.md`):

- **Bus demand is throughput (DD-002).** Section 3.4 of the specification takes bus demand as the loads on that bus. This tool reports for a bus everything that passes through it: its own loads plus the demand of every bus and TRU it feeds, with TRU input power after efficiency. The capacity check uses that figure, since a busbar's rating applies to what it carries. Otherwise an overload on a feeding bus would go unseen. The bus's own loads are reported separately as `own`. Bus labels on the schematic show throughput.
- **Essential loads (DD-001).** Capacity checks alone report PASS when every source has failed, because nothing is overloaded. A load may therefore be marked `"essential": true`. A configuration fails if any essential load is unpowered, meaning its bus is de-energised or its crew switch is off. Each unpowered essential load is reported by name. A definition with no essential load gets a warning.

## JSON format reference

One file describes one aircraft. It is a JSON object with these top-level keys, all required: `meta`, `settings`, `sources`, `buses`, `trus`, `contactors`, `loads` and `scenarios`. Use an empty list where you have none of a kind.

Units: power and capacity are in **watts**, voltage is in **volts**, and the safety margin and the TRU efficiency are **decimals** (0.10 means 10 %). Every `id` must be unique across `sources`, `buses`, `trus`, `contactors` and `loads`. Scenario ids must be unique among scenarios. An `id` is the key other elements use to refer to it. A `name` is the text shown to people.

The validator returns all errors at once, each with its JSON path and a message. It does not open an invalid file.

### Time bands

Every load and every capacity is a band object with three keys, all required. Each value is a number of watts, zero or more:

| Key | Meaning |
| --- | --- |
| `transient` | The inrush peak at switch-on. |
| `short_term` | The demand over the first 5 seconds, between the peak and steady state. |
| `continuous` | Steady state. |

Typically `transient ≥ short_term ≥ continuous` for a load, but the tool does not enforce `transient ≥ short_term ≥ continuous`. Enter the figure that belongs in each band. A missing band or a negative value is an error.

### `meta`

| Key | Required | Meaning |
| --- | --- | --- |
| `aircraft` | yes | Aircraft name, text. |
| `revision` | yes | Revision of this file, text. |
| `description` | no | Free text. |

### `settings`

| Key | Required | Meaning |
| --- | --- | --- |
| `safety_margin` | yes | Global margin as a decimal, zero or more. `0.10` is 10 %. |
| `bands` | no | Display labels for the bands. The keys are `transient`, `short_term` and `continuous`, and each is optional. Each holds an optional `label` (text) and an optional `duration_s` (seconds, a number). Labels default to Transient, 5 s and Continuous. |

### `sources`

Engine generators, the APU generator, the emergency (RAT) generator and batteries. Each source is an object:

| Key | Required | Meaning |
| --- | --- | --- |
| `id`, `name` | yes | Identity. |
| `kind` | yes | `engine_generator`, `apu_generator`, `emergency_generator` or `battery`. |
| `engine` | engine generators only | Engine number, an integer. Two generators cannot share one. Any number of engines is allowed. |
| `output` | yes | `AC` or `DC`. Engine and APU generators are AC. A battery is DC. An emergency generator can be either. |
| `voltage` | yes | Nominal voltage in volts, above zero. For AC it is the phase voltage, for example 115. |
| `phases` | no | AC only. Number of phases, default 3. On a DC source it is an unknown key. |
| `capacity` | yes | Band object, in watts. |
| `safety_margin` | no | Overrides the global margin for this element. |
| `default_state` | yes, except on an emergency generator | `operative` or `failed`. An emergency generator takes `available` or `unavailable` and defaults to `unavailable`. |

There can be at most one APU generator. To model a RAT with an AC output and a DC output, give it two source entries, one per output. Each is clicked and checked on its own, and there is no combined limit.

### `buses`

| Key | Required | Meaning |
| --- | --- | --- |
| `id`, `name` | yes | Identity. |
| `type` | yes | `AC` or `DC`. |
| `role` | yes | `main`, `essential`, `emergency`, `other` or `battery`. `battery` is for DC buses only. The role is a descriptive tag used for layout and display. |
| `voltage` | yes | Nominal voltage in volts, above zero. |
| `phases` | no | AC only, default 3. |
| `crew_switch` | no | `true` if the flight crew switch the loads on this bus on. Default `false`. The switch starts `on`. |
| `capacity` | no | Band object, in watts. With no capacity the bus is not checked. |
| `safety_margin` | no | Overrides the global margin. |

### `trus`

Transformer rectifier units. They convert AC to DC, one way.

| Key | Required | Meaning |
| --- | --- | --- |
| `id`, `name` | yes | Identity. |
| `input_bus` | yes | Id of an AC bus. |
| `output_bus` | yes | Id of a DC bus. |
| `efficiency` | yes | Decimal above 0 and at most 1. Input power is output power divided by it. |
| `capacity` | yes | Band object in watts. It is the output capacity. |
| `safety_margin` | no | Overrides the global margin. |
| `default_state` | yes | `operative` or `failed`. |

Each TRU needs exactly one `tru` contactor between `input_bus` and the TRU, and exactly one between the TRU and `output_bus`.

### `contactors`

A contactor exists everywhere a source connects to a bus, at both ends of a TRU, and wherever two buses are tied. It joins exactly two nodes.

| Key | Required | Meaning |
| --- | --- | --- |
| `id`, `name` | yes | Identity. |
| `kind` | yes | `source` joins a source and a bus. `bus_tie` joins two buses. `tru` joins a bus and a TRU. |
| `from`, `to` | yes | Ids of the two nodes it joins. Power passes both ways when it is closed. A contactor cannot join an AC node to a DC node. |
| `capacity` | no | Band object, in watts. With none, the contactor is not checked. |
| `safety_margin` | no | Overrides the global margin. |
| `default_state` | yes | `closed` or `open`. |

### `loads`

Loads are always on and each is attached to one bus. Circuit breakers are not modelled. Loads and breakers are not drawn.

| Key | Required | Meaning |
| --- | --- | --- |
| `id`, `name` | yes | Identity. |
| `bus` | yes | Id of the bus that feeds the load. |
| `power` | yes | Band object, in watts. |
| `essential` | no | `true` if the load is needed for continued safe flight. Default `false`. See DD-001 above. |

### `scenarios`

A scenario is a configuration to check. It lists only the components that differ from their `default_state`.

| Key | Required | Meaning |
| --- | --- | --- |
| `id`, `name` | yes | Identity. |
| `description` | no | Free text. |
| `states` | yes | An object mapping a component id to its state. Use `{}` for the defaults. |

Valid state values:

| Component | Values |
| --- | --- |
| Engine generator, APU generator, battery, TRU | `operative`, `failed` |
| Emergency generator | `available`, `unavailable` |
| Contactor | `closed`, `open` |
| Bus with `crew_switch` | `on`, `off` |

A key that matches no component with a state, or a value that is not valid for it, is an error.

### Validation rules

These are errors and stop the file from loading:

- A missing required key, a wrong type or a number out of range.
- A repeated id.
- A reference to something that does not exist, such as a load on an unknown bus.
- A TRU that is connected DC to AC, a contactor between an AC node and a DC node, or a contactor of the wrong kind for the nodes it joins.
- A second APU generator, two generators for one engine, or a source whose `output` does not suit its `kind`.
- A TRU without exactly one input contactor and one output contactor.
- A scenario state for an unknown component or with an invalid value.

These are warnings. They are shown but do not block the file:

- A key the tool does not know. It is ignored.
- A contactor that joins two nodes of the same kind but different nominal voltages.
- A source with no contactor.
- A bus that no source can feed.
- No load is marked essential. Total power loss would still pass.

## Adding a new aircraft

You do not change the tool. You write a new definition file.

1. Copy `definitions/generic_twin.json` to a new file in the `definitions/` folder, for example `definitions/my_aircraft.json`. The file name without `.json` becomes the definition id. Use letters, digits, `_` and `-`.
2. Edit `meta` and `settings`. Set the global `safety_margin`.
3. List the `sources`: one engine generator per engine (numbered with `engine`), the APU generator if there is one, the RAT outputs and the batteries. Give each a capacity in all three bands and a `default_state`.
4. List the `buses` with their `type`, `role` and nominal voltage. Set `crew_switch: true` on a bus whose loads the crew switch on, usually the battery bus. Add a `capacity` to any bus that has a rating.
5. List the `trus` and, for each one, the two `tru` contactors.
6. List the `contactors`: one `source` contactor wherever a source connects to a bus, and a `bus_tie` for every tie between buses. Choose each `default_state` so that the default configuration is sound. In particular do not leave two AC sources joined by closed contactors.
7. List the `loads` with their power in all three bands.
8. Mark the loads needed for continued safe flight with `"essential": true`. Be careful with what each configuration can power. With no AC on battery (see Known limits), an essential load on an AC bus fails every battery-only scenario.
9. Write the `scenarios`: the normal case, each generator loss, the APU only, loss of generators and APU, each TRU failure, the RAT only, battery only, and so on.

**Scenarios must list contactors.** The tool does no automatic reconfiguration. It does not transfer a bus to another source by itself and it does not shed loads. If the APU is to feed AC BUS 1 after Generator 1 fails, the scenario must say `"GEN1": "failed"` and also close the APU line contactor for that bus, for example `"APLC1": "closed"`. If you leave the contactor out, the bus stays dead, and the result shows exactly that. When you close a tie that joins two live AC sources, open another contactor, or the scenario fails with "AC sources paralleled".

Validate the file by running the batch command on it:

```sh
uv run ela batch definitions/my_aircraft.json
```

If there are errors, the exit code is 2 and each error is printed with its JSON path. Fix them all and run it again. Warnings are printed with a `warning:` prefix. Read them. When the file is valid, the command runs the scenarios. Then reload the web page. The new file is in the definition list, and the schematic is drawn from the file with no coordinates to enter. You can also upload the file from the page instead of copying it into `definitions/`.

## Known limits

- **Meshed islands (DD-004).** The specification assumes power reaches a bus along a single path. When closed contactors form a loop, the split of power around the loop cannot be found without impedances, and impedances are out of scope. The tool picks a deterministic spanning tree of the island (breadth-first from the source with the lowest id, neighbours in id order). The contactors left out carry zero, and a `meshed_island` warning names them. Totals per bus and source are not affected, but the flow shown on a contactor in a loop is an assumption.
- **No AC on battery (DD-019).** The component model has no inverter, and DC to AC conversion is not allowed. With only the battery, every AC bus is dead. Essential loads on an AC bus cannot be powered in that configuration.
- **No endurance check.** Batteries are checked for power in the three bands only. There is no amp-hour, depletion or endurance calculation.
- **No automatic reconfiguration.** Every configuration is static and planned in advance as a scenario.
- **Paralleled AC (DD-005).** An AC island with more than one live source is reported as a configuration error. Its buses stay energised and its loads count, but no demand is given to its sources and contactors, so they are not checked.
- **Static and simple.** Loads are always on, with no flight phases. Voltage is constant. There is no time-domain simulation. AC power factor is 1.0.
- **Reference methodology only.** The tool follows the summation method of MIL-E-7016F and ASTM F2490 as a reference. It is not certified and does not claim compliance with either document. Its results are not certification evidence.
- **Local use.** The server has no authentication and listens on the loopback address only. The page does not edit a definition. Edit the JSON file by hand.

## Running the tests

The test suite uses pytest and drives a real Chromium browser with Playwright. Install the browser once:

```console
uv run playwright install chromium
```

Run the suite and the style check:

```console
uv run pytest
uv run ruff check .
```

The browser tests are slow. A full run takes about 15 minutes, because the `meta` tests run the rest of the suite in a subprocess. Tests that do that carry the `meta` marker. `uv run pytest -m "not meta"` leaves them out, and `uv run pytest -m "not e2e"` leaves out the browser tests.

Each test carries `@pytest.mark.tc("TC-...")`, the id of a case in `docs/test-cases.md`. The trace from requirements to cases to tests is generated into `docs/traceability.md`:

```console
uv run python tools/trace_report.py
```

## Repository layout

| Path | Contents |
| --- | --- |
| `ela/` | The Python package: `model.py` (schema), `validate.py`, `engine.py` (analysis), `layout.py` (schematic), `batch.py`, `cli.py`, `api.py` (FastAPI app). |
| `web/` | The front end: plain HTML, CSS and JavaScript modules, with no build step. |
| `definitions/` | Definition files. `generic_twin.json` is the sample. |
| `tests/` | The pytest suite. `tests/data/generic_twin_expected.json` is the hand-calculated result for the sample. |
| `docs/` | Specification, decisions, requirements, test cases, plan and trace. |
