# ELA tool requirements

Requirements for the Electrical Load Analysis (ELA) tool specified in `docs/spec.md` v1.0. Three levels are held in this one file. L0 records are stakeholder requirements: what the tool must achieve for an aircraft electrical engineer. L1 records are system requirements: black-box behaviour of the tool as a whole, independent of implementation. L2 records are component requirements, each allocated to exactly one component from `docs/plan.md`, and each L2 section is one implementation issue. The rulings in `docs/decisions.md` take precedence over `docs/spec.md` wherever the two differ. Test cases are held only in `docs/test-cases.md`.

## Assumptions

Assumptions inherited from `docs/spec.md` §9, followed by readings adopted here where the specification and rulings leave a detail open. Item 3 of §9 is closed by DD-001 and is not repeated.

<!-- BEGIN SECTION ASSUMPTIONS -->

### ASM-001

```asm
ID: ASM-001
Assumption: AC current is per-phase with power factor 1.0, and `phases` defaults to 3.
Rationale: Accepted from docs/spec.md §9 item 1. Loads are given in watts, so no reactive power is
  modelled.
Affects: L1-ELA-031, L2-ENG-058, L2-MOD-016
Status: Accepted
```

### ASM-002

```asm
ID: ASM-002
Assumption: AC paralleling is an error, DC TRUs share in proportion to capacity, and the battery
  supplies only when it is the sole source on its island.
Rationale: Accepted from docs/spec.md §9 item 2, as refined by DD-005, DD-006 and DD-015.
Affects: L1-ELA-020, L1-ELA-021, L1-ELA-022
Status: Accepted
```

### ASM-003

```asm
ID: ASM-003
Assumption: The band selector defaults to Continuous for displayed bus values, and amber shows an
  overload in any band.
Rationale: Accepted from docs/spec.md §9 item 4.
Affects: L1-ELA-043, L1-ELA-044, L2-WIN-024, L2-WIN-019
Status: Accepted
```

### ASM-004

```asm
ID: ASM-004
Assumption: The RAT default state is unavailable (stowed) unless a scenario deploys it.
Rationale: Accepted from docs/spec.md §9 item 5. A definition that omits `default_state` on an
  emergency generator gets `unavailable`.
Affects: L2-MOD-015, L2-SMP-023
Status: Accepted
```

### ASM-005

```asm
ID: ASM-005
Assumption: The `voltage` of an AC bus is the phase voltage `V_phase` used in the AC current
  formula, so a 115 V, 3-phase bus carrying 3450 W reports 10 A.
Rationale: docs/spec.md §3.7 uses `V_phase` but §5.1 defines only `voltage`. The 115 V figure in
  §5.1 is a conventional line-to-neutral value.
Affects: L1-ELA-031, L2-ENG-058
Status: Accepted
```

### ASM-006

```asm
ID: ASM-006
Assumption: `default_state` is required on TRUs, contactors and every source except an emergency
  generator. An explicit `default_state` of `available` on an emergency generator is honoured.
Rationale: DD-021 rules that an explicit value is honoured and that an absent value defaults to
  `unavailable`. `default_state` is not among the keys docs/spec.md §5.2 names as optional.
Affects: L2-MOD-014, L2-MOD-015, L2-MOD-021, L2-MOD-022
Status: Accepted
```

### ASM-007

```asm
ID: ASM-007
Assumption: More than one source of kind `apu_generator`, or two engine generators with the same
  `engine` number, is a validation error.
Rationale: docs/spec.md §4.1 says one per engine and §4.2 says one per aircraft. §5.2 does not list
  either as an error, so this reading is open to challenge at review.
Affects: L2-VAL-016, L2-VAL-017
Status: Accepted
```

### ASM-008

```asm
ID: ASM-008
Assumption: A contactor is also incompatible when its endpoints do not suit its `kind`: `source`
  joins a source and a bus, `bus_tie` joins two buses, and `tru` joins a bus and a TRU.
Rationale: Extends "incompatible nodes" in docs/spec.md §5.2 using the definitions in §4.8, because
  the engine depends on these endpoint types.
Affects: L2-VAL-021
Status: Accepted
```

### ASM-009

```asm
ID: ASM-009
Assumption: Numeric ranges not stated in the specification apply: voltages are greater than 0,
  `phases` is an integer of at least 1, and `safety_margin` is at least 0.
Rationale: Current formulas divide by voltage and phases, and a negative margin would weaken the
  criterion in docs/spec.md §3.6.
Affects: L2-VAL-015
Status: Accepted
```

### ASM-010

```asm
ID: ASM-010
Assumption: Every energised element with a capacity is checked unless DD-005 removes its demand, and
  zero demand counts. De-energised and failed elements are not checked.
Rationale: DD-011 states that de-energised elements are not checked, and DD-005 removes demand from
  paralleled sources and contactors. An energised element at zero demand stays checked.
Affects: L2-ENG-042, L2-ENG-049, L2-ENG-050
Status: Accepted
```

### ASM-011

```asm
ID: ASM-011
Assumption: Equal smallest margins, within the DD-023 tolerance of 1e-6 %, are resolved to the
  lowest element id, then to band order `transient`, `short_term`, `continuous`.
Rationale: DD-011 states the zero-capacity cases and DD-023 states the tolerance, but neither gives
  a tie order. A fixed order keeps results repeatable.
Affects: L2-ENG-049
Status: Accepted
```

### ASM-012

```asm
ID: ASM-012
Assumption: On a paralleled island, an available emergency generator output counts as an operative
  source for DD-005.
Rationale: Withdrawn: DD-005 now states that a live source may be operative or available.
Affects: L1-ELA-022, L2-ENG-028
Status: Withdrawn
```

### ASM-013

```asm
ID: ASM-013
Assumption: An `unavailable` emergency generator output is drawn dark grey without a failure mark.
Rationale: `unavailable` is the normal stowed state, so a failure mark in the default view would
  mislead. docs/spec.md §6.2 gives the mark only to a failed source or TRU.
Affects: L2-WIN-020, L2-WIN-018
Status: Accepted
```

### ASM-014

```asm
ID: ASM-014
Assumption: Buses of role `other` take the layer of the essential and emergency buses of their type,
  on the AC side, and the last DC bus layer on the DC side.
Rationale: docs/spec.md §6.2 lists no layer for this role.
Affects: L2-LAY-003
Status: Accepted
```

### ASM-015

```asm
ID: ASM-015
Assumption: Project choices for figures the specification leaves open: a laptop screen means a 1366
  × 768 px viewport with a schematic drawing area of at least 1000 × 560 px; a redraw completes
  within 1 second; power displays as an integer in W below 1000 W and with two decimals in kW from
  1000 W; current displays with two decimals and a percentage with at most two; negative numbers in
  all program output use ASCII hyphen-minus; a successful upload returns HTTP 201; a JSON path is
  `$`-rooted, for example `$.loads[3].bus`.
Rationale: Each vague or unstated value needs one testable figure. These can be changed at review
  without altering the structure of the requirements.
Affects: L1-ELA-041, L1-ELA-049, L2-LAY-018, L2-WIN-016, L2-WIN-022, L2-WIN-031, L2-WBT-002,
  L2-CLI-002, L2-WIN-025, L2-API-006, L2-VAL-003
Status: Accepted
```

<!-- END SECTION ASSUMPTIONS -->

## L0 stakeholder requirements

<!-- BEGIN SECTION L0 -->

### L0-ELA-001

```req
ID: L0-ELA-001
Level: L0
Type: Functional
Statement: The tool shall enable an aircraft electrical engineer to determine, for every planned
  configuration of an aircraft electrical system including failure configurations, whether the
  available power is sufficient to supply the connected loads.
Rationale: This is the purpose of an electrical load analysis in the sense of MIL-E-7016F.
Parent(s): —
Source: docs/spec.md §1
Allocated to: —
Verification: Test; success criteria: analysing the delivered sample definition gives a PASS or FAIL
  verdict for every scenario, and each verdict equals the hand-calculated verdict recorded in
  `tests/data/generic_twin_expected.json`.
Status: Draft
```

### L0-ELA-002

```req
ID: L0-ELA-002
Level: L0
Type: Functional
Statement: The tool shall analyse any aircraft whose electrical architecture, loads and scenarios
  are described in a single JSON definition file, with no change to the tool.
Rationale: The tool is generic and is not tied to one aircraft.
Parent(s): —
Source: docs/spec.md §1; docs/spec.md §2
Allocated to: —
Verification: Test; success criteria: a 4-engine definition and the 2-engine sample definition are
  both loaded and analysed by the same unmodified tool.
Status: Draft
```

### L0-ELA-003

```req
ID: L0-ELA-003
Level: L0
Type: Functional
Statement: The tool shall compute its results by summing power demand in three time bands and
  comparing it, with a safety margin, against the capacity of each source and distribution element.
Rationale: The analysis is deliberately a summation in the MIL-E-7016F style and not a simulation.
Parent(s): —
Source: docs/spec.md §1; docs/spec.md §3
Allocated to: —
Verification: Test; success criteria: for every sample scenario, demand and capacity results for all
  three bands match the hand calculations recorded in `tests/data/generic_twin_expected.json` to
  within 1 W.
Status: Draft
```

### L0-ELA-004

```req
ID: L0-ELA-004
Level: L0
Type: Functional
Statement: The tool shall let the engineer explore configurations on a drawn schematic of the
  system, showing the resulting energisation and bus loading after each state change.
Rationale: Interactive exploration is the first of the two stated uses of the tool.
Parent(s): —
Source: docs/spec.md §1; docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: in a browser, failing a generator on the sample schematic
  changes the displayed energisation and bus values to the hand-calculated result recorded in
  `tests/data/generic_twin_expected.json` for that configuration.
Status: Draft
```

### L0-ELA-005

```req
ID: L0-ELA-005
Level: L0
Type: Functional
Statement: The tool shall run every defined scenario automatically and report each scenario that
  fails the continued safe flight criteria.
Rationale: Batch verification is the second of the two stated uses of the tool.
Parent(s): —
Source: docs/spec.md §1; docs/spec.md §6.3
Allocated to: —
Verification: Test; success criteria: a batch run of the sample definition reports every scenario,
  and the scenarios reported as FAIL are exactly those recorded as failing in
  `tests/data/generic_twin_expected.json`.
Status: Draft
```

### L0-ELA-006

```req
ID: L0-ELA-006
Level: L0
Type: Functional
Statement: The tool shall show whether the loads needed for continued safe flight remain powered in
  each configuration.
Rationale: The aim is that the crew can deal with the emergency and return safely. Capacity checks
  alone report PASS when every source has failed.
Parent(s): —
Source: docs/spec.md §1; docs/spec.md §9; DD-001
Allocated to: —
Verification: Test; success criteria: the sample scenario designed to fail on an essential load is
  reported FAIL with each unpowered essential load named.
Status: Draft
```

### L0-ELA-007

```req
ID: L0-ELA-007
Level: L0
Type: Usability
Statement: The tool shall be usable by a single engineer on a local workstation by following its
  delivered documentation.
Rationale: This is a local single-user tool with one-command start.
Parent(s): —
Source: docs/spec.md §7.3; docs/spec.md §8; DD-016
Allocated to: —
Verification: Test; success criteria: following only the README commands on a clean checkout starts
  the tool, opens the sample definition in a browser and completes a batch run.
Status: Draft
```

### L0-ELA-008

```req
ID: L0-ELA-008
Level: L0
Type: Data
Statement: The tool shall be delivered with a complete worked example that demonstrates both passing
  and failing results.
Rationale: A worked example shows how a definition is written and what a failing report looks like.
Parent(s): —
Source: docs/spec.md §5.3; docs/spec.md §8
Allocated to: —
Verification: Test; success criteria: the delivered example contains at least one scenario that
  passes and at least one that fails when analysed.
Status: Draft
```

### L0-ELA-009

```req
ID: L0-ELA-009
Level: L0
Type: Constraint
Statement: The tool shall be delivered with automated tests that give repeatable evidence of its
  behaviour.
Rationale: An analysis tool is only useful if its results can be trusted and re-checked.
Parent(s): —
Source: docs/spec.md §7.1; docs/spec.md §8; DD-003
Allocated to: —
Verification: Test; success criteria: `pytest tests -m "not meta"`, run in a subprocess, completes
  with no failing test.
Status: Draft
```

<!-- END SECTION L0 -->

## L1 system requirements

<!-- BEGIN SECTION L1 -->

### L1-ELA-001

```req
ID: L1-ELA-001
Level: L1
Type: Data
Statement: The tool shall read an aircraft's topology, loads, analysis settings and scenarios from
  one JSON definition file.
Rationale: A single file keeps a definition complete and portable between aircraft projects.
Parent(s): L0-ELA-002
Source: docs/spec.md §2; docs/spec.md §5
Allocated to: —
Verification: Test; success criteria: the tool opens the sample definition and analyses all its
  scenarios with that file as its only input data.
Status: Draft
```

### L1-ELA-002

```req
ID: L1-ELA-002
Level: L1
Type: Data
Statement: The tool shall interpret definition values with power in watts, voltage in volts, and
  margins and efficiencies as decimals.
Rationale: One fixed unit system removes conversion errors from hand-edited files.
Parent(s): L0-ELA-002
Source: docs/spec.md §5
Allocated to: —
Verification: Test; success criteria: a definition with a 1000 W load and `safety_margin` 0.10 gives
  demand 1000 W and demand with margin 1100 W.
Status: Draft
```

### L1-ELA-003

```req
ID: L1-ELA-003
Level: L1
Type: Functional
Statement: The tool shall impose no upper limit on the number of engine generators in a definition.
Rationale: Twin and four-engine aircraft are typical, and up to about 8 is expected, with no hard
  limit.
Parent(s): L0-ELA-002
Source: docs/spec.md §4.1
Allocated to: —
Verification: Test; success criteria: definitions with 2, 4, 8 and 12 engine generators each load
  and analyse with no error.
Status: Draft
```

### L1-ELA-004

```req
ID: L1-ELA-004
Level: L1
Type: Functional
Statement: The tool shall accept definitions holding zero or one APU generator.
Rationale: Not every aircraft has an APU.
Parent(s): L0-ELA-002
Source: docs/spec.md §4.2
Allocated to: —
Verification: Test; success criteria: one definition with no APU generator and one with an APU
  generator each load and analyse with no error.
Status: Draft
```

### L1-ELA-005

```req
ID: L1-ELA-005
Level: L1
Type: Data
Statement: The tool shall model each electrical component as an engine generator, APU generator,
  emergency generator output, battery, AC bus, DC bus, TRU, contactor or bus tie, with the
  attributes and states given in docs/spec.md §4.
Rationale: These kinds cover the aircraft electrical architectures in scope. Each carries a unique
  id and a readable name.
Parent(s): L0-ELA-002
Source: docs/spec.md §4; DD-008
Allocated to: —
Verification: Test; success criteria: a definition containing every component kind loads, and each
  stateful kind takes each of its listed states in analysis.
Status: Draft
```

### L1-ELA-006

```req
ID: L1-ELA-006
Level: L1
Type: Functional
Statement: The tool shall validate every definition before analysing it.
Rationale: Analysis of a malformed definition would give meaningless results.
Parent(s): L0-ELA-002
Source: docs/spec.md §5.2; docs/spec.md §6.1
Allocated to: —
Verification: Test; success criteria: a definition with a dangling bus reference yields validation
  errors and no analysis result.
Status: Draft
```

### L1-ELA-007

```req
ID: L1-ELA-007
Level: L1
Type: Functional
Statement: The tool shall report all validation errors of a definition in one response, each with
  its JSON path and a readable message.
Rationale: Definitions are edited by hand, so seeing every error at once saves repeated runs.
Parent(s): L0-ELA-002
Source: docs/spec.md §5.2
Allocated to: —
Verification: Test; success criteria: a definition seeded with 5 independent faults yields at least
  one error for each fault in one response, each error with a path that locates the fault and a
  non-empty message.
Status: Draft
```

### L1-ELA-008

```req
ID: L1-ELA-008
Level: L1
Type: Functional
Statement: The tool shall refuse to open a definition that has a validation error.
Rationale: An invalid definition cannot be analysed reliably.
Parent(s): L0-ELA-002
Source: docs/spec.md §6.1
Allocated to: —
Verification: Test; success criteria: selecting an invalid definition displays its errors and draws
  no schematic for it.
Status: Draft
```

### L1-ELA-009

```req
ID: L1-ELA-009
Level: L1
Type: Functional
Statement: The tool shall report definition warnings without blocking the definition from loading.
Rationale: Warnings mark content that is suspicious but legal.
Parent(s): L0-ELA-002
Source: docs/spec.md §5.2; DD-017
Allocated to: —
Verification: Test; success criteria: a definition with an unknown key opens normally and the
  warning naming that key is displayed.
Status: Draft
```

### L1-ELA-010

```req
ID: L1-ELA-010
Level: L1
Type: Functional
Statement: The tool shall treat a state entry that names no stateful component, or gives a value
  invalid for that component, as an error in both scenarios and interactive analysis requests.
Rationale: A mistyped component id would otherwise silently analyse the wrong configuration.
Parent(s): L0-ELA-002
Source: docs/spec.md §5.2; DD-009
Allocated to: —
Verification: Test; success criteria: a scenario entry with an unknown id is reported as a
  validation error, and the same entry in an interactive analysis request is rejected with an error.
Status: Draft
```

### L1-ELA-011

```req
ID: L1-ELA-011
Level: L1
Type: Data
Statement: The tool shall evaluate every load power and every capacity separately in the three bands
  `transient`, `short_term` and `continuous`.
Rationale: `transient` is peak demand at switch-on or inrush, `short_term` is demand over the first
  5 seconds or so, and `continuous` is steady-state demand.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.1; DD-010
Allocated to: —
Verification: Test; success criteria: a definition with different values in each band gives three
  different demand results for a bus, each equal to the sum for that band.
Status: Draft
```

### L1-ELA-012

```req
ID: L1-ELA-012
Level: L1
Type: Constraint
Statement: The tool shall accept a definition regardless of the numeric ordering of the three band
  values of a load or capacity.
Rationale: `transient ≥ short_term ≥ continuous` is typical but is not a rule.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.1; DD-010
Allocated to: —
Verification: Test; success criteria: a definition with a load whose `continuous` value exceeds its
  `transient` value loads with no error and no warning about band ordering.
Status: Draft
```

### L1-ELA-013

```req
ID: L1-ELA-013
Level: L1
Type: Functional
Statement: The tool shall determine a component to be energised only if a path exists to it from an
  operative or available source through closed contactors and energised converters.
Rationale: This is the definition of energisation. A failed source supplies nothing and bridges
  nothing.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.3; DD-012
Allocated to: —
Verification: Test; success criteria: with its only source failed a bus is reported de-energised,
  and with that source restored the bus is reported energised.
Status: Draft
```

### L1-ELA-014

```req
ID: L1-ELA-014
Level: L1
Type: Functional
Statement: The tool shall pass power through a closed contactor or bus tie in both directions and
  through an open one in neither direction.
Rationale: Contactors and ties are bidirectional switches.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.3
Allocated to: —
Verification: Test; success criteria: a bus tie energises the far bus from either end when closed,
  and from neither end when open.
Status: Draft
```

### L1-ELA-015

```req
ID: L1-ELA-015
Level: L1
Type: Functional
Statement: The tool shall pass power through a TRU only from AC to DC.
Rationale: A TRU is a one-way rectifier.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.3; docs/spec.md §4.7
Allocated to: —
Verification: Test; success criteria: a live DC bus with both TRU contactors closed does not
  energise the AC bus at the TRU input.
Status: Draft
```

### L1-ELA-016

```req
ID: L1-ELA-016
Level: L1
Type: Functional
Statement: The tool shall count a load's power if and only if its bus is energised and no crew
  switch on that bus is off.
Rationale: Loads are always on, so their draw depends only on the bus and its crew switch.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.2; docs/spec.md §3.4; docs/spec.md §4.9
Allocated to: —
Verification: Test; success criteria: a load counts at its defined power with its bus energised, and
  counts zero with the bus de-energised or the crew switch off.
Status: Draft
```

### L1-ELA-017

```req
ID: L1-ELA-017
Level: L1
Type: Functional
Statement: The tool shall start every interactive session and every scenario with each crew switch
  on, unless the scenario sets it off.
Rationale: The crew switches the battery-fed loads on, so the analysis assumes that has been done.
Parent(s): L0-ELA-003
Source: docs/spec.md §4.9
Allocated to: —
Verification: Test; success criteria: a new session and a scenario that does not list the switch
  both show it on, and a scenario listing it `off` shows it off.
Status: Draft
```

### L1-ELA-018

```req
ID: L1-ELA-018
Level: L1
Type: Functional
Statement: The tool shall report, for each energised bus and band, both its throughput demand,
  meaning its own loads plus all power fed through it, and its own-load power.
Rationale: A busbar's rating applies to what it carries, so own loads alone would hide overloads on
  feeding buses.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.4; DD-002
Allocated to: —
Verification: Test; success criteria: on a bus with 1000 W of own loads feeding a downstream bus of
  500 W, throughput demand is 1500 W and own-load power is 1000 W.
Status: Draft
```

### L1-ELA-019

```req
ID: L1-ELA-019
Level: L1
Type: Functional
Statement: The tool shall propagate demand upstream from each bus to the sources feeding it, with
  input power at each TRU equal to its output power divided by its efficiency.
Rationale: TRU losses mean the AC side always supplies more than the DC side consumes.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.4; DD-004; DD-013; DD-014
Allocated to: —
Verification: Test; success criteria: a 850 W DC bus fed by a TRU of efficiency 0.85 from a single
  generator gives 1000 W demand on that generator.
Status: Draft
```

### L1-ELA-020

```req
ID: L1-ELA-020
Level: L1
Type: Functional
Statement: The tool shall share the demand of a DC island fed by more than one non-battery DC source
  in proportion to their continuous capacities, in all three bands.
Rationale: Static configurations need one deterministic sharing rule.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.5; DD-006
Allocated to: —
Verification: Test; success criteria: two TRUs of 6000 W and 3000 W continuous capacity on one
  island with 900 W demand carry 600 W and 300 W in each band.
Status: Draft
```

### L1-ELA-021

```req
ID: L1-ELA-021
Level: L1
Type: Functional
Statement: The tool shall assign zero demand to a battery on a DC island that another energised DC
  source is feeding.
Rationale: The battery supplies only when it is the island's sole source.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.5; DD-015
Allocated to: —
Verification: Test; success criteria: a battery shows zero demand with a TRU feeding its island, and
  shows the island demand when that TRU has failed.
Status: Draft
```

### L1-ELA-022

```req
ID: L1-ELA-022
Level: L1
Type: Functional
Statement: The tool shall flag a configuration error with the message "AC sources paralleled" when
  more than one live AC source is connected to one island of buses.
Rationale: Unsynchronised AC generators are not paralleled, so such a configuration is a planning
  mistake.
Parent(s): L0-ELA-001
Source: docs/spec.md §3.5; DD-005
Allocated to: —
Verification: Test; success criteria: closing a tie between two live generators' buses gives FAIL
  with a configuration error containing "AC sources paralleled".
Status: Draft
```

### L1-ELA-023

```req
ID: L1-ELA-023
Level: L1
Type: Functional
Statement: The tool shall issue a warning naming the contactors left out of the flow calculation
  when an island contains a closed loop.
Rationale: The split of power around a loop is indeterminate without impedances, so the assumption
  made has to stay visible.
Parent(s): L0-ELA-003
Source: DD-004
Allocated to: —
Verification: Test; success criteria: closing a ring of three bus ties gives a warning naming the
  one contactor left out.
Status: Draft
```

### L1-ELA-024

```req
ID: L1-ELA-024
Level: L1
Type: Functional
Statement: The tool shall declare an element with a defined capacity overloaded unless `demand × (1
  + safety_margin) ≤ capacity` holds in all three bands, treating an excess within 1e-6 W as
  satisfying it.
Rationale: This is the pass criterion for sources, TRUs, buses and rated contactors and ties. IEEE
  arithmetic makes 3000 × 1.1 exceed 3300, so DD-023 sets a tolerance.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.6; DD-023
Allocated to: —
Verification: Test; success criteria: with `safety_margin` 0.10 and demand 1000 W, capacity 1100 W
  is not overloaded and capacity 1099 W is overloaded, and with demand 3000 W, capacity 3300 W is
  not overloaded.
Status: Draft
```

### L1-ELA-025

```req
ID: L1-ELA-025
Level: L1
Type: Functional
Statement: The tool shall use an element's own `safety_margin`, when the definition gives one, in
  place of the global value for that element.
Rationale: A global value is required, and individual elements may override it.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.6; docs/spec.md §5.2
Allocated to: —
Verification: Test; success criteria: with a global margin of 0.10 and an element margin of 0.25,
  that element's demand with margin is 1.25 × demand and another element's is 1.10 × demand.
Status: Draft
```

### L1-ELA-026

```req
ID: L1-ELA-026
Level: L1
Type: Functional
Statement: The tool shall leave an element with no capacity defined unconstrained, with no capacity
  check.
Rationale: Capacity is optional on buses and contactors.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.6
Allocated to: —
Verification: Test; success criteria: a bus with no capacity carrying any demand is not reported as
  overloaded.
Status: Draft
```

### L1-ELA-027

```req
ID: L1-ELA-027
Level: L1
Type: Functional
Statement: The tool shall report a configuration as PASS only if no element is overloaded, there is
  no configuration error and no essential load is unpowered.
Rationale: DD-001 adds the essential load condition to the criterion in docs/spec.md §3.6.
Parent(s): L0-ELA-001
Source: docs/spec.md §3.6; DD-001
Allocated to: —
Verification: Test; success criteria: one configuration with each of the three conditions gives
  FAIL, and one with none gives PASS.
Status: Draft
```

### L1-ELA-028

```req
ID: L1-ELA-028
Level: L1
Type: Functional
Statement: The tool shall report each essential load that is unpowered, meaning its bus is
  de-energised or its crew switch is off.
Rationale: Naming each one shows directly which minimum equipment has been lost.
Parent(s): L0-ELA-006
Source: DD-001
Allocated to: —
Verification: Test; success criteria: with two essential loads on a dead bus and one on a
  crew-switched bus switched off, all three are listed by name.
Status: Draft
```

### L1-ELA-029

```req
ID: L1-ELA-029
Level: L1
Type: Functional
Statement: The tool shall report, for each checked element and band, the remaining margin in watts
  as `capacity − demand × (1 + margin)` and as that value's percentage of capacity.
Rationale: The specification uses remaining margin without defining it, and a percentage compares
  elements of different sizes.
Parent(s): L0-ELA-001
Source: docs/spec.md §6.2; DD-011
Allocated to: —
Verification: Test; success criteria: capacity 2000 W, demand 1000 W and margin 0.10 give a
  remaining margin of 900 W and 45 %.
Status: Draft
```

### L1-ELA-030

```req
ID: L1-ELA-030
Level: L1
Type: Functional
Statement: The tool shall identify the worst element of a configuration as the checked element and
  band with the smallest remaining margin percentage.
Rationale: One figure per scenario shows how close the configuration is to its limit.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3; DD-011
Allocated to: —
Verification: Test; success criteria: in a configuration with known margins, the element and band
  reported are those with the smallest percentage.
Status: Draft
```

### L1-ELA-031

```req
ID: L1-ELA-031
Level: L1
Type: Functional
Statement: The tool shall report voltage, power and current per band for each energised bus.
Rationale: These are the electrical quantities the engineer reads from the analysis.
Parent(s): L0-ELA-003
Source: docs/spec.md §3.7
Allocated to: —
Verification: Test; success criteria: a 28 V DC bus carrying 2800 W reports 28 V, 2800 W and 100 A,
  and a 115 V 3-phase AC bus carrying 3450 W reports 115 V, 3450 W and 10 A per phase.
Status: Draft
```

### L1-ELA-032

```req
ID: L1-ELA-032
Level: L1
Type: Constraint
Statement: The tool shall compute each result solely from the definition and the component states,
  with no time-domain simulation.
Rationale: The analysis is a static summation in the three bands.
Parent(s): L0-ELA-003
Source: docs/spec.md §1; docs/spec.md §2
Allocated to: —
Verification: Test; success criteria: repeated analysis of one configuration gives identical
  results, and no analysis request takes a time or time-step input.
Status: Draft
```

### L1-ELA-033

```req
ID: L1-ELA-033
Level: L1
Type: Constraint
Statement: The tool shall analyse each configuration exactly as stated, with no automatic
  reconfiguration, bus transfer or load shedding.
Rationale: All configurations are static and planned in advance as scenarios.
Parent(s): L0-ELA-001
Source: docs/spec.md §2
Allocated to: —
Verification: Test; success criteria: with the generator on a bus failed and its tie open, the bus
  stays de-energised, and an overloaded configuration keeps every load at its defined power.
Status: Draft
```

### L1-ELA-034

```req
ID: L1-ELA-034
Level: L1
Type: Constraint
Statement: The tool shall perform no battery endurance check.
Rationale: Amp-hour checks are out of scope for this build.
Parent(s): L0-ELA-003
Source: docs/spec.md §2; docs/spec.md §4.4
Allocated to: —
Verification: Test; success criteria: analysis results for a battery-only configuration contain no
  amp-hour, endurance or time-to-depletion quantity.
Status: Draft
```

### L1-ELA-035

```req
ID: L1-ELA-035
Level: L1
Type: Constraint
Statement: The tool shall compute a bus's own-load power from its loads' defined power in every
  configuration, with no variation by flight phase.
Rationale: Loads are always on, as defined.
Parent(s): L0-ELA-003
Source: docs/spec.md §2
Allocated to: —
Verification: Test; success criteria: a bus's own-load power is identical across all scenarios in
  which the bus is energised and no crew switch on it is off.
Status: Draft
```

### L1-ELA-036

```req
ID: L1-ELA-036
Level: L1
Type: Data
Statement: The tool shall be delivered with a sample definition of a generic twin-engine transport
  containing both passing and failing scenarios.
Rationale: The sample demonstrates the tool and its failure report.
Parent(s): L0-ELA-008
Source: docs/spec.md §5.3; docs/spec.md §8
Allocated to: —
Verification: Test; success criteria: the delivered sample loads with no error, and a batch run of
  it reports at least one PASS and at least one FAIL.
Status: Draft
```

### L1-ELA-037

```req
ID: L1-ELA-037
Level: L1
Type: Functional
Statement: The tool shall list the `*.json` definition files found in its definitions folder,
  refreshing the list on each page load.
Rationale: The engineer picks among definitions held on disk.
Parent(s): L0-ELA-002
Source: docs/spec.md §6.1; DD-024
Allocated to: —
Verification: Test; success criteria: adding a valid definition file to the folder and reloading the
  page makes it appear in the list displayed in the browser, and a file that is not `*.json` is not
  listed.
Status: Draft
```

### L1-ELA-038

```req
ID: L1-ELA-038
Level: L1
Type: Functional
Statement: The tool shall accept a definition file uploaded from the browser.
Rationale: A definition can come from outside the `definitions/` folder.
Parent(s): L0-ELA-002
Source: docs/spec.md §6.1; DD-016
Allocated to: —
Verification: Test; success criteria: a valid file uploaded from the browser appears in the
  definition list and can be opened.
Status: Draft
```

### L1-ELA-039

```req
ID: L1-ELA-039
Level: L1
Type: Functional
Statement: The tool shall reset the interactive view when the engineer switches to another
  definition.
Rationale: State changes made for one aircraft have no meaning on another.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.1
Allocated to: —
Verification: Test; success criteria: after failing a generator and switching definition, the new
  definition is displayed with all components at their default states.
Status: Draft
```

### L1-ELA-040

```req
ID: L1-ELA-040
Level: L1
Type: Functional
Statement: The tool shall draw the system automatically as a top-to-bottom layered schematic with no
  coordinates held in the definition.
Rationale: Definitions stay electrical, and any aircraft gets a schematic with no drawing effort.
Parent(s): L0-ELA-004
Source: docs/spec.md §2; docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: the sample definition, which holds no coordinate data, is
  drawn with sources above buses, buses above TRUs and TRUs above DC buses.
Status: Draft
```

### L1-ELA-041

```req
ID: L1-ELA-041
Level: L1
Type: Usability
Statement: The tool shall keep a schematic of up to 50 displayed items legible on a 1366 × 768 px
  screen, with pan and zoom available.
Rationale: The specification asks for up to about 50 items on a laptop screen. The 1366 × 768 px
  figure is a project choice that makes the requirement testable.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: a 50-item schematic at the initial zoom shows every item
  inside the viewport with no two items overlapping, and panning and zooming change the view.
Status: Draft
```

### L1-ELA-042

```req
ID: L1-ELA-042
Level: L1
Type: Constraint
Statement: The tool shall draw no individual load or circuit breaker on the schematic.
Rationale: The schematic shows distribution architecture. Circuit breakers are implicit and
  lossless.
Parent(s): L0-ELA-004
Source: docs/spec.md §2; docs/spec.md §3.2; docs/spec.md §4.10; docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: the drawn schematic of the sample definition contains no
  element for any load or circuit breaker.
Status: Draft
```

### L1-ELA-043

```req
ID: L1-ELA-043
Level: L1
Type: Functional
Statement: The tool shall show each schematic element's state by colour: green for energised, dark
  grey for de-energised, amber for overloaded in any band, and dark grey with a failure mark for a
  failed source or TRU.
Rationale: The colours give the state of the whole system at a glance.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: on one configuration holding all four states, each element has
  the colour and mark listed for its state.
Status: Draft
```

### L1-ELA-044

```req
ID: L1-ELA-044
Level: L1
Type: Functional
Statement: The tool shall label energised buses, and only energised buses, with voltage, current and
  power for an engineer-selected band that defaults to Continuous.
Rationale: Dead buses carry no meaningful values, and one band at a time keeps the schematic
  uncluttered.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: energised buses show the three values, a de-energised bus
  shows none, and changing the band changes the values shown.
Status: Draft
```

### L1-ELA-045

```req
ID: L1-ELA-045
Level: L1
Type: Functional
Statement: The tool shall state on an overloaded element which bands failed when any failed band
  differs from the displayed band.
Rationale: An overload in a band that is not displayed has to remain visible.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: a bus overloaded only in `transient` with Continuous displayed
  is amber and names the transient band.
Status: Draft
```

### L1-ELA-046

```req
ID: L1-ELA-046
Level: L1
Type: Functional
Statement: The tool shall show, on hover or tap of any schematic element, its demand, demand with
  margin, capacity and remaining margin in W with its percentage, for all three bands.
Rationale: The labels show one band, and this detail shows all three.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: hovering over a rated bus shows the 12 values, which equal the
  analysis result.
Status: Draft
```

### L1-ELA-047

```req
ID: L1-ELA-047
Level: L1
Type: Functional
Statement: The tool shall show the load and the percentage of capacity of each energised source and
  TRU.
Rationale: The engineer needs to see how hard each supply is working.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: an energised generator carrying 45000 W of 90000 W capacity
  shows that load and 50 %.
Status: Draft
```

### L1-ELA-048

```req
ID: L1-ELA-048
Level: L1
Type: Functional
Statement: The tool shall toggle a component's state when the engineer clicks a generator, APU
  generator, battery, TRU, emergency generator output, contactor, bus tie or crew switch.
Rationale: Point-and-click state changes are the means of exploring a configuration.
Parent(s): L0-ELA-004
Source: docs/spec.md §4; docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: one click on each listed kind changes its state, and a second
  click restores it.
Status: Draft
```

### L1-ELA-049

```req
ID: L1-ELA-049
Level: L1
Type: Performance
Statement: The tool shall recompute the analysis and redraw the schematic after each click with no
  other user action, completing within 1 second on the sample definition.
Rationale: This replaces "instantly" in the specification. The 1 second figure is a project choice
  that makes the requirement testable.
Parent(s): L0-ELA-004
Source: docs/spec.md §1; docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: on the sample definition, 20 consecutive clicks each update
  the display with no further action, and the slowest takes no more than 1 second.
Status: Draft
```

### L1-ELA-050

```req
ID: L1-ELA-050
Level: L1
Type: Functional
Statement: The tool shall return all components to their default states when the engineer presses
  Reset, keeping the selected band and clearing any selected scenario.
Rationale: The engineer needs a known starting point after exploring.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: after changing several states, Reset shows the same component
  states and verdict as a freshly opened definition, with the selected band unchanged and no
  scenario selected.
Status: Draft
```

### L1-ELA-051

```req
ID: L1-ELA-051
Level: L1
Type: Functional
Statement: The tool shall apply a chosen scenario's states to the schematic when the engineer
  selects it from a Load scenario control.
Rationale: A batch result can then be inspected visually.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2
Allocated to: —
Verification: Test; success criteria: selecting a scenario shows the same verdict and bus values as
  the batch result for that scenario.
Status: Draft
```

### L1-ELA-052

```req
ID: L1-ELA-052
Level: L1
Type: Functional
Statement: The tool shall show overall PASS or FAIL for the current configuration, together with
  every overload, configuration error and unpowered essential load.
Rationale: The engineer needs the verdict and its reasons in one place.
Parent(s): L0-ELA-004
Source: docs/spec.md §6.2; DD-001
Allocated to: —
Verification: Test; success criteria: a configuration with an overload and an unpowered essential
  load shows FAIL and lists both, and a passing configuration shows PASS with an empty list.
Status: Draft
```

### L1-ELA-053

```req
ID: L1-ELA-053
Level: L1
Type: Constraint
Statement: The tool shall provide no means of editing topology or loads in its user interface.
Rationale: The JSON file is edited by hand in this build.
Parent(s): L0-ELA-002
Source: docs/spec.md §2
Allocated to: —
Verification: Test; success criteria: the user interface has no control that adds, removes or
  changes a component or load in the definition, and the definition file is byte-identical after an
  interactive session.
Status: Draft
```

### L1-ELA-054

```req
ID: L1-ELA-054
Level: L1
Type: Functional
Statement: The tool shall run all scenarios of a definition on one request, from either the browser
  or the command line.
Rationale: Both a person and an automated check need to start a run.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3
Allocated to: —
Verification: Test; success criteria: one browser action and one command each give results for every
  scenario, and the two sets of results are equal.
Status: Draft
```

### L1-ELA-055

```req
ID: L1-ELA-055
Level: L1
Type: Functional
Statement: The tool shall report for each scenario its id, name, PASS or FAIL, worst element and
  band, smallest remaining margin, number of overloads counted as element-band entries,
  configuration errors and unpowered essential loads.
Rationale: These fields summarise a scenario in one row. The essential load field follows from
  DD-001.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3; DD-001
Allocated to: —
Verification: Test; success criteria: the results for the sample definition hold all these fields
  for every scenario, with values equal to those recorded in
  `tests/data/generic_twin_expected.json`.
Status: Draft
```

### L1-ELA-056

```req
ID: L1-ELA-056
Level: L1
Type: Functional
Statement: The tool shall show every failing element and band of a scenario on request from its
  batch result.
Rationale: The summary row names only the worst element.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3
Allocated to: —
Verification: Test; success criteria: expanding a scenario with several overloads lists each failing
  element and band.
Status: Draft
```

### L1-ELA-057

```req
ID: L1-ELA-057
Level: L1
Type: Functional
Statement: The tool shall open a scenario in the interactive view from its batch result.
Rationale: The engineer can move from a failed row to the schematic of that configuration.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3
Allocated to: —
Verification: Test; success criteria: activating a result row shows that scenario on the schematic
  with the same verdict.
Status: Draft
```

### L1-ELA-058

```req
ID: L1-ELA-058
Level: L1
Type: Interface
Statement: The tool shall export batch results in both CSV and JSON formats.
Rationale: Results are needed as evidence and in other tools.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3
Allocated to: —
Verification: Test; success criteria: both exports of a sample run parse and hold the same values as
  the displayed results.
Status: Draft
```

### L1-ELA-059

```req
ID: L1-ELA-059
Level: L1
Type: Interface
Statement: The tool shall end a command-line batch run with exit code 0 when all scenarios pass, 1
  when at least one fails, and 2 for an invalid definition or bad usage.
Rationale: A non-zero code makes the run usable in automated checks, and a separate code tells
  failed analysis from bad input.
Parent(s): L0-ELA-005
Source: docs/spec.md §6.3; DD-018
Allocated to: —
Verification: Test; success criteria: runs on an all-passing definition, on the sample definition,
  and on an invalid definition give exit codes 0, 1 and 2.
Status: Draft
```

### L1-ELA-060

```req
ID: L1-ELA-060
Level: L1
Type: Usability
Statement: The tool shall start with one command and serve its whole user interface to a web
  browser.
Rationale: The engineer needs no separate front-end server.
Parent(s): L0-ELA-007
Source: docs/spec.md §7.3
Allocated to: —
Verification: Test; success criteria: after the single documented command, a browser pointed at the
  tool shows the working interface.
Status: Draft
```

### L1-ELA-061

```req
ID: L1-ELA-061
Level: L1
Type: Constraint
Statement: The tool shall run as a local service reachable only from the local machine, with no
  authentication.
Rationale: This is a local single-user tool.
Parent(s): L0-ELA-007
Source: DD-016
Allocated to: —
Verification: Test; success criteria: started with the documented command, the tool listens only on
  the loopback address and answers requests that carry no credentials.
Status: Draft
```

### L1-ELA-062

```req
ID: L1-ELA-062
Level: L1
Type: Constraint
Statement: The tool shall need no compile, bundle or other build step for its user interface.
Rationale: Serving the source files directly removes the need for a front-end toolchain.
Parent(s): L0-ELA-007
Source: docs/spec.md §7.3; DD-003
Allocated to: —
Verification: Inspection; success criteria: the repository holds no bundler or transpiler
  configuration, and the served front-end files are the source files.
Status: Draft
```

### L1-ELA-063

```req
ID: L1-ELA-063
Level: L1
Type: Constraint
Statement: The tool shall run its analysis with no web server or browser present.
Rationale: This lets the analysis be tested and run from the command line independently.
Parent(s): L0-ELA-005
Source: docs/spec.md §7.1
Allocated to: —
Verification: Test; success criteria: a command-line batch run completes with no server running and
  with no network access.
Status: Draft
```

### L1-ELA-064

```req
ID: L1-ELA-064
Level: L1
Type: Usability
Statement: The tool shall be delivered with documentation covering installation, running, the JSON
  format and how to add a new aircraft.
Rationale: Definitions are written by hand, so the format has to be documented.
Parent(s): L0-ELA-007
Source: docs/spec.md §8
Allocated to: —
Verification: Test; success criteria: the delivered README has a section for each of the four
  topics.
Status: Draft
```

### L1-ELA-065

```req
ID: L1-ELA-065
Level: L1
Type: Constraint
Statement: The tool shall be delivered with automated tests covering energisation, TRU efficiency,
  bus ties, source failures, AC paralleling detection, DC sharing, battery priority, safety margin,
  crew switch, validation errors and every sample scenario.
Rationale: These are the behaviours the specification names as needing test evidence.
Parent(s): L0-ELA-009
Source: docs/spec.md §7.1; docs/spec.md §8
Allocated to: —
Verification: Test; success criteria: `pytest tests -m "not meta"`, run in a subprocess, passes, and
  the suite has at least one test for each named topic and for each sample scenario.
Status: Draft
```

### L1-ELA-066

```req
ID: L1-ELA-066
Level: L1
Type: Constraint
Statement: The tool shall be delivered with automated browser tests for its user interface
  requirements.
Rationale: Every user interface requirement gets a repeatable test.
Parent(s): L0-ELA-009
Source: DD-003
Allocated to: —
Verification: Test; success criteria: `pytest tests -m "not meta"`, run in a subprocess, drives a
  real browser against the running tool and passes.
Status: Draft
```

<!-- END SECTION L1 -->

## L2 component requirements

## C-MODEL: definition schema

<!-- BEGIN SECTION MOD-TOPLEVEL -->

### L2-MOD-001

```req
ID: L2-MOD-001
Level: L2
Type: Data
Statement: The schema shall require the top-level keys `meta`, `settings`, `sources`, `buses`,
  `trus`, `contactors`, `loads` and `scenarios`.
Rationale: docs/spec.md §5.1 places everything in these collections. A list may be empty, for
  example `trus` on an aircraft with no TRUs.
Parent(s): L1-ELA-001
Source: docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: removing each of the 8 keys in turn from a valid definition is
  rejected with an error naming that key, and the unmodified definition is accepted.
Status: Draft
```

### L2-MOD-002

```req
ID: L2-MOD-002
Level: L2
Type: Data
Statement: The schema shall require `meta.aircraft` and `meta.revision`.
Rationale: These identify the definition.
Parent(s): L1-ELA-001
Source: docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a definition lacking either key is rejected, and a definition
  holding both is accepted.
Status: Draft
```

### L2-MOD-003

```req
ID: L2-MOD-003
Level: L2
Type: Data
Statement: The schema shall treat `meta.description` as optional free text.
Rationale: docs/spec.md §5.1 shows it, and nothing depends on it.
Parent(s): L1-ELA-001
Source: docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a definition lacking `meta.description` is accepted, and one
  holding it gives no unknown-key warning.
Status: Draft
```

### L2-MOD-004

```req
ID: L2-MOD-004
Level: L2
Type: Data
Statement: The schema shall hold power, capacity and voltage values, margins and efficiencies with
  no unit conversion, as watts, volts and decimals.
Rationale: The units are fixed by the file format.
Parent(s): L1-ELA-002
Source: docs/spec.md §5
Allocated to: C-MODEL
Verification: Test; success criteria: parsing `135000` as a capacity, `115` as a voltage, `0.10` as
  a margin and `0.85` as an efficiency gives those same numeric values.
Status: Draft
```

### L2-MOD-005

```req
ID: L2-MOD-005
Level: L2
Type: Data
Statement: The schema shall require `settings.safety_margin` as a finite JSON number, with strict
  parsing that accepts no boolean, numeric string or NaN.
Rationale: A global value is required, whereas per-element values are optional. The same strict rule
  applies to every numeric key.
Parent(s): L1-ELA-025
Source: docs/spec.md §3.6; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a definition lacking `settings.safety_margin` is rejected, the
  values `true`, `"0.10"` and NaN are each rejected, and `0.10` is accepted.
Status: Draft
```

### L2-MOD-006

```req
ID: L2-MOD-006
Level: L2
Type: Data
Statement: The schema shall require each `power` and each `capacity` object to hold numeric values
  for all of `transient`, `short_term` and `continuous`.
Rationale: The three band keys are fixed.
Parent(s): L1-ELA-011
Source: docs/spec.md §3.1; DD-010
Allocated to: C-MODEL
Verification: Test; success criteria: a `power` object and a `capacity` object each lacking one band
  are rejected in turn for each band, and objects with all three are accepted.
Status: Draft
```

### L2-MOD-007

```req
ID: L2-MOD-007
Level: L2
Type: Data
Statement: The schema shall treat `settings.bands` as optional, with the default labels `Transient`,
  `5 s` and `Continuous` for `transient`, `short_term` and `continuous`.
Rationale: Labels are display text with sensible defaults.
Parent(s): L1-ELA-011
Source: docs/spec.md §5.1; DD-010
Allocated to: C-MODEL
Verification: Test; success criteria: a definition omitting `settings.bands` parses with those three
  labels, and one giving a `label` of `Peak` for `transient` parses with `Peak`.
Status: Draft
```

### L2-MOD-008

```req
ID: L2-MOD-008
Level: L2
Type: Data
Statement: The schema shall accept an optional numeric `duration_s` on each band entry of
  `settings.bands`.
Rationale: docs/spec.md §5.1 shows it on `short_term`. It is descriptive and has no effect on the
  analysis.
Parent(s): L1-ELA-011
Source: docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a definition with `duration_s` 5 on `short_term` gives no
  unknown-key warning and gives the same analysis result as one without it.
Status: Draft
```

<!-- END SECTION MOD-TOPLEVEL -->

<!-- BEGIN SECTION MOD-SOURCES -->

### L2-MOD-009

```req
ID: L2-MOD-009
Level: L2
Type: Data
Statement: The schema shall require a string `id` and a string `name` on every source, bus, TRU,
  contactor and load.
Rationale: All components have a unique id and a readable name.
Parent(s): L1-ELA-005
Source: docs/spec.md §4; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: removing `id` or `name` from one element of each of the 5
  collections gives at least one error at the parent path naming the key. Checks depending on the
  missing key are skipped for that element, and a removed `id` may also report the references it
  breaks.
Status: Draft
```

### L2-MOD-010

```req
ID: L2-MOD-010
Level: L2
Type: Data
Statement: The schema shall accept source `kind` values `engine_generator`, `apu_generator`,
  `emergency_generator` and `battery` only.
Rationale: These are the four source kinds in the specification.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.1 to §4.4; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: each of the 4 values is accepted and the value `fuel_cell` is
  rejected.
Status: Draft
```

### L2-MOD-011

```req
ID: L2-MOD-011
Level: L2
Type: Data
Statement: The schema shall require `output`, `voltage` and `capacity` on every source.
Rationale: `output` is `AC` or `DC`. Capacity is required on sources by §5.2. L2-VAL-033 limits
  which kinds may take each `output`.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.1 to §4.4; docs/spec.md §5.1; docs/spec.md §5.2
Allocated to: C-MODEL
Verification: Test; success criteria: removing each of the 3 keys in turn is rejected, and an
  `output` of `AC` and of `DC` are each accepted on an emergency generator.
Status: Draft
```

### L2-MOD-012

```req
ID: L2-MOD-012
Level: L2
Type: Data
Statement: The schema shall require an integer `engine` number on each source of kind
  `engine_generator`.
Rationale: The engine number orders generators on the schematic.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.1; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: an engine generator lacking `engine` is rejected, and an APU
  generator lacking `engine` is accepted.
Status: Draft
```

### L2-MOD-013

```req
ID: L2-MOD-013
Level: L2
Type: Data
Statement: The schema shall represent each emergency generator output as a separate source entry
  with its own `output`, `capacity` and `default_state`.
Rationale: A RAT with AC and DC outputs is two sources, as in docs/spec.md §5.1.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.3; DD-008
Allocated to: C-MODEL
Verification: Test; success criteria: a definition with one AC and one DC `emergency_generator`
  entry parses as 2 sources with independent capacities and states.
Status: Draft
```

### L2-MOD-014

```req
ID: L2-MOD-014
Level: L2
Type: Data
Statement: The schema shall require `default_state` with value `operative` or `failed` on engine
  generator, APU generator and battery sources.
Rationale: The allowed values come from DD-009. `default_state` is not among the keys §5.2 names as
  optional.
Parent(s): L1-ELA-005
Source: docs/spec.md §5.2; DD-009
Allocated to: C-MODEL
Verification: Test; success criteria: an engine generator lacking `default_state` is rejected, a
  battery with `failed` is accepted, and an APU generator with `available` is rejected.
Status: Draft
```

### L2-MOD-015

```req
ID: L2-MOD-015
Level: L2
Type: Data
Statement: The schema shall treat `default_state` on an emergency generator as optional with value
  `available` or `unavailable`, honoured when present and defaulting to `unavailable` when absent.
Rationale: The allowed values come from DD-009. The rule comes from DD-021, which settles the
  difference between docs/spec.md §4.3 and §5.1.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.3; docs/spec.md §9; DD-009; DD-021
Allocated to: C-MODEL
Verification: Test; success criteria: an emergency generator lacking `default_state` parses as
  `unavailable`, one giving `available` parses as `available`, and one with `operative` is rejected.
Status: Draft
```

### L2-MOD-016

```req
ID: L2-MOD-016
Level: L2
Type: Data
Statement: The schema shall treat `phases` as an optional integer on AC sources and AC buses,
  defaulting to 3, with `phases` on a DC element being an unknown key.
Rationale: The AC current formula divides by `phases`.
Parent(s): L1-ELA-031
Source: docs/spec.md §3.7; docs/spec.md §4.1; docs/spec.md §4.5
Allocated to: C-MODEL
Verification: Test; success criteria: an AC bus omitting `phases` parses as 3, one giving 1 parses
  as 1, and a DC bus giving `phases` gets an unknown-key warning.
Status: Draft
```

<!-- END SECTION MOD-SOURCES -->

<!-- BEGIN SECTION MOD-NETWORK -->

### L2-MOD-017

```req
ID: L2-MOD-017
Level: L2
Type: Data
Statement: The schema shall require `type` with value `AC` or `DC`, `role` and `voltage` on every
  bus.
Rationale: docs/spec.md §4.5 and §4.6 call the role a type. The key in §5.1 is `role`.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.5; docs/spec.md §4.6; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: removing each key in turn is rejected, and a `type` of `HVDC`
  is rejected.
Status: Draft
```

### L2-MOD-018

```req
ID: L2-MOD-018
Level: L2
Type: Data
Statement: The schema shall accept bus `role` values `main`, `essential`, `emergency` and `other` on
  AC buses, and those four plus `battery` on DC buses.
Rationale: The role is a descriptive tag used for layout and display.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.5; docs/spec.md §4.6
Allocated to: C-MODEL
Verification: Test; success criteria: each listed role is accepted on its bus type, `battery` is
  rejected on an AC bus, and `spare` is rejected on both.
Status: Draft
```

### L2-MOD-019

```req
ID: L2-MOD-019
Level: L2
Type: Data
Statement: The schema shall treat `capacity` as optional on buses and contactors.
Rationale: An element with no capacity is unconstrained.
Parent(s): L1-ELA-026
Source: docs/spec.md §4.5; docs/spec.md §4.6; docs/spec.md §4.8; docs/spec.md §5.2
Allocated to: C-MODEL
Verification: Test; success criteria: a bus and a contactor with no `capacity` parse with capacity
  absent, and each with a full `capacity` object parses with it present.
Status: Draft
```

### L2-MOD-020

```req
ID: L2-MOD-020
Level: L2
Type: Data
Statement: The schema shall accept an optional boolean `crew_switch` on a bus, defaulting to false.
Rationale: Only buses declared with it have a crew switch.
Parent(s): L1-ELA-016
Source: docs/spec.md §4.9; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a bus omitting `crew_switch` parses as false, and one giving
  `true` parses as true.
Status: Draft
```

### L2-MOD-021

```req
ID: L2-MOD-021
Level: L2
Type: Data
Statement: The schema shall require `input_bus`, `output_bus`, `efficiency`, `capacity` and
  `default_state` on every TRU, with `default_state` value `operative` or `failed`.
Rationale: A TRU always hangs off buses, so a RAT feeds a TRU through a small dedicated AC bus.
  `capacity` is the output capacity.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.7; docs/spec.md §5.1; DD-007; DD-009
Allocated to: C-MODEL
Verification: Test; success criteria: removing each of the 5 keys in turn is rejected, and a TRU
  `default_state` of `closed` is rejected.
Status: Draft
```

### L2-MOD-022

```req
ID: L2-MOD-022
Level: L2
Type: Data
Statement: The schema shall require `kind` with value `source`, `bus_tie` or `tru`, single-valued
  `from` and `to`, and `default_state` with value `closed` or `open`, on every contactor, the input
  or output role of a `tru` contactor being decided by which bus it joins and not by `from` and
  `to`.
Rationale: A contactor connects exactly two nodes.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.8; docs/spec.md §5.1; DD-009
Allocated to: C-MODEL
Verification: Test; success criteria: removing each of the 4 keys in turn is rejected, a list given
  for `to` is rejected, and a `default_state` of `on` is rejected.
Status: Draft
```

### L2-MOD-023

```req
ID: L2-MOD-023
Level: L2
Type: Data
Statement: The schema shall offer no key that connects a source to a bus other than a contactor
  record.
Rationale: A contactor exists everywhere a source connects to a bus.
Parent(s): L1-ELA-005
Source: docs/spec.md §4.8
Allocated to: C-MODEL
Verification: Test; success criteria: a source carrying a `bus` key gains no connection to that bus
  and the key is reported as an unknown-key warning.
Status: Draft
```

### L2-MOD-024

```req
ID: L2-MOD-024
Level: L2
Type: Data
Statement: The schema shall accept an optional numeric `safety_margin` on each source, TRU, bus and
  contactor.
Rationale: A per-element value overrides the global value.
Parent(s): L1-ELA-025
Source: docs/spec.md §3.6; docs/spec.md §5.2
Allocated to: C-MODEL
Verification: Test; success criteria: one element of each of the 4 collections with `safety_margin`
  0.25 parses with no unknown-key warning and holds 0.25.
Status: Draft
```

<!-- END SECTION MOD-NETWORK -->

<!-- BEGIN SECTION MOD-LOADS-SCENARIOS -->

### L2-MOD-025

```req
ID: L2-MOD-025
Level: L2
Type: Data
Statement: The schema shall require `bus` as a single bus id and `power` on every load.
Rationale: Each load is connected to exactly one bus.
Parent(s): L1-ELA-016
Source: docs/spec.md §3.2; docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a load lacking `bus` or `power` is rejected, and a load with a
  list of two bus ids is rejected.
Status: Draft
```

### L2-MOD-026

```req
ID: L2-MOD-026
Level: L2
Type: Data
Statement: The schema shall accept an optional boolean `essential` on a load, defaulting to false.
Rationale: Essential loads carry the check added by DD-001.
Parent(s): L1-ELA-028
Source: DD-001
Allocated to: C-MODEL
Verification: Test; success criteria: a load omitting `essential` parses as false, and one giving
  `true` parses as true.
Status: Draft
```

### L2-MOD-027

```req
ID: L2-MOD-027
Level: L2
Type: Data
Statement: The schema shall require `id`, `name` and a `states` object on every scenario.
Rationale: An empty `states` object describes the default configuration.
Parent(s): L1-ELA-001
Source: docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a scenario lacking any of the 3 keys is rejected, and a
  scenario with empty `states` is accepted.
Status: Draft
```

### L2-MOD-028

```req
ID: L2-MOD-028
Level: L2
Type: Data
Statement: The schema shall treat a scenario's `description` as optional free text.
Rationale: Scenario S02 in docs/spec.md §5.1 has no description.
Parent(s): L1-ELA-001
Source: docs/spec.md §5.1
Allocated to: C-MODEL
Verification: Test; success criteria: a scenario lacking `description` is accepted, and one holding
  it gives no unknown-key warning.
Status: Draft
```

### L2-MOD-029

```req
ID: L2-MOD-029
Level: L2
Type: Constraint
Statement: The schema shall define no coordinate or position key on any element.
Rationale: The schematic layout is automatic.
Parent(s): L1-ELA-040
Source: docs/spec.md §2; docs/spec.md §6.2
Allocated to: C-MODEL
Verification: Test; success criteria: the model's generated schema contains no key named `x`, `y`,
  `position` or `coordinates`, and a definition using `x` on a bus gets an unknown-key warning.
Status: Draft
```

### L2-MOD-030

```req
ID: L2-MOD-030
Level: L2
Type: Constraint
Statement: The schema shall define no circuit breaker element.
Rationale: Circuit breakers exist only implicitly as the lossless load-to-bus link.
Parent(s): L1-ELA-042
Source: docs/spec.md §3.2; docs/spec.md §4.10
Allocated to: C-MODEL
Verification: Test; success criteria: the model's generated schema contains no collection or key for
  circuit breakers.
Status: Draft
```

### L2-MOD-031

```req
ID: L2-MOD-031
Level: L2
Type: Constraint
Statement: The schema shall define no amp-hour or endurance key on a battery.
Rationale: Battery capacity is power per band only.
Parent(s): L1-ELA-034
Source: docs/spec.md §2; docs/spec.md §4.4
Allocated to: C-MODEL
Verification: Test; success criteria: a battery with an `amp_hours` key gets an unknown-key warning
  and the same analysis result as one without it.
Status: Draft
```

### L2-MOD-032

```req
ID: L2-MOD-032
Level: L2
Type: Constraint
Statement: The schema shall define no flight-phase key on a load or scenario.
Rationale: Loads are always on, as defined.
Parent(s): L1-ELA-035
Source: docs/spec.md §2
Allocated to: C-MODEL
Verification: Test; success criteria: a load with a `flight_phase` key gets an unknown-key warning
  and the same analysis result as one without it.
Status: Draft
```

### L2-MOD-033

```req
ID: L2-MOD-033
Level: L2
Type: Constraint
Statement: The schema shall be implemented as Pydantic models in `ela/model.py`.
Rationale: Pydantic is the mandated schema technology, and the file is fixed by docs/plan.md.
Parent(s): L1-ELA-006
Source: docs/spec.md §7.1
Allocated to: C-MODEL
Verification: Test; success criteria: `ela/model.py` exists, and importing it exposes a definition
  model that is a subclass of `pydantic.BaseModel`.
Status: Draft
```

<!-- END SECTION MOD-LOADS-SCENARIOS -->

## C-VALID: validator

<!-- BEGIN SECTION VAL-REPORTING -->

### L2-VAL-001

```req
ID: L2-VAL-001
Level: L2
Type: Functional
Statement: The validator shall return lists of errors and warnings for any parsed JSON document,
  raising no exception for invalid content. A file that does not parse as JSON is reported by its
  caller as one error at path `$`.
Rationale: Callers present problems to the engineer, so an exception would lose all but the first.
Parent(s): L1-ELA-006
Source: docs/spec.md §5.2; docs/spec.md §7.1
Allocated to: C-VALID
Verification: Test; success criteria: 20 malformed documents, including one that is a JSON list and
  one that is an empty object, each return a non-empty error list and raise nothing.
Status: Draft
```

### L2-VAL-002

```req
ID: L2-VAL-002
Level: L2
Type: Functional
Statement: The validator shall return every error in the document in one call.
Rationale: The validator returns all errors at once.
Parent(s): L1-ELA-007
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: a document seeded with a missing key, a duplicate id, a
  dangling reference, a reversed TRU and an AC-to-DC contactor returns at least one error for each
  of the 5 faults in one call.
Status: Draft
```

### L2-VAL-003

```req
ID: L2-VAL-003
Level: L2
Type: Functional
Statement: The validator shall give each error and warning a `$`-rooted JSON path and a readable
  message.
Rationale: The path locates the fault in a hand-edited file.
Parent(s): L1-ELA-007
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: an unknown bus on the fourth load gives path `$.loads[3].bus`
  and a message naming the unknown id.
Status: Draft
```

### L2-VAL-004

```req
ID: L2-VAL-004
Level: L2
Type: Functional
Statement: The validator shall return a usable definition only when the error list is empty.
Rationale: An invalid definition is never opened.
Parent(s): L1-ELA-008
Source: docs/spec.md §5.2; docs/spec.md §6.1
Allocated to: C-VALID
Verification: Test; success criteria: a document with one error returns no definition, and a
  document with warnings only returns a definition and the warnings.
Status: Draft
```

### L2-VAL-005

```req
ID: L2-VAL-005
Level: L2
Type: Constraint
Statement: The validator shall be implemented in `ela/validate.py`.
Rationale: The file is fixed by docs/plan.md.
Parent(s): L1-ELA-006
Source: docs/spec.md §7.1
Allocated to: C-VALID
Verification: Test; success criteria: `ela/validate.py` exists and exposes the validation entry
  point.
Status: Draft
```

### L2-VAL-006

```req
ID: L2-VAL-006
Level: L2
Type: Constraint
Statement: The validator test suite shall hold pytest tests under `tests/` for every error and
  warning condition in the C-VALID requirements.
Rationale: Validation errors are a topic the specification names as needing test evidence.
Parent(s): L1-ELA-065
Source: docs/spec.md §7.1
Allocated to: C-VALID
Verification: Test; success criteria: `pytest tests -m "not meta"`, run in a subprocess, passes, and
  at least one collected test exists for each error and warning condition.
Status: Draft
```

### L2-VAL-031

```req
ID: L2-VAL-031
Level: L2
Type: Interface
Statement: The validator shall expose `validate(doc)` in `ela.validate`, returning a result with
  `errors` and `warnings`, each entry holding `path` and `message`, and `definition`, which is
  `None` when the document is rejected.
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-006
Source: DD-024
Allocated to: C-VALID
Verification: Test; success criteria: `ela.validate.validate` on a valid document gives empty
  `errors` and a `definition`, and on an invalid document gives entries with `path` and `message`
  and `definition` `None`.
Status: Draft
```

<!-- END SECTION VAL-REPORTING -->

<!-- BEGIN SECTION VAL-STRUCTURE -->

### L2-VAL-007

```req
ID: L2-VAL-007
Level: L2
Type: Functional
Statement: The validator shall report each missing required key as at least one error at the parent
  path naming the key. Checks depending on the missing key are skipped for that element, and a
  removed `id` may also report the references it breaks.
Rationale: Missing required keys are errors.
Parent(s): L1-ELA-006
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: removing each required key other than `id` of each collection
  gives exactly one error at the path of the parent object naming the key, and removing an `id`
  gives at least one such error.
Status: Draft
```

### L2-VAL-008

```req
ID: L2-VAL-008
Level: L2
Type: Functional
Statement: The validator shall report an error for each value of the wrong type or outside its
  allowed values, accepting as a number only a finite JSON number and so rejecting booleans, numeric
  strings, NaN and infinities.
Rationale: The schema's enumerations and types are enforced.
Parent(s): L1-ELA-006
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: the string `"0.85"` for `efficiency`, a `kind` of `fuel_cell`,
  `true` for `safety_margin`, `"yes"` for `crew_switch` and NaN for a band value each give one error
  at that key's path.
Status: Draft
```

### L2-VAL-009

```req
ID: L2-VAL-009
Level: L2
Type: Functional
Statement: The validator shall report an error for each id that is repeated across sources, buses,
  TRUs, contactors and loads, and for each scenario id repeated among scenarios.
Rationale: Components are addressed by id, including in `states`, so ids are unique across
  collections.
Parent(s): L1-ELA-006
Source: docs/spec.md §4; docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: a bus and a TRU sharing an id give one error, two scenarios
  sharing an id give one error, and a scenario sharing an id with a bus gives none.
Status: Draft
```

### L2-VAL-010

```req
ID: L2-VAL-010
Level: L2
Type: Functional
Statement: The validator shall report a band missing from a `power` or `capacity` object as one
  error at that object's path, naming the band.
Rationale: L2-MOD-006 states the rule, and this states how it is reported.
Parent(s): L1-ELA-011
Source: docs/spec.md §3.1; DD-010
Allocated to: C-VALID
Verification: Test; success criteria: a load lacking `short_term` gives one error at that load's
  `power` path naming the band.
Status: Draft
```

### L2-VAL-011

```req
ID: L2-VAL-011
Level: L2
Type: Functional
Statement: The validator shall report a missing `capacity` on a source or TRU as one error at that
  element's path.
Rationale: L2-MOD-011 and L2-MOD-021 state the rule, and this states how it is reported.
Parent(s): L1-ELA-006
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: removing `capacity` from a source and from a TRU gives 2
  errors, and removing it from a bus and from a contactor gives none.
Status: Draft
```

<!-- END SECTION VAL-STRUCTURE -->

<!-- BEGIN SECTION VAL-VALUES -->

### L2-VAL-012

```req
ID: L2-VAL-012
Level: L2
Type: Functional
Statement: The validator shall report an error for each negative `power` or `capacity` value.
Rationale: Negative power and capacity have no meaning here.
Parent(s): L1-ELA-011
Source: DD-010
Allocated to: C-VALID
Verification: Test; success criteria: a load with `transient` −1 gives one error, and a load with
  `transient` 0 gives none.
Status: Draft
```

### L2-VAL-013

```req
ID: L2-VAL-013
Level: L2
Type: Constraint
Statement: The validator shall raise neither an error nor a warning for the numeric ordering of a
  load's or capacity's bands.
Rationale: The ordering is typical but the tool must not enforce it.
Parent(s): L1-ELA-012
Source: docs/spec.md §3.1; DD-010
Allocated to: C-VALID
Verification: Test; success criteria: a load with `continuous` greater than `transient` gives an
  empty error list and no warning about band ordering.
Status: Draft
```

### L2-VAL-014

```req
ID: L2-VAL-014
Level: L2
Type: Functional
Statement: The validator shall report an error for a TRU `efficiency` outside `0 < η ≤ 1`.
Rationale: Efficiency divides output power and cannot exceed 1.
Parent(s): L1-ELA-006
Source: docs/spec.md §4.7
Allocated to: C-VALID
Verification: Test; success criteria: efficiencies 0, −0.1 and 1.01 each give one error, and 1.0 and
  0.01 give none.
Status: Draft
```

### L2-VAL-015

```req
ID: L2-VAL-015
Level: L2
Type: Functional
Statement: The validator shall report an error for each value outside its range, the ranges being
  `voltage > 0`, `phases ≥ 1` and `safety_margin ≥ 0`.
Rationale: These values are divisors or would weaken the criterion. The ranges are recorded as an
  assumption.
Parent(s): L1-ELA-006
Source: docs/spec.md §3.7
Allocated to: C-VALID
Verification: Test; success criteria: `voltage` 0, `phases` 0 and `safety_margin` −0.1 each give one
  error, and `safety_margin` 0 gives none.
Status: Draft
```

### L2-VAL-016

```req
ID: L2-VAL-016
Level: L2
Type: Functional
Statement: The validator shall report an error for a definition holding more than one
  `apu_generator` source.
Rationale: The specification allows one APU generator per aircraft. The reading is recorded as an
  assumption.
Parent(s): L1-ELA-004
Source: docs/spec.md §4.2
Allocated to: C-VALID
Verification: Test; success criteria: two APU generators give one error, and zero or one give none.
Status: Draft
```

### L2-VAL-017

```req
ID: L2-VAL-017
Level: L2
Type: Functional
Statement: The validator shall report an error for two engine generators with the same `engine`
  number.
Rationale: The specification allows one generator per engine. The reading is recorded as an
  assumption.
Parent(s): L1-ELA-003
Source: docs/spec.md §4.1
Allocated to: C-VALID
Verification: Test; success criteria: two generators on engine 1 give one error, and generators on
  engines 1 to 8 give none.
Status: Draft
```

### L2-VAL-033

```req
ID: L2-VAL-033
Level: L2
Type: Functional
Statement: The validator shall report an error for a battery with `output` AC, or an engine or APU
  generator with `output` DC. When the same source also breaks L2-VAL-020, both errors are reported,
  each at its own path.
Rationale: Engine and APU generators are AC sources and batteries are DC sources. Only an emergency
  generator can take either. Each error is true, so reporting both keeps the validator free of a
  suppression rule.
Parent(s): L1-ELA-006
Source: docs/spec.md §4.1; docs/spec.md §4.2; docs/spec.md §4.4
Allocated to: C-VALID
Verification: Test; success criteria: a battery with `output` AC on an AC bus, an engine generator
  with `output` DC on a DC bus and an APU generator with `output` DC on a DC bus each give one error
  at that key's path, a battery with `output` AC on a DC bus gives that error and the L2-VAL-020
  error at the contactor's path, and an emergency generator with either value gives none.
Status: Draft
```

<!-- END SECTION VAL-VALUES -->

<!-- BEGIN SECTION VAL-REFERENCES -->

### L2-VAL-018

```req
ID: L2-VAL-018
Level: L2
Type: Functional
Statement: The validator shall report an error for each dangling reference in `loads[].bus`,
  `trus[].input_bus`, `trus[].output_bus`, `contactors[].from` or `contactors[].to`.
Rationale: A load on a bus that does not exist is the specification's own example.
Parent(s): L1-ELA-006
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: one unknown id placed in each of the 5 keys gives at least one
  error at each of the 5 paths.
Status: Draft
```

### L2-VAL-019

```req
ID: L2-VAL-019
Level: L2
Type: Functional
Statement: The validator shall report an error for a TRU whose `input_bus` is not an AC bus or whose
  `output_bus` is not a DC bus.
Rationale: A TRU connected DC to AC is an error.
Parent(s): L1-ELA-006
Source: docs/spec.md §4.7; docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: swapping the two keys on a valid TRU gives errors at both
  paths, and the unswapped TRU gives none.
Status: Draft
```

### L2-VAL-020

```req
ID: L2-VAL-020
Level: L2
Type: Functional
Statement: The validator shall report an error for a contactor joining an AC node to a DC node.
Rationale: A TRU node counts as AC at the contactor joining its `input_bus` and DC at the contactor
  joining its `output_bus`, whichever way `from` and `to` are written. A source node takes its
  `output`. A source that also breaks L2-VAL-033 gets both errors, each at its own path.
Parent(s): L1-ELA-006
Source: docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: a tie between an AC bus and a DC bus gives one error, a DC
  battery contactor to an AC bus gives one error, a normal TRU input and output give none, and a TRU
  input contactor written from the TRU to its input bus gives none.
Status: Draft
```

### L2-VAL-021

```req
ID: L2-VAL-021
Level: L2
Type: Functional
Statement: The validator shall report an error for a contactor whose endpoints do not suit its
  `kind`, where `source` joins a source and a bus, `bus_tie` joins two buses and `tru` joins a bus
  and a TRU.
Rationale: Extends "incompatible nodes" with the definitions in §4.8. The reading is recorded as an
  assumption.
Parent(s): L1-ELA-006
Source: docs/spec.md §4.8; docs/spec.md §5.2
Allocated to: C-VALID
Verification: Test; success criteria: a `bus_tie` from a source to a bus gives one error, and a
  `tru` contactor between two buses gives one error.
Status: Draft
```

### L2-VAL-022

```req
ID: L2-VAL-022
Level: L2
Type: Functional
Statement: The validator shall report an error for a contactor whose `from` equals its `to`.
Rationale: A contactor connects exactly two nodes.
Parent(s): L1-ELA-006
Source: docs/spec.md §4.8
Allocated to: C-VALID
Verification: Test; success criteria: a contactor from `AC1` to `AC1` gives one error.
Status: Draft
```

### L2-VAL-023

```req
ID: L2-VAL-023
Level: L2
Type: Functional
Statement: The validator shall report an error for a TRU whose `tru` contactors are not exactly one
  joining its `input_bus` and one joining its `output_bus`. A contactor breaking this and L2-VAL-021
  is reported once.
Rationale: This gives one energisation rule. A RAT output feeding a TRU directly fails this check,
  so it goes through a small dedicated AC bus.
Parent(s): L1-ELA-006
Source: docs/spec.md §4.3; DD-007
Allocated to: C-VALID
Verification: Test; success criteria: a TRU with no input contactor, one with two output contactors,
  and one with a second output contactor to another DC bus each give at least one error naming the
  TRU, an input contactor from a RAT source gives exactly one error, and a RAT feeding a dedicated
  bus with a TRU on it gives none.
Status: Draft
```

<!-- END SECTION VAL-REFERENCES -->

<!-- BEGIN SECTION VAL-SCENARIOS -->

### L2-VAL-024

```req
ID: L2-VAL-024
Level: L2
Type: Functional
Statement: The validator shall report an error for each scenario `states` key that matches no
  stateful component.
Rationale: Stateful components are sources, TRUs, contactors and crew-switched buses, so a load id
  or a bus with no crew switch is not a valid key.
Parent(s): L1-ELA-010
Source: docs/spec.md §5.2; DD-009
Allocated to: C-VALID
Verification: Test; success criteria: an unknown id, a load id and a bus lacking `crew_switch` each
  give one error at path `$.scenarios[n].states.<key>`.
Status: Draft
```

### L2-VAL-025

```req
ID: L2-VAL-025
Level: L2
Type: Functional
Statement: The validator shall report an error for each scenario `states` value invalid for its
  component.
Rationale: Valid values: `operative` or `failed` for engine, APU, battery and TRU; `available` or
  `unavailable` for emergency generator; `closed` or `open` for contactor; `on` or `off` for a
  crew-switched bus.
Parent(s): L1-ELA-010
Source: docs/spec.md §4; DD-009
Allocated to: C-VALID
Verification: Test; success criteria: for each of the 4 value families, each valid value gives no
  error, and a value from another family gives one error.
Status: Draft
```

### L2-VAL-026

```req
ID: L2-VAL-026
Level: L2
Type: Interface
Statement: The validator shall expose its `states` check as a callable shared by scenario validation
  and the interactive analysis request.
Rationale: One check guarantees the same rule in both places.
Parent(s): L1-ELA-010
Source: DD-009
Allocated to: C-VALID
Verification: Test; success criteria: the callable, given a `states` object with one unknown key and
  one bad value, returns 2 errors, and scenario validation returns the same 2 errors for that
  object.
Status: Draft
```

<!-- END SECTION VAL-SCENARIOS -->

<!-- BEGIN SECTION VAL-WARNINGS -->

### L2-VAL-027

```req
ID: L2-VAL-027
Level: L2
Type: Functional
Statement: The validator shall report a warning, rather than an error, for each unknown key.
Rationale: Unknown keys are ignored with a warning.
Parent(s): L1-ELA-009
Source: docs/spec.md §5.2; DD-017
Allocated to: C-VALID
Verification: Test; success criteria: an unknown key at top level and one on a bus each give one
  warning naming the key, and the error list is empty.
Status: Draft
```

### L2-VAL-028

```req
ID: L2-VAL-028
Level: L2
Type: Functional
Statement: The validator shall report a warning for a contactor joining two AC nodes or two DC nodes
  of different nominal voltage.
Rationale: DD-017 says "same kind", meaning AC or DC, not the schema key `kind`. TRU nodes have no
  voltage and are excluded.
Parent(s): L1-ELA-009
Source: DD-017
Allocated to: C-VALID
Verification: Test; success criteria: a tie between a 115 V AC bus and a 200 V AC bus gives one such
  warning and no error.
Status: Draft
```

### L2-VAL-029

```req
ID: L2-VAL-029
Level: L2
Type: Functional
Statement: The validator shall report a warning for a source with no contactor.
Rationale: Such a source can feed nothing, which is suspicious but legal.
Parent(s): L1-ELA-009
Source: DD-017
Allocated to: C-VALID
Verification: Test; success criteria: a source that no contactor references gives one such warning
  at that source's path and no error.
Status: Draft
```

### L2-VAL-030

```req
ID: L2-VAL-030
Level: L2
Type: Functional
Statement: The validator shall report a warning for a bus with no possible feed, meaning no path
  from any source even with all contactors closed and all sources and TRUs live.
Rationale: This is suspicious but legal.
Parent(s): L1-ELA-009
Source: DD-017
Allocated to: C-VALID
Verification: Test; success criteria: a bus with no contactor gives one such warning and no error,
  and a bus reachable only through an open contactor gives none.
Status: Draft
```

### L2-VAL-032

```req
ID: L2-VAL-032
Level: L2
Type: Functional
Statement: The validator shall report a warning at path `$.loads` when a definition marks no load as
  essential.
Rationale: With no essential loads, total power loss still reports PASS under DD-001. The warning
  keeps that visible with no change to the pass rule.
Parent(s): L1-ELA-009
Source: DD-025
Allocated to: C-VALID
Verification: Test; success criteria: a definition with no essential load gives this warning, no
  error and a usable definition, and a definition with one essential load gives no such warning.
Status: Draft
```

<!-- END SECTION VAL-WARNINGS -->

## C-ENGINE: analysis engine

<!-- BEGIN SECTION ENG-ENERGISATION -->

### L2-ENG-001

```req
ID: L2-ENG-001
Level: L2
Type: Functional
Statement: The engine shall take each component's state from the supplied state map when the map
  lists it, and from its `default_state` otherwise.
Rationale: A scenario lists only the components that differ from their default.
Parent(s): L1-ELA-013
Source: docs/spec.md §5.2
Allocated to: C-ENGINE
Verification: Test; success criteria: a state map listing one generator as `failed` gives that
  generator `failed` and every other component its `default_state`.
Status: Draft
```

### L2-ENG-002

```req
ID: L2-ENG-002
Level: L2
Type: Functional
Statement: The engine shall treat each crew switch as `on` unless the supplied state map sets it
  `off`.
Rationale: The switch is on at the start of every simulation.
Parent(s): L1-ELA-017
Source: docs/spec.md §4.9
Allocated to: C-ENGINE
Verification: Test; success criteria: an empty state map gives `on`, and a state map with the bus id
  set to `off` gives `off`.
Status: Draft
```

### L2-ENG-003

```req
ID: L2-ENG-003
Level: L2
Type: Functional
Statement: The engine shall report a source energised if and only if it is live, meaning its state
  is `operative` or, for an emergency generator, `available`.
Rationale: A failed source supplies nothing, and a stowed RAT supplies nothing.
Parent(s): L1-ELA-013
Source: docs/spec.md §3.3; docs/spec.md §4.3
Allocated to: C-ENGINE
Verification: Test; success criteria: a generator as `failed` and an emergency generator as
  `unavailable` each report de-energised and leave their otherwise unfed bus de-energised.
Status: Draft
```

### L2-ENG-004

```req
ID: L2-ENG-004
Level: L2
Type: Functional
Statement: The engine shall report a bus energised if and only if a path connects it to a live
  source through closed contactors and energised TRUs.
Rationale: This is the energisation definition applied to buses.
Parent(s): L1-ELA-013
Source: docs/spec.md §3.3
Allocated to: C-ENGINE
Verification: Test; success criteria: on a chain of generator, contactor, bus, tie and second bus,
  both buses are energised with all closed, and only the first with the tie open.
Status: Draft
```

### L2-ENG-005

```req
ID: L2-ENG-005
Level: L2
Type: Functional
Statement: The engine shall treat a closed contactor as a path in both directions regardless of its
  `from` and `to` order, a `tru` contactor being input or output according to which bus it joins.
Rationale: Contactors and bus ties pass power in both directions when closed.
Parent(s): L1-ELA-014
Source: docs/spec.md §3.3
Allocated to: C-ENGINE
Verification: Test; success criteria: swapping `from` and `to` on a closed bus tie gives identical
  energisation in both directions, and swapping them on a TRU input contactor leaves it the TRU's
  input.
Status: Draft
```

### L2-ENG-006

```req
ID: L2-ENG-006
Level: L2
Type: Functional
Statement: The engine shall treat an open contactor as no path in either direction.
Rationale: An open contactor passes nothing.
Parent(s): L1-ELA-014
Source: docs/spec.md §3.3
Allocated to: C-ENGINE
Verification: Test; success criteria: an open tie between a live bus and a bus with no other feed
  leaves the second bus de-energised, from either end.
Status: Draft
```

### L2-ENG-007

```req
ID: L2-ENG-007
Level: L2
Type: Functional
Statement: The engine shall report a TRU energised if and only if its state is `operative`, its
  input AC bus is energised and its input contactor is closed.
Rationale: The specification's rule omits `operative`, but a failed TRU is not a path under DD-012
  and §6.2 draws it as failed.
Parent(s): L1-ELA-013
Source: docs/spec.md §3.3; docs/spec.md §4.7; DD-012
Allocated to: C-ENGINE
Verification: Test; success criteria: of the four cases, only the operative TRU with live input bus
  and closed input contactor is energised, and it stays energised with its output contactor open.
Status: Draft
```

### L2-ENG-008

```req
ID: L2-ENG-008
Level: L2
Type: Functional
Statement: The engine shall pass energisation through a TRU only from its input side to its output
  side.
Rationale: TRUs pass power only from AC to DC.
Parent(s): L1-ELA-015
Source: docs/spec.md §3.3; docs/spec.md §4.7
Allocated to: C-ENGINE
Verification: Test; success criteria: a battery-fed DC bus with closed TRU output and input
  contactors leaves the TRU and its input AC bus de-energised.
Status: Draft
```

### L2-ENG-009

```req
ID: L2-ENG-009
Level: L2
Type: Functional
Statement: The engine shall treat a source with several contactors as connecting those buses only
  while it is live.
Rationale: A failed source supplies nothing and bridges nothing.
Parent(s): L1-ELA-013
Source: docs/spec.md §3.3; DD-012
Allocated to: C-ENGINE
Verification: Test; success criteria: two buses joined only through one source's two closed
  contactors, with a second live source on one bus, leave the other bus de-energised when the first
  source is failed.
Status: Draft
```

### L2-ENG-010

```req
ID: L2-ENG-010
Level: L2
Type: Functional
Statement: The engine shall report a contactor energised if and only if it is closed and at least
  one end is energised.
Rationale: Needed to colour contactors on the schematic.
Parent(s): L1-ELA-043
Source: DD-013
Allocated to: C-ENGINE
Verification: Test; success criteria: a closed contactor with one live end is energised, an open
  contactor with two live ends is not, and a closed contactor with two dead ends is not.
Status: Draft
```

<!-- END SECTION ENG-ENERGISATION -->

<!-- BEGIN SECTION ENG-DEMAND -->

### L2-ENG-011

```req
ID: L2-ENG-011
Level: L2
Type: Functional
Statement: The engine shall compute a bus's own-load power in each band as the sum of that band's
  `power` for all loads on the bus.
Rationale: This is step 1 of the method in docs/spec.md §3.4, now one term of bus demand under
  DD-002.
Parent(s): L1-ELA-016
Source: docs/spec.md §3.4; DD-002
Allocated to: C-ENGINE
Verification: Test; success criteria: loads of 100 W and 250 W in `continuous` on an energised bus
  give own-load power of 350 W in that band.
Status: Draft
```

### L2-ENG-012

```req
ID: L2-ENG-012
Level: L2
Type: Functional
Statement: The engine shall count zero own-load power on a de-energised bus, own-load power always
  being a number.
Rationale: If a bus is lost, every load on it is lost.
Parent(s): L1-ELA-016
Source: docs/spec.md §3.2; docs/spec.md §3.4
Allocated to: C-ENGINE
Verification: Test; success criteria: opening the only contactor feeding a bus with 500 W of loads
  gives own-load power 0 W in all three bands, with demand null.
Status: Draft
```

### L2-ENG-013

```req
ID: L2-ENG-013
Level: L2
Type: Functional
Statement: The engine shall count zero own-load power on a crew-switched bus whose switch is `off`,
  leaving the bus's energised state unchanged.
Rationale: The bus itself may still be energised.
Parent(s): L1-ELA-016
Source: docs/spec.md §3.4; docs/spec.md §4.9
Allocated to: C-ENGINE
Verification: Test; success criteria: a live crew-switched bus with its switch `off` reports
  energised with own-load power 0 W, and with its switch `on` it reports its load sum.
Status: Draft
```

### L2-ENG-014

```req
ID: L2-ENG-014
Level: L2
Type: Functional
Statement: The engine shall compute a bus's own-load power from unchanged load `power` values in
  every configuration in which the bus is energised and no crew switch on it is off.
Rationale: Loads are always on, with no flight-phase variation.
Parent(s): L1-ELA-035
Source: docs/spec.md §2; docs/spec.md §3.2
Allocated to: C-ENGINE
Verification: Test; success criteria: a bus's own-load power is identical across all sample
  scenarios meeting that condition.
Status: Draft
```

### L2-ENG-015

```req
ID: L2-ENG-015
Level: L2
Type: Functional
Statement: The engine shall add no loss between a load and its bus.
Rationale: Circuit breakers are lossless.
Parent(s): L1-ELA-016
Source: docs/spec.md §3.2; docs/spec.md §4.10
Allocated to: C-ENGINE
Verification: Test; success criteria: a single 1000 W load gives own-load power of exactly 1000 W.
Status: Draft
```

### L2-ENG-016

```req
ID: L2-ENG-016
Level: L2
Type: Functional
Statement: The engine shall compute TRU input power in each band as output power divided by
  `efficiency`.
Rationale: The AC side always supplies more than the DC side consumes.
Parent(s): L1-ELA-019
Source: docs/spec.md §3.4; docs/spec.md §4.7
Allocated to: C-ENGINE
Verification: Test; success criteria: TRU output 850 W at `efficiency` 0.85 gives input 1000 W, and
  at `efficiency` 1.0 gives input 850 W.
Status: Draft
```

### L2-ENG-017

```req
ID: L2-ENG-017
Level: L2
Type: Functional
Statement: The engine shall compute bus demand as throughput, equal to own-load power plus TRU input
  power drawn from the bus plus power leaving the bus through closed bus ties and through source
  contactors to other buses, excluding TRU input contactors.
Rationale: Departs from docs/spec.md §3.4 step 1 by ruling. A busbar's rating applies to what it
  carries. TRU input power is counted once, though a TRU input contactor is also a closed contactor
  leaving the bus.
Parent(s): L1-ELA-018
Source: docs/spec.md §3.4; DD-002
Allocated to: C-ENGINE
Verification: Test; success criteria: a bus with 1000 W own load, a TRU drawing 1000 W input and a
  tie feeding 500 W onward has demand 2500 W.
Status: Draft
```

### L2-ENG-018

```req
ID: L2-ENG-018
Level: L2
Type: Functional
Statement: The engine shall report a bus's own-load power separately from its demand.
Rationale: Both figures are useful, and DD-002 requires both.
Parent(s): L1-ELA-018
Source: DD-002
Allocated to: C-ENGINE
Verification: Test; success criteria: the bus in a throughput test reports demand 2500 W and
  own-load power 1000 W.
Status: Draft
```

### L2-ENG-019

```req
ID: L2-ENG-019
Level: L2
Type: Functional
Statement: The engine shall compute source demand as the total demand flowing back to that source.
Rationale: This is step 4 of the method in docs/spec.md §3.4.
Parent(s): L1-ELA-019
Source: docs/spec.md §3.4
Allocated to: C-ENGINE
Verification: Test; success criteria: a generator feeding 2000 W of AC loads and a TRU of input 1000
  W has demand 3000 W.
Status: Draft
```

<!-- END SECTION ENG-DEMAND -->

<!-- BEGIN SECTION ENG-FLOW -->

### L2-ENG-020

```req
ID: L2-ENG-020
Level: L2
Type: Functional
Statement: The engine shall group buses and live sources into islands joined by closed contactors,
  with TRUs forming the boundary between islands and each group of de-energised buses forming an
  island with no root.
Rationale: Feeding rules, sharing and flow are all defined per island.
Parent(s): L1-ELA-019
Source: docs/spec.md §3.5; DD-012
Allocated to: C-ENGINE
Verification: Test; success criteria: a system with two generators on untied AC buses and one TRU
  gives 3 islands, with the TRU's output bus in a different island from its input bus, and a dead
  bus group gives an island with no source.
Status: Draft
```

### L2-ENG-021

```req
ID: L2-ENG-021
Level: L2
Type: Functional
Statement: The engine shall find the power crossing each closed contactor by node balance on a
  spanning tree of its island rooted at the source with the lowest id, as the net of demand minus
  source injection on the side away from that root.
Rationale: Flow follows from node balance when no loop is present. DD-004 roots the tree at the
  source with the lowest id, which defines the far side of a tie with sources on both sides.
Parent(s): L1-ELA-019
Source: docs/spec.md §3.4; DD-004
Allocated to: C-ENGINE
Verification: Test; success criteria: a single-source chain of three buses with own loads of 100 W,
  200 W and 300 W gives 500 W on the first tie and 300 W on the second.
Status: Draft
```

### L2-ENG-022

```req
ID: L2-ENG-022
Level: L2
Type: Functional
Statement: The engine shall report contactor flow as a non-negative magnitude.
Rationale: A multi-source DC island can carry flow toward the tree root.
Parent(s): L1-ELA-019
Source: DD-004
Allocated to: C-ENGINE
Verification: Test; success criteria: a tie between two buses fed by equal-capacity TRUs, with own
  loads of 300 W and 100 W, carries 100 W whichever bus is the tree root.
Status: Draft
```

### L2-ENG-023

```req
ID: L2-ENG-023
Level: L2
Type: Functional
Statement: The engine shall build the spanning tree of a looped island breadth-first from the
  island's source with the lowest id, visiting neighbours by node id then contactor id, compared by
  Unicode code point.
Rationale: The split round a loop is indeterminate without impedances, so a fixed rule keeps results
  repeatable.
Parent(s): L1-ELA-023
Source: DD-004
Allocated to: C-ENGINE
Verification: Test; success criteria: a ring of three closed ties gives the same tree on every run
  and after reordering the JSON arrays, with the tree edges predicted by the rule, and of two
  parallel ties between the same buses the lower contactor id is kept.
Status: Draft
```

### L2-ENG-024

```req
ID: L2-ENG-024
Level: L2
Type: Functional
Statement: The engine shall assign zero flow to each contactor left out of the spanning tree.
Rationale: This is the stated assumption for looped islands.
Parent(s): L1-ELA-023
Source: DD-004
Allocated to: C-ENGINE
Verification: Test; success criteria: the contactor left out of a three-tie ring reports demand 0 W
  in all three bands.
Status: Draft
```

### L2-ENG-025

```req
ID: L2-ENG-025
Level: L2
Type: Functional
Statement: The engine shall issue a `meshed_island` warning naming each contactor left out of a
  spanning tree, on energised, non-paralleled islands only.
Rationale: The warning keeps the assumption visible.
Parent(s): L1-ELA-023
Source: DD-004
Allocated to: C-ENGINE
Verification: Test; success criteria: a three-tie ring gives one `meshed_island` warning naming the
  omitted contactor, an unlooped island, a de-energised ring and a paralleled ring give no such
  warning, and the verdict is unaffected by the warning.
Status: Draft
```

### L2-ENG-026

```req
ID: L2-ENG-026
Level: L2
Type: Functional
Statement: The engine shall set a contactor's demand to the power crossing it found by node balance,
  which is the source output for a source's only contactor, TRU input power for a TRU input, TRU
  output power for a TRU output, and cut-set flow for a tie.
Rationale: Needed to check rated contactors. A source with several contactors splits its output
  across them. DD-005 takes precedence on a paralleled island, where no demand is attributed to
  contactors.
Parent(s): L1-ELA-019
Source: DD-013
Allocated to: C-ENGINE
Verification: Test; success criteria: on a generator feeding a bus with a TRU of output 850 W and
  efficiency 0.85, the TRU output contactor carries 850 W, the TRU input contactor 1000 W and the
  generator contactor 1000 W.
Status: Draft
```

### L2-ENG-027

```req
ID: L2-ENG-027
Level: L2
Type: Functional
Statement: The engine shall treat a TRU that is energised with an open output contactor as feeding
  nothing, with zero demand.
Rationale: TRU energisation is defined by the input side alone.
Parent(s): L1-ELA-019
Source: docs/spec.md §3.3; DD-014
Allocated to: C-ENGINE
Verification: Test; success criteria: such a TRU reports energised with output and input power 0 W,
  and its output bus gets no feed from it.
Status: Draft
```

<!-- END SECTION ENG-FLOW -->

<!-- BEGIN SECTION ENG-PARALLEL -->

### L2-ENG-028

```req
ID: L2-ENG-028
Level: L2
Type: Functional
Statement: The engine shall record a configuration error containing the text "AC sources paralleled"
  and the source ids concerned for each AC island with more than one live source.
Rationale: Unsynchronised AC generators are not paralleled, and the scenario fails explicitly.
Parent(s): L1-ELA-022
Source: docs/spec.md §3.5; DD-005
Allocated to: C-ENGINE
Verification: Test; success criteria: two live generators joined by a closed tie give one such error
  naming both, and an available AC RAT output closed onto a live bus gives one such error.
Status: Draft
```

### L2-ENG-029

```req
ID: L2-ENG-029
Level: L2
Type: Functional
Statement: The engine shall keep the buses of a paralleled AC island energised with their loads
  counted.
Rationale: The failure message is required, and the buses are still physically fed.
Parent(s): L1-ELA-022
Source: DD-005
Allocated to: C-ENGINE
Verification: Test; success criteria: on a paralleled island, every bus reports energised and
  own-load power equal to its load sum.
Status: Draft
```

### L2-ENG-030

```req
ID: L2-ENG-030
Level: L2
Type: Functional
Statement: The engine shall compute bus demand on a paralleled AC island as own-load power plus TRU
  input power only.
Rationale: Splitting power between unsynchronised sources would be invented data.
Parent(s): L1-ELA-018
Source: DD-002; DD-005
Allocated to: C-ENGINE
Verification: Test; success criteria: a paralleled bus with 1000 W own load and a TRU of input 500 W
  reports demand 1500 W regardless of ties to other buses on the island.
Status: Draft
```

### L2-ENG-031

```req
ID: L2-ENG-031
Level: L2
Type: Functional
Statement: The engine shall attribute no demand to the sources and contactors of a paralleled AC
  island, reporting their demand as null.
Rationale: These elements are not capacity-checked. This includes TRU input contactors on that
  island, as DD-013 gives DD-005 precedence.
Parent(s): L1-ELA-022
Source: DD-005
Allocated to: C-ENGINE
Verification: Test; success criteria: the two sources, their contactors and the TRU input contactor
  on a paralleled island report null demand, and none appears among checked elements, even when
  loads exceed source capacity.
Status: Draft
```

### L2-ENG-032

```req
ID: L2-ENG-032
Level: L2
Type: Functional
Statement: The engine shall analyse DC islands downstream of a paralleled AC island as normal.
Rationale: TRU output and DC demand do not depend on the split between AC sources.
Parent(s): L1-ELA-019
Source: DD-005
Allocated to: C-ENGINE
Verification: Test; success criteria: a DC bus fed by a TRU from a paralleled island reports the
  same demand, and the TRU the same output demand, as with the AC island not paralleled.
Status: Draft
```

<!-- END SECTION ENG-PARALLEL -->

<!-- BEGIN SECTION ENG-DC-SOURCES -->

### L2-ENG-033

```req
ID: L2-ENG-033
Level: L2
Type: Functional
Statement: The engine shall share a DC island's demand among all non-battery DC sources feeding it,
  TRUs and DC emergency generator outputs alike, in proportion to their continuous capacities, for
  all three bands.
Rationale: This generalises the rule in docs/spec.md §3.5 to DC RAT outputs. A DC output feeds a DC
  bus directly.
Parent(s): L1-ELA-020
Source: docs/spec.md §3.5; DD-006
Allocated to: C-ENGINE
Verification: Test; success criteria: a TRU of 6000 W and a DC RAT output of 3000 W continuous
  capacity with 900 W demand in each band carry 600 W and 300 W, and the same 2:1 split holds in
  `transient` even when their `transient` capacities have another ratio.
Status: Draft
```

### L2-ENG-034

```req
ID: L2-ENG-034
Level: L2
Type: Functional
Statement: The engine shall split a DC island's demand equally among its sources when their total
  continuous capacity is zero.
Rationale: Proportional sharing is undefined in that case.
Parent(s): L1-ELA-020
Source: DD-006
Allocated to: C-ENGINE
Verification: Test; success criteria: two TRUs of zero continuous capacity with 900 W demand carry
  450 W each.
Status: Draft
```

### L2-ENG-035

```req
ID: L2-ENG-035
Level: L2
Type: Functional
Statement: The engine shall assign zero demand, in all three bands, to a battery on a DC island with
  another DC source feeding that island.
Rationale: The battery is treated as not discharging.
Parent(s): L1-ELA-021
Source: docs/spec.md §3.5; DD-015
Allocated to: C-ENGINE
Verification: Test; success criteria: a battery tied to a bus fed by an energised TRU reports demand
  0 W, and the TRU carries all the island demand.
Status: Draft
```

### L2-ENG-036

```req
ID: L2-ENG-036
Level: L2
Type: Functional
Statement: The engine shall count a TRU or DC emergency generator output as feeding an island only
  while it is live, energised and connected to the island by a closed contactor.
Rationale: A failed TRU, or one with an open output contactor, must not silence the battery.
Parent(s): L1-ELA-021
Source: docs/spec.md §3.5; DD-015
Allocated to: C-ENGINE
Verification: Test; success criteria: the battery carries the island demand with the TRU failed,
  with the TRU's input bus dead, and with the TRU's output contactor open.
Status: Draft
```

### L2-ENG-037

```req
ID: L2-ENG-037
Level: L2
Type: Functional
Statement: The engine shall assign the whole demand of a DC island to its battery when that battery
  is the island's sole source.
Rationale: The battery supplies when it is the sole source.
Parent(s): L1-ELA-021
Source: docs/spec.md §3.5
Allocated to: C-ENGINE
Verification: Test; success criteria: a battery alone on a bus with 500 W of loads has demand 500 W.
Status: Draft
```

### L2-ENG-038

```req
ID: L2-ENG-038
Level: L2
Type: Functional
Statement: The engine shall share a DC island's demand among two or more batteries that are its sole
  sources in proportion to their continuous capacities.
Rationale: The same sharing rule applies to batteries, with no new concept.
Parent(s): L1-ELA-020
Source: DD-006
Allocated to: C-ENGINE
Verification: Test; success criteria: batteries of 3000 W and 1000 W continuous capacity with 800 W
  demand carry 600 W and 200 W.
Status: Draft
```

### L2-ENG-039

```req
ID: L2-ENG-039
Level: L2
Type: Constraint
Statement: The engine shall assign no negative demand to any battery.
Rationale: Battery charging is not modelled.
Parent(s): L1-ELA-021
Source: DD-015
Allocated to: C-ENGINE
Verification: Test; success criteria: in every sample scenario every battery's demand is at least 0
  W in all three bands.
Status: Draft
```

### L2-ENG-040

```req
ID: L2-ENG-040
Level: L2
Type: Functional
Statement: The engine shall check each emergency generator output against its own capacity alone,
  with no combined limit across outputs.
Rationale: Each RAT output is its own source.
Parent(s): L1-ELA-024
Source: docs/spec.md §4.3; DD-008
Allocated to: C-ENGINE
Verification: Test; success criteria: with `safety_margin` 0.10, AC and DC outputs each at 90 % of
  their own capacity report no overload, even when their sum exceeds either capacity.
Status: Draft
```

<!-- END SECTION ENG-DC-SOURCES -->

<!-- BEGIN SECTION ENG-CHECK -->

### L2-ENG-041

```req
ID: L2-ENG-041
Level: L2
Type: Functional
Statement: The engine shall evaluate `demand × (1 + safety_margin) ≤ capacity` for each checked
  element in each of the three bands, treating an excess within 1e-6 W as satisfying it.
Rationale: This is the criterion, inclusive at equality. DD-023 sets the tolerance, because IEEE
  arithmetic makes 3000 × 1.1 exceed 3300.
Parent(s): L1-ELA-024
Source: docs/spec.md §3.6; DD-023
Allocated to: C-ENGINE
Verification: Test; success criteria: with demand 1000 W and margin 0.10, the check holds at
  capacity 1100 W and fails at capacity 1099 W, in each band separately, and with demand 3000 W it
  holds at capacity 3300 W.
Status: Draft
```

### L2-ENG-042

```req
ID: L2-ENG-042
Level: L2
Type: Functional
Statement: The engine shall treat as checked every energised source, TRU, bus and contactor that has
  a capacity, unless DD-005 removes its demand, counting zero demand as checked.
Rationale: DD-011 states that de-energised elements are not checked, and DD-005 removes demand from
  paralleled sources and contactors.
Parent(s): L1-ELA-024
Source: docs/spec.md §3.6; DD-005; DD-011
Allocated to: C-ENGINE
Verification: Test; success criteria: in a configuration with one generator failed, the failed
  generator is absent from checked elements and the operative generator is present, and an energised
  battery at zero demand is present with remaining margin 100 %.
Status: Draft
```

### L2-ENG-043

```req
ID: L2-ENG-043
Level: L2
Type: Functional
Statement: The engine shall use an element's own `safety_margin` when defined and
  `settings.safety_margin` otherwise.
Rationale: A per-element value overrides the global value.
Parent(s): L1-ELA-025
Source: docs/spec.md §3.6; docs/spec.md §5.2
Allocated to: C-ENGINE
Verification: Test; success criteria: with global 0.10 and element 0.25 at demand 1000 W, the
  element's demand with margin is 1250 W, and a sibling's is 1100 W.
Status: Draft
```

### L2-ENG-044

```req
ID: L2-ENG-044
Level: L2
Type: Functional
Statement: The engine shall exclude an element with no capacity defined from the capacity check.
Rationale: Such elements are unconstrained.
Parent(s): L1-ELA-026
Source: docs/spec.md §3.6
Allocated to: C-ENGINE
Verification: Test; success criteria: an unrated bus carrying 1 MW is absent from checked elements
  and reports no overload.
Status: Draft
```

### L2-ENG-045

```req
ID: L2-ENG-045
Level: L2
Type: Functional
Statement: The engine shall report an element as overloaded when it fails the check in any band.
Rationale: An element failing any band is overloaded.
Parent(s): L1-ELA-024
Source: docs/spec.md §3.6
Allocated to: C-ENGINE
Verification: Test; success criteria: an element failing only `short_term` is overloaded and the
  overload lists `short_term` alone.
Status: Draft
```

### L2-ENG-046

```req
ID: L2-ENG-046
Level: L2
Type: Functional
Statement: The engine shall use as demand in a capacity check the source demand for a source, the
  output power for a TRU, the throughput for a bus and the power crossing it for a contactor.
Rationale: TRU capacity is an output capacity under docs/spec.md §4.7, so input power is not
  compared with it.
Parent(s): L1-ELA-024
Source: docs/spec.md §3.6; docs/spec.md §4.7; DD-002; DD-013
Allocated to: C-ENGINE
Verification: Test; success criteria: a TRU of output 850 W, efficiency 0.85 and capacity 900 W with
  margin 0 is not overloaded, even though its input is 1000 W.
Status: Draft
```

### L2-ENG-047

```req
ID: L2-ENG-047
Level: L2
Type: Functional
Statement: The engine shall compute remaining margin in watts as `capacity − demand × (1 + margin)`
  and in percent as that value ÷ `capacity` × 100, negative when overloaded.
Rationale: The specification uses the term without defining it.
Parent(s): L1-ELA-029
Source: DD-011
Allocated to: C-ENGINE
Verification: Test; success criteria: capacity 2000 W, demand 1000 W and margin 0.10 give 900 W and
  45 %, and demand 2000 W gives −200 W and −10 %.
Status: Draft
```

### L2-ENG-048

```req
ID: L2-ENG-048
Level: L2
Type: Functional
Statement: The engine shall give a zero-capacity element a remaining margin of −100 % with non-zero
  demand and 0 % with zero demand.
Rationale: Both cases come from DD-011.
Parent(s): L1-ELA-029
Source: DD-011
Allocated to: C-ENGINE
Verification: Test; success criteria: capacity 0 W gives −100 % at demand 1 W and 0 % at demand 0 W,
  with no division error.
Status: Draft
```

### L2-ENG-049

```req
ID: L2-ENG-049
Level: L2
Type: Functional
Statement: The engine shall report as the worst element the checked element and band with the
  smallest remaining margin percentage, treating margins within 1e-6 % as equal and resolving ties
  to the lowest element id and then to the order `transient`, `short_term`, `continuous`.
Rationale: A percentage compares elements of different sizes fairly. DD-023 sets the tolerance, and
  the tie rule keeps results repeatable.
Parent(s): L1-ELA-030
Source: DD-011; DD-023
Allocated to: C-ENGINE
Verification: Test; success criteria: three elements at 40 %, 12 % and 25 % give the 12 % element,
  two elements tied at 10 % give the lower id, and two elements differing by less than 1e-6 % count
  as tied.
Status: Draft
```

### L2-ENG-050

```req
ID: L2-ENG-050
Level: L2
Type: Functional
Statement: The engine shall report the worst element and smallest margin as null when no element is
  checked.
Rationale: With nothing checked there is no worst element.
Parent(s): L1-ELA-030
Source: DD-011
Allocated to: C-ENGINE
Verification: Test; success criteria: a configuration with all sources failed gives null for both
  values.
Status: Draft
```

<!-- END SECTION ENG-CHECK -->

<!-- BEGIN SECTION ENG-RESULTS -->

### L2-ENG-051

```req
ID: L2-ENG-051
Level: L2
Type: Functional
Statement: The engine shall give a verdict of PASS if and only if no element is overloaded, there is
  no configuration error and no essential load is unpowered.
Rationale: DD-001 extends docs/spec.md §3.6.
Parent(s): L1-ELA-027
Source: docs/spec.md §3.6; DD-001
Allocated to: C-ENGINE
Verification: Test; success criteria: four configurations, clean, overloaded, paralleled and with an
  unpowered essential load, give PASS, FAIL, FAIL and FAIL.
Status: Draft
```

### L2-ENG-052

```req
ID: L2-ENG-052
Level: L2
Type: Functional
Statement: The engine shall report each essential load as unpowered when its bus is de-energised or
  its bus's crew switch is `off`.
Rationale: Capacity checks alone report PASS when every source has failed.
Parent(s): L1-ELA-028
Source: DD-001
Allocated to: C-ENGINE
Verification: Test; success criteria: essential loads on a dead bus and on a live bus with its crew
  switch `off` are each listed with load id, name and bus, and an essential load on a live bus is
  not listed.
Status: Draft
```

### L2-ENG-053

```req
ID: L2-ENG-053
Level: L2
Type: Functional
Statement: The engine shall report each overload with element, band, demand with margin and
  capacity.
Rationale: These are the fields shown in the status panel.
Parent(s): L1-ELA-052
Source: docs/spec.md §6.2
Allocated to: C-ENGINE
Verification: Test; success criteria: an element failing two bands gives two overload entries, each
  holding the four fields with the expected values.
Status: Draft
```

### L2-ENG-054

```req
ID: L2-ENG-054
Level: L2
Type: Interface
Statement: The engine shall return for every source, bus, TRU and contactor, per band, its energised
  state, demand, demand with margin, capacity and remaining margin in W and %. Demand is null on a
  de-energised element and on an element with no attributed demand. Own-load power is always a
  number.
Rationale: Tooltips, labels and the analyse response are built from this.
Parent(s): L1-ELA-046
Source: docs/spec.md §6.2; docs/spec.md §7.2
Allocated to: C-ENGINE
Verification: Test; success criteria: the result for the sample default configuration holds all
  these fields for all three bands for every element, with capacity and the remaining-margin fields
  null where no capacity is defined, and demand with margin still a number on an energised element
  with no capacity.
Status: Draft
```

### L2-ENG-055

```req
ID: L2-ENG-055
Level: L2
Type: Functional
Statement: The engine shall report the load of each source and TRU per band as a percentage equal to
  demand ÷ capacity × 100. It is null when capacity is 0 or demand is null.
Rationale: Sources and TRUs show their load and percentage of capacity.
Parent(s): L1-ELA-047
Source: docs/spec.md §6.2
Allocated to: C-ENGINE
Verification: Test; success criteria: demand 45000 W on capacity 90000 W reports 50 %, and capacity
  0 W reports null with no division error.
Status: Draft
```

### L2-ENG-056

```req
ID: L2-ENG-056
Level: L2
Type: Functional
Statement: The engine shall report each energised bus's voltage as its nominal `voltage`,
  independent of demand.
Rationale: Voltage is treated as constant.
Parent(s): L1-ELA-031
Source: docs/spec.md §3.2; docs/spec.md §3.7
Allocated to: C-ENGINE
Verification: Test; success criteria: a 28 V bus reports 28 V at demand 0 W and at demand 5000 W.
Status: Draft
```

### L2-ENG-057

```req
ID: L2-ENG-057
Level: L2
Type: Functional
Statement: The engine shall compute DC bus current as `I = P / V`, where `P` is bus demand.
Rationale: DD-002 makes the label values throughput, so current uses throughput.
Parent(s): L1-ELA-031
Source: docs/spec.md §3.7; DD-002
Allocated to: C-ENGINE
Verification: Test; success criteria: 2800 W on a 28 V DC bus gives 100 A.
Status: Draft
```

### L2-ENG-058

```req
ID: L2-ENG-058
Level: L2
Type: Functional
Statement: The engine shall compute AC bus current per phase as `I = P / (phases × V_phase)` with
  power factor 1.0, where `P` is bus demand and `V_phase` is the bus `voltage`.
Rationale: Loads are given in watts.
Parent(s): L1-ELA-031
Source: docs/spec.md §3.7; DD-002
Allocated to: C-ENGINE
Verification: Test; success criteria: 3450 W on a 115 V 3-phase bus gives 10 A, and 1150 W on a 115
  V 1-phase bus gives 10 A.
Status: Draft
```

### L2-ENG-059

```req
ID: L2-ENG-059
Level: L2
Type: Functional
Statement: The engine shall report no voltage, power or current for a de-energised bus. Demand is
  null on a de-energised element and on an element with no attributed demand. Own-load power is
  always a number.
Rationale: Quantities are reported for energised buses only.
Parent(s): L1-ELA-044
Source: docs/spec.md §3.7; docs/spec.md §6.2
Allocated to: C-ENGINE
Verification: Test; success criteria: a de-energised bus has null voltage, demand and current in all
  three bands, and own-load power 0 W.
Status: Draft
```

### L2-ENG-069

```req
ID: L2-ENG-069
Level: L2
Type: Interface
Statement: The engine shall expose each element record as `el[id]` with `state`, `energised` and,
  per band, `demand`, `with_margin`, `capacity`, `margin_w` and `margin_pct`, a bus adding `own`,
  `voltage` and `current`, a source or TRU adding `load_pct`, and a TRU adding `input` and `output`.
  On a bus with no crew switch, `state` is null.
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-046
Source: DD-024
Allocated to: C-ENGINE
Verification: Test; success criteria: on a definition with one source, bus, TRU and contactor, each
  record holds exactly the named attributes for its kind, and `state` is null on a bus with no crew
  switch.
Status: Draft
```

<!-- END SECTION ENG-RESULTS -->

<!-- BEGIN SECTION ENG-PURITY -->

### L2-ENG-060

```req
ID: L2-ENG-060
Level: L2
Type: Interface
Statement: The engine shall expose one analysis function that takes a validated definition and a
  state map and returns the analysis result.
Rationale: One entry point makes the batch, command-line and interactive results the same.
Parent(s): L1-ELA-032
Source: docs/spec.md §7.1
Allocated to: C-ENGINE
Verification: Test; success criteria: calling the function directly gives results equal to those
  from the batch runner for every sample scenario.
Status: Draft
```

### L2-ENG-068

```req
ID: L2-ENG-068
Level: L2
Type: Interface
Statement: The engine shall expose `analyse(defn, states)` in `ela.engine`, returning a result with
  `verdict`, `overloads` (entries `element`, `band`, `demand_with_margin`, `capacity`),
  `config_errors`, `unpowered` (entries `id`, `name`, `bus`), `warnings` (entries `code`, `element`,
  `message`, with `code` `meshed_island` for that warning), `worst` (`element`, `band`,
  `margin_pct`), `checked` (element ids), `islands` (entries `buses`, `sources`) and `el`.
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-032
Source: DD-024
Allocated to: C-ENGINE
Verification: Test; success criteria: `ela.engine.analyse` on a failing configuration returns a
  result holding each named attribute, with each entry holding its named fields, and on a looped
  island each `warnings` entry has `code` `meshed_island`.
Status: Draft
```

### L2-ENG-061

```req
ID: L2-ENG-061
Level: L2
Type: Constraint
Statement: The engine shall take no time, duration or step input.
Rationale: The analysis is not a time-domain simulation.
Parent(s): L1-ELA-032
Source: docs/spec.md §1; docs/spec.md §2
Allocated to: C-ENGINE
Verification: Test; success criteria: the signature of the analysis function has only the definition
  and state map parameters, and two calls with equal input give equal output.
Status: Draft
```

### L2-ENG-062

```req
ID: L2-ENG-062
Level: L2
Type: Constraint
Statement: The engine shall leave its input definition and state map unmodified.
Rationale: Repeated analysis must not depend on earlier calls.
Parent(s): L1-ELA-032
Source: docs/spec.md §7.1
Allocated to: C-ENGINE
Verification: Test; success criteria: deep copies taken before a call equal the inputs after the
  call.
Status: Draft
```

### L2-ENG-063

```req
ID: L2-ENG-063
Level: L2
Type: Constraint
Statement: The engine shall report every component in exactly the state the state map and defaults
  give it, with no automatic change.
Rationale: Automatic reconfiguration and bus transfer are out of scope.
Parent(s): L1-ELA-033
Source: docs/spec.md §2
Allocated to: C-ENGINE
Verification: Test; success criteria: with a generator failed, the reported state of every contactor
  equals its default, and a de-energised bus with an open tie to a live bus stays de-energised.
Status: Draft
```

### L2-ENG-064

```req
ID: L2-ENG-064
Level: L2
Type: Constraint
Statement: The engine shall remove no load from demand in response to an overload.
Rationale: Load shedding is out of scope.
Parent(s): L1-ELA-033
Source: docs/spec.md §2
Allocated to: C-ENGINE
Verification: Test; success criteria: a configuration that overloads a generator reports own-load
  power equal to the full load sum on every energised bus.
Status: Draft
```

### L2-ENG-065

```req
ID: L2-ENG-065
Level: L2
Type: Constraint
Statement: The engine shall report no battery endurance quantity.
Rationale: Battery capacity is checked as power only.
Parent(s): L1-ELA-034
Source: docs/spec.md §2; docs/spec.md §4.4
Allocated to: C-ENGINE
Verification: Test; success criteria: the serialised analysis result for a battery-only
  configuration holds no key containing `endurance`, `amp_hour` or `depletion`.
Status: Draft
```

### L2-ENG-066

```req
ID: L2-ENG-066
Level: L2
Type: Constraint
Statement: The engine shall be a pure Python package with no web dependency, implemented in
  `ela/engine.py`.
Rationale: It can then be tested and run from the command line independently.
Parent(s): L1-ELA-063
Source: docs/spec.md §7.1
Allocated to: C-ENGINE
Verification: Test; success criteria: in a fresh interpreter, importing `ela.engine` leaves
  `fastapi`, `starlette` and `uvicorn` absent from `sys.modules`.
Status: Draft
```

### L2-ENG-067

```req
ID: L2-ENG-067
Level: L2
Type: Constraint
Statement: The engine test suite shall hold pytest tests under `tests/` for energisation, TRU
  efficiency, bus ties, source failures, AC paralleling detection, DC sharing, battery priority,
  safety margin and crew switch.
Rationale: These are the engine topics named in the specification, and unit tests are a listed
  deliverable.
Parent(s): L1-ELA-065
Source: docs/spec.md §7.1; docs/spec.md §8
Allocated to: C-ENGINE
Verification: Test; success criteria: `pytest tests -m "not meta"`, run in a subprocess, passes, and
  at least one test exists for each of the 9 topics.
Status: Draft
```

<!-- END SECTION ENG-PURITY -->

## C-SAMPLE: sample definition

<!-- BEGIN SECTION SMP-TOPOLOGY -->

### L2-SMP-001

```req
ID: L2-SMP-001
Level: L2
Type: Data
Statement: The sample definition shall be stored at `definitions/generic_twin.json` and pass
  validation with no error.
Rationale: The path is fixed by docs/plan.md, and the sample must always open.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3; docs/spec.md §7.1
Allocated to: C-SAMPLE
Verification: Test; success criteria: validating that file gives an empty error list, and
  `meta.aircraft` contains `twin` in any case.
Status: Draft
```

### L2-SMP-002

```req
ID: L2-SMP-002
Level: L2
Type: Data
Statement: The sample definition shall hold 2 engine generators, 1 APU generator, at least 1
  emergency generator entry with AC output and 1 battery.
Rationale: This is the source set the specification lists.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: counting `sources` by `kind` and `output` gives those numbers.
Status: Draft
```

### L2-SMP-003

```req
ID: L2-SMP-003
Level: L2
Type: Data
Statement: The sample definition shall hold buses named AC BUS 1, AC BUS 2, AC ESS, DC BUS 1, DC BUS
  2, DC ESS and DC BAT.
Rationale: This is the bus set the specification lists. A small dedicated AC bus for the RAT is
  allowed by DD-007.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: each of the 7 names is contained in the `name` of exactly one
  bus, of the expected `type`.
Status: Draft
```

### L2-SMP-004

```req
ID: L2-SMP-004
Level: L2
Type: Data
Statement: The sample definition shall declare the DC BAT bus with `crew_switch: true`.
Rationale: The DC BAT bus is crew-switched.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: that bus has `crew_switch` true.
Status: Draft
```

### L2-SMP-005

```req
ID: L2-SMP-005
Level: L2
Type: Data
Statement: The sample definition shall hold exactly 3 TRUs, exactly one of which has DC ESS as its
  `output_bus`.
Rationale: This is the TRU set the specification lists.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: `trus` has 3 entries and one has the DC ESS bus as
  `output_bus`.
Status: Draft
```

### L2-SMP-006

```req
ID: L2-SMP-006
Level: L2
Type: Data
Statement: The sample definition shall hold a contactor for every source-to-bus connection, a TRU
  input and output contactor for every TRU, a bus tie between AC BUS 1 and AC BUS 2, a bus tie
  between an AC main bus and AC ESS, and at least one bus tie on each of DC ESS and DC BAT.
Rationale: All source and TRU contactors and bus ties are listed in the specification. Tests rely on
  the two AC ties, which show paralleling and a cross-layer tie.
Parent(s): L1-ELA-036
Source: docs/spec.md §4.8; docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: every source has at least one `source` contactor, every TRU
  has one input and one output contactor, a `bus_tie` joins AC BUS 1 and AC BUS 2, a `bus_tie` joins
  an AC main bus and AC ESS, and DC ESS and DC BAT are each an end of a `bus_tie`.
Status: Draft
```

<!-- END SECTION SMP-TOPOLOGY -->

<!-- BEGIN SECTION SMP-LOADS -->

### L2-SMP-007

```req
ID: L2-SMP-007
Level: L2
Type: Data
Statement: The sample definition shall hold between 40 and 60 loads inclusive.
Rationale: The specification asks for about 40 to 60 loads.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: `loads` has at least 40 and at most 60 entries.
Status: Draft
```

### L2-SMP-008

```req
ID: L2-SMP-008
Level: L2
Type: Data
Statement: The sample definition shall give every load band values satisfying `transient ≥
  short_term ≥ continuous > 0`.
Rationale: This is the measurable part of "plausible figures". The tool does not enforce it, but the
  sample follows the typical pattern.
Parent(s): L1-ELA-036
Source: docs/spec.md §3.1; docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: the inequality holds for every load in the file.
Status: Draft
```

### L2-SMP-009

```req
ID: L2-SMP-009
Level: L2
Type: Data
Statement: The sample definition shall connect at least one load to every bus named in the
  specification's sample.
Rationale: A bus with no load demonstrates nothing.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: each of the 7 named buses is the `bus` of at least one load.
Status: Draft
```

### L2-SMP-010

```req
ID: L2-SMP-010
Level: L2
Type: Data
Statement: The sample definition shall mark at least one load on the DC BAT bus `essential: true`.
Rationale: The sample demonstrates the essential load check, including through the crew switch.
Parent(s): L1-ELA-028
Source: docs/spec.md §5.3; DD-001
Allocated to: C-SAMPLE
Verification: Test; success criteria: at least one load on the DC BAT bus has `essential` true.
Status: Draft
```

### L2-SMP-011

```req
ID: L2-SMP-011
Level: L2
Type: Data
Statement: The sample definition shall mark as essential only loads on buses that are energised in
  its battery-only scenario.
Rationale: The component model has no inverter, so every AC bus is dead on battery only.
Parent(s): L1-ELA-028
Source: DD-019
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysing the battery-only scenario leaves the bus of every
  essential load energised, and every AC bus de-energised.
Status: Draft
```

<!-- END SECTION SMP-LOADS -->

<!-- BEGIN SECTION SMP-SCENARIOS -->

### L2-SMP-012

```req
ID: L2-SMP-012
Level: L2
Type: Data
Statement: The sample definition shall hold between 10 and 15 scenarios inclusive.
Rationale: The count is stated in the specification.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: `scenarios` has at least 10 and at most 15 entries.
Status: Draft
```

### L2-SMP-013

```req
ID: L2-SMP-013
Level: L2
Type: Data
Statement: The sample definition shall hold a normal scenario in which both engine generators are
  live and no emergency generator output is live.
Rationale: The normal configuration is the baseline.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysing the scenarios finds at least one meeting that state
  condition with a PASS verdict.
Status: Draft
```

### L2-SMP-014

```req
ID: L2-SMP-014
Level: L2
Type: Data
Statement: The sample definition shall hold, for each engine generator, a scenario in which that
  generator alone of the two has failed.
Rationale: Each single generator loss is listed in the specification.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: using each generator's `engine` number, one scenario exists
  with engine 1 failed and engine 2 live, and another with engine 2 failed and engine 1 live.
Status: Draft
```

### L2-SMP-015

```req
ID: L2-SMP-015
Level: L2
Type: Data
Statement: The sample definition shall hold an APU-only scenario in which both engine generators
  have failed and the APU generator feeds at least one bus.
Rationale: APU-only is listed in the specification.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysing the scenario gives both engine generators failed,
  the APU generator with non-zero demand, and no emergency generator output live.
Status: Draft
```

### L2-SMP-016

```req
ID: L2-SMP-016
Level: L2
Type: Data
Statement: The sample definition shall hold a scenario in which one engine generator and the APU
  generator have both failed.
Rationale: Generator plus APU loss is listed in the specification.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: one scenario sets the APU generator and exactly one engine
  generator to `failed`.
Status: Draft
```

### L2-SMP-017

```req
ID: L2-SMP-017
Level: L2
Type: Data
Statement: The sample definition shall set each of its 3 TRUs to `failed` in at least one scenario.
Rationale: TRU failures are listed in the specification.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: for each TRU, some scenario's `states` gives that TRU the
  value `failed`.
Status: Draft
```

### L2-SMP-018

```req
ID: L2-SMP-018
Level: L2
Type: Data
Statement: The sample definition shall hold a RAT-only emergency scenario in which all engine and
  APU generators have failed and an emergency generator output is available.
Rationale: RAT-only emergency is listed in the specification.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysing that scenario gives non-zero demand on the emergency
  generator output and at least one energised AC bus.
Status: Draft
```

### L2-SMP-019

```req
ID: L2-SMP-019
Level: L2
Type: Data
Statement: The sample definition shall hold a battery-only scenario in which all engine and APU
  generators have failed and no emergency generator output is available.
Rationale: Battery-only is listed in the specification. On battery only, every AC bus is dead.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3; DD-019
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysing that scenario gives non-zero demand on the battery
  and every AC bus de-energised.
Status: Draft
```

<!-- END SECTION SMP-SCENARIOS -->

<!-- BEGIN SECTION SMP-OUTCOMES -->

### L2-SMP-020

```req
ID: L2-SMP-020
Level: L2
Type: Data
Statement: The sample definition shall hold at least one scenario designed to fail by overload, with
  `designed to fail` in its `description`.
Rationale: This demonstrates the report. The marker lets tests identify such scenarios.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: at least one scenario with that marker gives FAIL with at
  least one overload and no configuration error.
Status: Draft
```

### L2-SMP-021

```req
ID: L2-SMP-021
Level: L2
Type: Data
Statement: The sample definition shall hold at least one scenario designed to fail on an unpowered
  essential load, with `designed to fail` in its `description`.
Rationale: This demonstrates the DD-001 check apart from any capacity failure.
Parent(s): L1-ELA-028
Source: docs/spec.md §5.3; DD-001
Allocated to: C-SAMPLE
Verification: Test; success criteria: at least one scenario with that marker gives FAIL with at
  least one unpowered essential load, zero overloads and no configuration error.
Status: Draft
```

### L2-SMP-022

```req
ID: L2-SMP-022
Level: L2
Type: Data
Statement: The sample definition shall give a FAIL verdict in every scenario whose `description`
  contains `designed to fail` and a PASS verdict in every other scenario.
Rationale: A failure in the sample is then always deliberate.
Parent(s): L1-ELA-036
Source: docs/spec.md §5.3
Allocated to: C-SAMPLE
Verification: Test; success criteria: batch analysis gives PASS for every scenario lacking the
  marker and FAIL for every scenario holding it.
Status: Draft
```

### L2-SMP-023

```req
ID: L2-SMP-023
Level: L2
Type: Data
Statement: The sample definition shall give a PASS verdict in its default configuration.
Rationale: The schematic opens in this configuration. The emergency generator output defaults to
  `unavailable`.
Parent(s): L1-ELA-036
Source: docs/spec.md §4.3; DD-020
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysis with an empty state map gives PASS with no
  configuration error, and every emergency generator output is `unavailable`.
Status: Draft
```

### L2-SMP-024

```req
ID: L2-SMP-024
Level: L2
Type: Data
Statement: The sample definition shall set the default states of its APU line contactor and
  emergency generator contactors so that defaults cause no AC paralleling.
Rationale: Bus transfers are not automatic, so the defaults have to isolate the sources.
Parent(s): L1-ELA-022
Source: DD-020
Allocated to: C-SAMPLE
Verification: Test; success criteria: analysis with an empty state map reports no "AC sources
  paralleled" error with all sources at their defaults.
Status: Draft
```

### L2-SMP-025

```req
ID: L2-SMP-025
Level: L2
Type: Data
Statement: The sample definition shall list in each scenario's `states` every contactor change that
  configuration needs.
Rationale: There is no automatic transfer, so S03 in docs/spec.md §5.1 is not enough on its own.
Parent(s): L1-ELA-033
Source: docs/spec.md §2; DD-020
Allocated to: C-SAMPLE
Verification: Test; success criteria: the RAT-only scenario's `states` lists at least one contactor,
  and that scenario energises an AC bus.
Status: Draft
```

### L2-SMP-026

```req
ID: L2-SMP-026
Level: L2
Type: Data
Statement: The sample definition shall list in each scenario's `states` only components whose value
  differs from their default.
Rationale: A scenario lists only what differs from `default_state`. The validator does not enforce
  this, but the sample follows it.
Parent(s): L1-ELA-001
Source: docs/spec.md §5.2
Allocated to: C-SAMPLE
Verification: Test; success criteria: no `states` entry in the file equals that component's default
  state.
Status: Draft
```

### L2-SMP-027

```req
ID: L2-SMP-027
Level: L2
Type: Constraint
Statement: The sample test suite shall hold a pytest test for every scenario in the sample
  definition, comparing the result with the hand-calculated values recorded in
  `tests/data/generic_twin_expected.json`.
Rationale: Every sample scenario is named as needing test evidence.
Parent(s): L1-ELA-065
Source: docs/spec.md §7.1
Allocated to: C-SAMPLE
Verification: Test; success criteria: `pytest tests -m "not meta"`, run in a subprocess, passes,
  each scenario id in the file has a test comparing verdict and source demands with
  `tests/data/generic_twin_expected.json`, and that file holds no unknown scenario id.
Status: Draft
```

<!-- END SECTION SMP-OUTCOMES -->

## C-BATCH: batch runner and export

<!-- BEGIN SECTION BAT-RUN -->

### L2-BAT-001

```req
ID: L2-BAT-001
Level: L2
Type: Functional
Statement: The batch runner shall return one result for every scenario in a definition, in file
  order.
Rationale: Batch verification covers every defined scenario.
Parent(s): L1-ELA-054
Source: docs/spec.md §6.3
Allocated to: C-BATCH
Verification: Test; success criteria: a definition with 12 scenarios gives 12 results with ids in
  file order.
Status: Draft
```

### L2-BAT-002

```req
ID: L2-BAT-002
Level: L2
Type: Functional
Statement: The batch runner shall start each scenario from default states with only that scenario's
  `states` applied.
Rationale: Scenarios are independent static configurations.
Parent(s): L1-ELA-017
Source: docs/spec.md §4.9; docs/spec.md §5.2
Allocated to: C-BATCH
Verification: Test; success criteria: reversing the scenario order gives the same result for each
  scenario.
Status: Draft
```

### L2-BAT-003

```req
ID: L2-BAT-003
Level: L2
Type: Data
Statement: The batch runner shall give each result the fields scenario id, name, result, worst
  element, worst band, smallest remaining margin percentage, overload count, configuration error
  count and unpowered essential load count, the overload count being the number of element-band
  entries.
Rationale: These are the columns of §6.3. Unpowered essential load count is added to report DD-001.
Parent(s): L1-ELA-055
Source: docs/spec.md §6.3; DD-001; DD-011
Allocated to: C-BATCH
Verification: Test; success criteria: for a scenario with known outcomes, every one of the 9 fields
  equals the hand-calculated value, and two elements failing 3 bands between them give an overload
  count of 3.
Status: Draft
```

### L2-BAT-004

```req
ID: L2-BAT-004
Level: L2
Type: Data
Statement: The batch runner shall give each result the list of every failing element and band, every
  configuration error message, every unpowered essential load and a `warnings` list.
Rationale: The expanded row and JSON export show this detail. A `meshed_island` warning reaches
  batch output through the `warnings` list.
Parent(s): L1-ELA-056
Source: docs/spec.md §6.3; DD-001
Allocated to: C-BATCH
Verification: Test; success criteria: a scenario with 2 overloaded elements across 3 bands gives 3
  overload entries, a paralleled scenario lists the message containing "AC sources paralleled", and
  a looped scenario lists its `meshed_island` warning.
Status: Draft
```

### L2-BAT-005

```req
ID: L2-BAT-005
Level: L2
Type: Functional
Statement: The batch runner shall obtain each result from the engine's analysis function with no
  analysis logic of its own.
Rationale: Batch and interactive results then cannot differ.
Parent(s): L1-ELA-032
Source: docs/spec.md §7.1
Allocated to: C-BATCH
Verification: Test; success criteria: each batch result equals the direct analysis result for the
  same scenario in verdict, overloads and worst element.
Status: Draft
```

### L2-BAT-006

```req
ID: L2-BAT-006
Level: L2
Type: Constraint
Statement: The batch runner shall be implemented in `ela/batch.py` with no web dependency.
Rationale: The file is fixed by docs/plan.md, and the command line uses it with no server.
Parent(s): L1-ELA-063
Source: docs/spec.md §7.1
Allocated to: C-BATCH
Verification: Test; success criteria: in a fresh interpreter, importing `ela.batch` leaves
  `fastapi`, `starlette` and `uvicorn` absent from `sys.modules`.
Status: Draft
```

### L2-BAT-010

```req
ID: L2-BAT-010
Level: L2
Type: Interface
Statement: The batch runner shall expose `run_batch(defn)` in `ela.batch`, returning one result per
  scenario with `scenario_id`, `name`, `result`, `worst_element`, `worst_band`,
  `smallest_margin_pct`, `overloads`, `configuration_errors`, `unpowered_essential`,
  `overload_details`, `error_messages`, `unpowered_details` and `warnings`.
Rationale: DD-024 makes these names binding so that tests can be written before the code. `warnings`
  is the list that L2-BAT-004 adds.
Parent(s): L1-ELA-055
Source: DD-024
Allocated to: C-BATCH
Verification: Test; success criteria: `ela.batch.run_batch` on a definition with one scenario
  returns one result holding each named field.
Status: Draft
```

<!-- END SECTION BAT-RUN -->

<!-- BEGIN SECTION BAT-EXPORT -->

### L2-BAT-007

```req
ID: L2-BAT-007
Level: L2
Type: Interface
Statement: The batch runner shall serialise results to CSV with one header row and one row per
  scenario.
Rationale: CSV suits spreadsheets and reports.
Parent(s): L1-ELA-058
Source: docs/spec.md §6.3
Allocated to: C-BATCH
Verification: Test; success criteria: a 12-scenario result gives 13 rows parsed by `csv.reader`,
  with columns `scenario_id`, `name`, `result`, `worst_element`, `worst_band`,
  `smallest_margin_pct`, `overloads`, `configuration_errors` and `unpowered_essential`.
Status: Draft
```

### L2-BAT-008

```req
ID: L2-BAT-008
Level: L2
Type: Interface
Statement: The batch runner shall serialise results to JSON holding every result field, every
  failing detail and the `warnings` list.
Rationale: JSON keeps the detail that a CSV row cannot.
Parent(s): L1-ELA-058
Source: docs/spec.md §6.3
Allocated to: C-BATCH
Verification: Test; success criteria: the JSON parses, and for every scenario it holds the 9 summary
  fields, the detail lists and `warnings`.
Status: Draft
```

### L2-BAT-009

```req
ID: L2-BAT-009
Level: L2
Type: Interface
Statement: The batch runner shall write a null worst element or margin as an empty CSV cell and as
  JSON `null`.
Rationale: DD-011 allows these values to be null.
Parent(s): L1-ELA-058
Source: docs/spec.md §6.3; DD-011
Allocated to: C-BATCH
Verification: Test; success criteria: a scenario with nothing checked gives empty CSV cells and JSON
  `null` in the worst element, worst band and margin fields.
Status: Draft
```

<!-- END SECTION BAT-EXPORT -->

## C-CLI: command line

<!-- BEGIN SECTION CLI-BATCH -->

### L2-CLI-001

```req
ID: L2-CLI-001
Level: L2
Type: Interface
Statement: The CLI shall run all scenarios of the definition file given as an argument under both
  `python -m ela batch <path>` and `ela batch <path>`.
Rationale: §6.3 gives the module form and DD-018 names the short form.
Parent(s): L1-ELA-054
Source: docs/spec.md §6.3; DD-018
Allocated to: C-CLI
Verification: Test; success criteria: both commands run on `definitions/generic_twin.json` give
  identical standard output.
Status: Draft
```

### L2-CLI-002

```req
ID: L2-CLI-002
Level: L2
Type: Interface
Statement: The CLI shall print to standard output one tab-separated line per scenario holding the 9
  fields of a batch result in column order, with `—` for a null value and a percentage to at most 2
  decimals, and to standard error one line for each scenario warning.
Rationale: This is the command-line equivalent of the results table. A tab keeps fields apart when a
  scenario name holds commas, and `—` matches the results table. Standard output stays one line per
  scenario.
Parent(s): L1-ELA-055
Source: docs/spec.md §6.3; DD-001
Allocated to: C-CLI
Verification: Test; success criteria: output for a 5-scenario definition is 5 lines of 9
  tab-separated fields whose values match the batch result, a scenario with nothing checked shows
  `—` in its worst element, band and margin fields, and a looped scenario's `meshed_island` warning
  appears on standard error.
Status: Draft
```

### L2-CLI-003

```req
ID: L2-CLI-003
Level: L2
Type: Interface
Statement: The CLI shall write the CSV export to `PATH` when given `--csv PATH`.
Rationale: Usable from automated checks.
Parent(s): L1-ELA-058
Source: DD-018
Allocated to: C-CLI
Verification: Test; success criteria: running with `--csv out.csv` creates a file equal to the batch
  runner's CSV serialisation.
Status: Draft
```

### L2-CLI-004

```req
ID: L2-CLI-004
Level: L2
Type: Interface
Statement: The CLI shall write the JSON export to `PATH` when given `--json PATH`.
Rationale: Usable from automated checks.
Parent(s): L1-ELA-058
Source: DD-018
Allocated to: C-CLI
Verification: Test; success criteria: running with `--json out.json` creates a file equal to the
  batch runner's JSON serialisation.
Status: Draft
```

### L2-CLI-005

```req
ID: L2-CLI-005
Level: L2
Type: Constraint
Statement: The CLI shall be implemented in `ela/cli.py` and `ela/__main__.py`.
Rationale: The files are fixed by docs/plan.md.
Parent(s): L1-ELA-063
Source: docs/spec.md §7.1
Allocated to: C-CLI
Verification: Test; success criteria: both files exist, and `python -m ela` reaches the CLI entry
  point.
Status: Draft
```

### L2-CLI-006

```req
ID: L2-CLI-006
Level: L2
Type: Constraint
Statement: The CLI shall complete a batch run with no server process running.
Rationale: The analysis runs without a web server.
Parent(s): L1-ELA-063
Source: docs/spec.md §7.1
Allocated to: C-CLI
Verification: Test; success criteria: a batch run completes with no server running, and the process
  opens no listening TCP port.
Status: Draft
```

<!-- END SECTION CLI-BATCH -->

<!-- BEGIN SECTION CLI-EXIT -->

### L2-CLI-007

```req
ID: L2-CLI-007
Level: L2
Type: Interface
Statement: The CLI shall exit with code 0 when every scenario passes.
Rationale: Exit code 0 is the success signal in automated checks.
Parent(s): L1-ELA-059
Source: docs/spec.md §6.3; DD-018
Allocated to: C-CLI
Verification: Test; success criteria: a definition with only passing scenarios gives exit code 0.
Status: Draft
```

### L2-CLI-008

```req
ID: L2-CLI-008
Level: L2
Type: Interface
Statement: The CLI shall exit with code 1 when at least one scenario fails.
Rationale: The exit code is non-zero if any scenario fails.
Parent(s): L1-ELA-059
Source: docs/spec.md §6.3; DD-018
Allocated to: C-CLI
Verification: Test; success criteria: `definitions/generic_twin.json`, which holds designed-to-fail
  scenarios, gives exit code 1.
Status: Draft
```

### L2-CLI-009

```req
ID: L2-CLI-009
Level: L2
Type: Interface
Statement: The CLI shall exit with code 2 for an invalid definition, a file that does not parse as
  JSON, or bad usage.
Rationale: This separates invalid input from failed analysis.
Parent(s): L1-ELA-059
Source: DD-018
Allocated to: C-CLI
Verification: Test; success criteria: an invalid definition, a file holding `{not json`, a path that
  does not exist, a missing argument and an unknown option each give exit code 2 with no traceback.
Status: Draft
```

### L2-CLI-010

```req
ID: L2-CLI-010
Level: L2
Type: Functional
Statement: The CLI shall print only the validation errors to standard error, with path and message,
  for an invalid definition.
Rationale: The engineer gets the same errors as in the browser. A rejected definition prints errors
  only, so warnings do not bury them.
Parent(s): L1-ELA-007
Source: docs/spec.md §5.2; DD-018
Allocated to: C-CLI
Verification: Test; success criteria: a definition with 3 errors and an unknown key prints exactly 3
  lines to standard error, each holding a JSON path and message, none of them a warning, and prints
  nothing to standard output.
Status: Draft
```

### L2-CLI-011

```req
ID: L2-CLI-011
Level: L2
Type: Functional
Statement: The CLI shall complete a run after printing definition warnings to standard error.
Rationale: Warnings do not block loading.
Parent(s): L1-ELA-009
Source: DD-017
Allocated to: C-CLI
Verification: Test; success criteria: a definition with one unknown key prints that warning to
  standard error, and the run completes with exit code 0 or 1.
Status: Draft
```

### L2-CLI-012

```req
ID: L2-CLI-012
Level: L2
Type: Constraint
Statement: The CLI package shall declare Python 3.12 or later as its required runtime.
Rationale: The project mandates this version.
Parent(s): L1-ELA-060
Source: docs/spec.md §7.1; DD-018
Allocated to: C-CLI
Verification: Test; success criteria: `pyproject.toml` has `requires-python` set to `>=3.12`.
Status: Draft
```

### L2-CLI-013

```req
ID: L2-CLI-013
Level: L2
Type: Constraint
Statement: The CLI package shall be managed with uv, with its dependencies recorded in
  `pyproject.toml` and `uv.lock`.
Rationale: This rests only on the project ruling.
Parent(s): Derived(DD-018)
Source: DD-018
Allocated to: C-CLI
Verification: Test; success criteria: both files exist, and `uv sync --locked` exits with code 0.
Status: Draft
```

<!-- END SECTION CLI-EXIT -->

## C-LAYOUT: schematic layout

<!-- BEGIN SECTION LAY-LAYERS -->

### L2-LAY-001

```req
ID: L2-LAY-001
Level: L2
Type: Functional
Statement: The layout engine shall compute coordinates from a validated definition alone, with no
  coordinates and no component states as input.
Rationale: Coordinates are computed in the back end. Elements do not move when a state changes.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2; docs/spec.md §7.1
Allocated to: C-LAYOUT
Verification: Test; success criteria: the layout function's parameters are the definition only, and
  a call before and after changing a `default_state` gives identical coordinates.
Status: Draft
```

### L2-LAY-002

```req
ID: L2-LAY-002
Level: L2
Type: Interface
Statement: The layout engine shall return one item for each source, contactor, bus, TRU and crew
  switch, with id, kind, top-left position and size, a crew switch item having id `<bus>_switch` and
  sitting adjacent to its bus bar.
Rationale: These are the displayed items.
Parent(s): L1-ELA-040
Source: docs/spec.md §7.1
Allocated to: C-LAYOUT
Verification: Test; success criteria: for the sample, the item ids are exactly the ids of those
  elements plus `<bus>_switch` for each crew-switched bus, each item has `x`, `y`, `width` and
  `height`, and the switch box touches or lies within 16 px of its bar.
Status: Draft
```

### L2-LAY-003

```req
ID: L2-LAY-003
Level: L2
Type: Functional
Statement: The layout engine shall place items top to bottom in the order sources, source
  contactors, AC main buses, AC essential, emergency and other buses, TRUs, then DC buses.
Rationale: This is the layer order in the specification. The role `other` has no layer there, so its
  position is recorded as an assumption.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: for the sample, the largest `y` of each group is less than the
  smallest `y` of the next group.
Status: Draft
```

### L2-LAY-004

```req
ID: L2-LAY-004
Level: L2
Type: Functional
Statement: The layout engine shall place each TRU's input contactor above that TRU and its output
  contactor below it.
Rationale: TRUs are drawn with their input and output contactors.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: for each sample TRU, input contactor `y` < TRU `y` < output
  contactor `y`.
Status: Draft
```

### L2-LAY-005

```req
ID: L2-LAY-005
Level: L2
Type: Functional
Statement: The layout engine shall place DC buses so that vertical position does not decrease in the
  role order main, essential, then emergency, battery and other.
Rationale: This is the bus order in the fifth layer of the specification.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: for the sample, `y` of DC BUS 1 ≤ `y` of DC ESS ≤ `y` of DC
  BAT.
Status: Draft
```

### L2-LAY-006

```req
ID: L2-LAY-006
Level: L2
Type: Functional
Statement: The layout engine shall place the source layer left to right as engine generators in
  `engine` order, then the APU generator, then emergency generator outputs, then batteries.
Rationale: This order is stated in the specification.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: a definition with sources declared in reverse order gives `x`
  increasing in the stated order.
Status: Draft
```

### L2-LAY-007

```req
ID: L2-LAY-007
Level: L2
Type: Functional
Statement: The layout engine shall produce a layout for a definition with any number of engine
  generators.
Rationale: There is no hard limit on engines.
Parent(s): L1-ELA-003
Source: docs/spec.md §4.1; docs/spec.md §7.1
Allocated to: C-LAYOUT
Verification: Test; success criteria: definitions with 2, 4, 8 and 12 engine generators each give
  one item per generator with no two items overlapping.
Status: Draft
```

### L2-LAY-008

```req
ID: L2-LAY-008
Level: L2
Type: Constraint
Statement: The layout engine shall return no item for a load or circuit breaker.
Rationale: These are not drawn.
Parent(s): L1-ELA-042
Source: docs/spec.md §2; docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: no item id in the sample layout equals a load id, and no item
  has a load or breaker kind.
Status: Draft
```

### L2-LAY-009

```req
ID: L2-LAY-009
Level: L2
Type: Constraint
Statement: The layout engine shall be implemented in `ela/layout.py` with no web dependency.
Rationale: The file is fixed by docs/plan.md.
Parent(s): L1-ELA-040
Source: docs/spec.md §7.1
Allocated to: C-LAYOUT
Verification: Test; success criteria: in a fresh interpreter, importing `ela.layout` leaves
  `fastapi`, `starlette` and `uvicorn` absent from `sys.modules`.
Status: Draft
```

### L2-LAY-019

```req
ID: L2-LAY-019
Level: L2
Type: Interface
Statement: The layout engine shall expose `layout(defn)` in `ela.layout`, returning `items` (`id`,
  `kind`, `x`, `y`, `width`, `height`, with `x` and `y` the top-left corner) and `connectors`
  (`from`, `to`, `points`).
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-040
Source: DD-024
Allocated to: C-LAYOUT
Verification: Test; success criteria: `ela.layout.layout` on a one-generator definition returns
  items and connectors holding each named field.
Status: Draft
```

<!-- END SECTION LAY-LAYERS -->

<!-- BEGIN SECTION LAY-ROUTING -->

### L2-LAY-010

```req
ID: L2-LAY-010
Level: L2
Type: Interface
Statement: The layout engine shall return one connector for each electrical link between items, as a
  polyline of points.
Rationale: Each contactor joins two nodes, so the links are known from the definition.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: for the sample, each contactor has connectors to both its
  `from` and `to` items, and each polyline starts and ends on those items' bounds.
Status: Draft
```

### L2-LAY-011

```req
ID: L2-LAY-011
Level: L2
Type: Functional
Statement: The layout engine shall route every connector orthogonally.
Rationale: Orthogonal connectors reduce clutter.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: every consecutive pair of points on every sample connector
  shares an `x` or a `y` value.
Status: Draft
```

### L2-LAY-012

```req
ID: L2-LAY-012
Level: L2
Type: Functional
Statement: The layout engine shall place a bus tie contactor joining two buses of the same layer
  with its centre `y` equal to those buses' centre `y`, between them in `x`.
Rationale: This is the measurable form of "horizontally where possible".
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: for a tie between two same-layer buses, the contactor's centre
  `y` equals the bus centre `y`, and its `x` lies between the two buses.
Status: Draft
```

### L2-LAY-013

```req
ID: L2-LAY-013
Level: L2
Type: Functional
Statement: The layout engine shall place a bus tie contactor joining two buses of different layers
  vertically between those buses.
Rationale: Bus ties are drawn between the buses they connect.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: for the sample tie between an AC main bus and AC ESS, the
  contactor's `y` lies between the two bus `y` values.
Status: Draft
```

### L2-LAY-014

```req
ID: L2-LAY-014
Level: L2
Type: Functional
Statement: The layout engine shall order items by barycentre within layers other than the source
  layer, so that crossings, counted as straight-line inversions between adjacent layers, do not
  exceed those of the same layers in definition order.
Rationale: This is the measurable form of "minimise line crossings". A Sugiyama-style method is
  named in the specification. The source layer keeps the fixed order of L2-LAY-006.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: on the sample and on 3 further fixture definitions, the
  inversion count is no greater than that of definition order, with the source layer in its fixed
  order in both counts.
Status: Draft
```

### L2-LAY-015

```req
ID: L2-LAY-015
Level: L2
Type: Functional
Statement: The layout engine shall produce zero connector crossings on a definition made of
  independent source-to-DC-bus chains that share no element.
Rationale: Such a definition needs no crossing, which gives a fixed target for the crossing test.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: a fixture of two independent generator-bus-TRU-bus chains with
  their array entries shuffled gives zero crossings.
Status: Draft
```

### L2-LAY-016

```req
ID: L2-LAY-016
Level: L2
Type: Usability
Statement: The layout engine shall leave no two item bounding boxes overlapping, on definitions of
  up to 50 displayed items, a crew switch touching its own bus bar not counting as an overlap.
Rationale: Overlap is the measurable form of unreadable clutter.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: no pair of items overlaps on the sample or on a 50-item
  fixture.
Status: Draft
```

### L2-LAY-017

```req
ID: L2-LAY-017
Level: L2
Type: Usability
Statement: The layout engine shall route no connector through the bounding box of an item other than
  its two end items.
Rationale: A line through an icon reads as a false connection.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: no connector segment intersects a non-end item on the sample
  or on a 50-item fixture.
Status: Draft
```

### L2-LAY-018

```req
ID: L2-LAY-018
Level: L2
Type: Usability
Statement: The layout engine shall size a 50-item layout so that, scaled uniformly to fit a 1000 ×
  560 px drawing area, every item other than a bus bar measures at least 16 px on its shorter side.
Rationale: This is a measurable form of "readable on a laptop screen". The fit uses the drawing
  area, as L2-WIN-016 does, because the page controls take the rest of the viewport. The 16 px and
  1000 × 560 px figures are project choices.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-LAYOUT
Verification: Test; success criteria: computing the fit scale of a 50-item fixture for a 1000 × 560
  px drawing area and applying it to all non-bus items gives no dimension below 16 px.
Status: Draft
```

<!-- END SECTION LAY-ROUTING -->

## C-API: HTTP API

<!-- BEGIN SECTION API-DEFINITIONS -->

### L2-API-001

```req
ID: L2-API-001
Level: L2
Type: Interface
Statement: The API shall return `{"definitions": [{"id", "aircraft", "revision"}]}` from `GET
  /api/definitions`, with one entry for every `*.json` file in the definitions folder, the file stem
  as `id`, and `aircraft` and `revision` taken from `meta` or null where the file does not give
  them.
Rationale: The definition id is the file stem. A file that does not parse stays listed, so that
  opening it shows its errors, and it has no `meta` to read.
Parent(s): L1-ELA-037
Source: docs/spec.md §6.1; docs/spec.md §7.2; DD-016; DD-024
Allocated to: C-API
Verification: Test; success criteria: with `generic_twin.json`, `other.json`, `raw.json` holding
  `{not json` and `notes.txt` in the folder, `definitions` holds entries with ids `generic_twin`,
  `other` and `raw`, and none for `notes`, the first two give `aircraft` and `revision` from their
  `meta`, and `raw` gives null for both.
Status: Draft
```

### L2-API-002

```req
ID: L2-API-002
Level: L2
Type: Interface
Statement: The API shall return `{"id", "definition", "layout", "warnings"}` from `GET
  /api/definitions/{id}` for a valid definition.
Rationale: The layout is computed in the back end and returned as coordinates.
Parent(s): L1-ELA-040
Source: docs/spec.md §7.1; docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: the response for `generic_twin` holds `id`, `definition`,
  `layout` with `items` and `connectors`, and a `warnings` list of entries with `path` and
  `message`.
Status: Draft
```

### L2-API-003

```req
ID: L2-API-003
Level: L2
Type: Interface
Statement: The API shall return HTTP 422 with `{"errors": [{"path", "message"}], "warnings": [...]}`
  from `GET /api/definitions/{id}` for a stored file that fails validation or does not parse as
  JSON.
Rationale: A file placed in the folder by hand can be invalid and must not open.
Parent(s): L1-ELA-008
Source: docs/spec.md §6.1
Allocated to: C-API
Verification: Test; success criteria: an invalid file in the folder gives 422 with every entry of
  `errors` holding `path` and `message`, a `warnings` list and no `layout`, and a file holding `{not
  json` gives 422 with an `errors` entry at path `$`.
Status: Draft
```

### L2-API-004

```req
ID: L2-API-004
Level: L2
Type: Interface
Statement: The API shall return HTTP 404 from every `/api/definitions/{id}` route when `{id}`
  matches no stored definition.
Rationale: An unknown id is a client error distinct from an invalid file.
Parent(s): L1-ELA-008
Source: docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: `GET`, `analyse`, `batch` and `export` requests on an unknown
  id each give 404.
Status: Draft
```

### L2-API-026

```req
ID: L2-API-026
Level: L2
Type: Interface
Statement: The API shall read its definitions folder from the environment variable
  `ELA_DEFINITIONS_DIR`, defaulting to `definitions/` at the repository root.
Rationale: Upload tests would otherwise write into the real folder.
Parent(s): L1-ELA-037
Source: DD-024
Allocated to: C-API
Verification: Test; success criteria: with the variable set to a temporary folder, listing and
  upload use that folder and leave `definitions/` unchanged, and with it unset the list holds
  `generic_twin`.
Status: Draft
```

<!-- END SECTION API-DEFINITIONS -->

<!-- BEGIN SECTION API-UPLOAD -->

### L2-API-005

```req
ID: L2-API-005
Level: L2
Type: Interface
Statement: The API shall store a valid file posted to `POST /api/definitions` in the definitions
  folder.
Rationale: Uploads extend the definition list.
Parent(s): L1-ELA-038
Source: docs/spec.md §7.2; DD-016
Allocated to: C-API
Verification: Test; success criteria: after posting a valid file, the file exists in the folder and
  its id appears in `GET /api/definitions`.
Status: Draft
```

### L2-API-006

```req
ID: L2-API-006
Level: L2
Type: Interface
Statement: The API shall answer a successful upload with HTTP 201 and `{"id", "warnings"}`.
Rationale: The front end needs the id and any warnings. The 201 status is a project choice.
Parent(s): L1-ELA-038
Source: docs/spec.md §7.2; DD-016
Allocated to: C-API
Verification: Test; success criteria: posting a valid file with one unknown key gives 201 and a body
  holding `id` and a `warnings` list with that key's warning.
Status: Draft
```

### L2-API-007

```req
ID: L2-API-007
Level: L2
Type: Interface
Statement: The API shall reject an invalid or unparsable upload with HTTP 422 and `{"errors":
  [{"path", "message"}], "warnings": [...]}`, storing nothing.
Rationale: Uploads are validated first.
Parent(s): L1-ELA-008
Source: docs/spec.md §7.2; DD-016
Allocated to: C-API
Verification: Test; success criteria: posting a file with 3 errors gives 422 with 3 `errors`
  entries, posting a file holding `{not json` gives 422 with an `errors` entry at path `$`, and the
  folder listing is unchanged.
Status: Draft
```

### L2-API-008

```req
ID: L2-API-008
Level: L2
Type: Interface
Statement: The API shall derive the stored name of an upload by taking the last path segment after
  `/` or `\`, dropping the extension and replacing each character outside `[A-Za-z0-9_-]` with `_`,
  rejecting an empty or Windows-reserved stem with HTTP 422.
Rationale: A sanitised name keeps uploads inside the definitions folder. The reserved stems are CON,
  PRN, AUX, NUL, COM1 to COM9 and LPT1 to LPT9, in any case.
Parent(s): L1-ELA-038
Source: DD-016
Allocated to: C-API
Verification: Test; success criteria: uploading as `../../evil name.json`, `..\..\evil2.json` and
  `/abs/evil3.json` stores one file each inside the folder with a name matching
  `^[A-Za-z0-9_-]+\.json$` and writes nothing outside it, the first stem being `evil_name`, and
  uploads named `.json` and `nul.json` give 422.
Status: Draft
```

### L2-API-009

```req
ID: L2-API-009
Level: L2
Type: Interface
Statement: The API shall return HTTP 409 for a valid upload whose sanitised name, compared
  case-insensitively, is already in use, leaving the existing file unchanged.
Rationale: Silent overwrite would lose a definition.
Parent(s): L1-ELA-038
Source: DD-016
Allocated to: C-API
Verification: Test; success criteria: uploading `generic_twin.json` or `GENERIC_TWIN.json` gives 409
  and the stored file is byte-identical, an invalid file with that name gives 422, and `a b.json`
  followed by `a_b.json` gives 201 then 409.
Status: Draft
```

<!-- END SECTION API-UPLOAD -->

<!-- BEGIN SECTION API-ANALYSE -->

### L2-API-010

```req
ID: L2-API-010
Level: L2
Type: Interface
Statement: The API shall return the analysis of the component states in the body of `POST
  /api/definitions/{id}/analyse`.
Rationale: This is the endpoint behind every interactive state change.
Parent(s): L1-ELA-013
Source: docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: a body setting one generator to `failed` gives a response
  equal to the engine result for that state map.
Status: Draft
```

### L2-API-011

```req
ID: L2-API-011
Level: L2
Type: Interface
Statement: The API shall include per-element energisation, demand and capacity, the verdict,
  overloads, configuration errors, unpowered essential loads and warnings in the analyse response.
Rationale: The status panel and schematic are drawn from these fields.
Parent(s): L1-ELA-052
Source: docs/spec.md §7.2; DD-001
Allocated to: C-API
Verification: Test; success criteria: the response for a failing configuration holds each named
  field with the expected values.
Status: Draft
```

### L2-API-012

```req
ID: L2-API-012
Level: L2
Type: Interface
Statement: The API shall reject an analyse body that fails the `states` check with HTTP 422 and
  `{"errors": [{"path", "message"}], "warnings": [...]}`.
Rationale: The interactive endpoint applies the same check as scenarios.
Parent(s): L1-ELA-010
Source: DD-009
Allocated to: C-API
Verification: Test; success criteria: a body with an unknown id, and a body with an invalid value,
  each give 422 with an `errors` entry holding `path` and `message`, and a `warnings` list.
Status: Draft
```

### L2-API-013

```req
ID: L2-API-013
Level: L2
Type: Interface
Statement: The API shall hold no component state between analyse requests.
Rationale: Each request states its configuration in full, so a request's result does not depend on
  earlier requests.
Parent(s): L1-ELA-032
Source: docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: one request failing a generator followed by one with an empty
  state map gives the default configuration's result.
Status: Draft
```

### L2-API-025

```req
ID: L2-API-025
Level: L2
Type: Interface
Statement: The API shall take the analyse body as `{"states": {...}}` and an upload as multipart
  form data with the field `file`.
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-013, L1-ELA-038
Source: DD-024
Allocated to: C-API
Verification: Test; success criteria: an analyse request with that body gives 200, and an upload
  using field `file` gives 201.
Status: Draft
```

<!-- END SECTION API-ANALYSE -->

<!-- BEGIN SECTION API-BATCH -->

### L2-API-014

```req
ID: L2-API-014
Level: L2
Type: Interface
Statement: The API shall return `{"results": [...]}` from `POST /api/definitions/{id}/batch`,
  holding the result of running each scenario as named in L2-BAT-010.
Rationale: This is the endpoint behind the Run all scenarios button.
Parent(s): L1-ELA-054
Source: docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: `results` in the response for `generic_twin` equals the batch
  runner's serialised results for that definition.
Status: Draft
```

### L2-API-015

```req
ID: L2-API-015
Level: L2
Type: Interface
Statement: The API shall hold the last batch results of each definition in memory for export.
Rationale: Export returns the last batch results. Results are not persisted.
Parent(s): L1-ELA-058
Source: docs/spec.md §7.2; DD-016
Allocated to: C-API
Verification: Test; success criteria: after runs on two definitions, each export returns its own
  definition's results, and after a server restart export returns 404.
Status: Draft
```

### L2-API-016

```req
ID: L2-API-016
Level: L2
Type: Interface
Statement: The API shall return the last batch results from `GET
  /api/definitions/{id}/batch/export?format=csv` as CSV and with `format=json` as JSON.
Rationale: These are the two export formats.
Parent(s): L1-ELA-058
Source: docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: after a run, each format gives status 200 with a body equal to
  the batch runner's serialisation and a matching content type.
Status: Draft
```

### L2-API-017

```req
ID: L2-API-017
Level: L2
Type: Interface
Statement: The API shall return HTTP 404 from the export route when no batch has run for that
  definition.
Rationale: There is nothing to export before a run.
Parent(s): L1-ELA-058
Source: DD-016
Allocated to: C-API
Verification: Test; success criteria: export before any run gives 404 for both formats.
Status: Draft
```

### L2-API-018

```req
ID: L2-API-018
Level: L2
Type: Interface
Statement: The API shall return HTTP 422 from the export route when `format` is absent or is not
  `csv` or `json`.
Rationale: Only two formats exist.
Parent(s): L1-ELA-058
Source: docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: `format=xml` and a request with no `format` after a run each
  give 422.
Status: Draft
```

<!-- END SECTION API-BATCH -->

<!-- BEGIN SECTION API-SERVER -->

### L2-API-019

```req
ID: L2-API-019
Level: L2
Type: Constraint
Statement: The API shall be a FastAPI application served by Uvicorn, implemented in `ela/api.py`
  with the name `app`.
Rationale: FastAPI and Uvicorn are the mandated technology, and the file is fixed by docs/plan.md.
Parent(s): L1-ELA-060
Source: docs/spec.md §7.1
Allocated to: C-API
Verification: Test; success criteria: `ela.api.app` is an instance of `fastapi.FastAPI`.
Status: Draft
```

### L2-API-020

```req
ID: L2-API-020
Level: L2
Type: Interface
Statement: The API shall serve the `web/` folder as static files with `web/index.html` at `/`.
Rationale: The whole tool is served by one process.
Parent(s): L1-ELA-060
Source: docs/spec.md §7.3
Allocated to: C-API
Verification: Test; success criteria: `GET /` returns `web/index.html`, and `GET` on each of the
  other front-end files returns its content with status 200.
Status: Draft
```

### L2-API-021

```req
ID: L2-API-021
Level: L2
Type: Usability
Statement: The API shall start in full from the single command `uvicorn ela.api:app`.
Rationale: One-command start is required.
Parent(s): L1-ELA-060
Source: docs/spec.md §7.3
Allocated to: C-API
Verification: Test; success criteria: running that command gives a process that answers `GET /` and
  `GET /api/definitions` with status 200.
Status: Draft
```

### L2-API-022

```req
ID: L2-API-022
Level: L2
Type: Constraint
Statement: The API shall listen on the loopback address only when started with the documented
  command.
Rationale: This is a local single-user tool.
Parent(s): L1-ELA-061
Source: DD-016
Allocated to: C-API
Verification: Test; success criteria: after starting with that command, the listening socket is
  bound to 127.0.0.1 and to no other address.
Status: Draft
```

### L2-API-023

```req
ID: L2-API-023
Level: L2
Type: Constraint
Statement: The API shall require no authentication on any route.
Rationale: This is a local single-user tool.
Parent(s): L1-ELA-061
Source: DD-016
Allocated to: C-API
Verification: Test; success criteria: every route answers a request with no credentials with a
  status other than 401 or 403.
Status: Draft
```

### L2-API-024

```req
ID: L2-API-024
Level: L2
Type: Constraint
Statement: The API shall expose no route that changes or deletes a stored definition.
Rationale: The JSON file is edited by hand. Upload adds a new file only.
Parent(s): L1-ELA-053
Source: docs/spec.md §2; docs/spec.md §7.2
Allocated to: C-API
Verification: Test; success criteria: the application's routes under `/api` are exactly the 6 in
  docs/spec.md §7.2 and none uses `PUT`, `PATCH` or `DELETE`.
Status: Draft
```

<!-- END SECTION API-SERVER -->

## C-WEBINT: interactive front end

<!-- BEGIN SECTION WIN-DEFINITIONS -->

### L2-WIN-001

```req
ID: L2-WIN-001
Level: L2
Type: Functional
Statement: The interactive front end shall list the definitions returned by `GET /api/definitions`
  in a selection control, refreshing the list on each page load.
Rationale: The engineer picks the aircraft here.
Parent(s): L1-ELA-037
Source: docs/spec.md §6.1
Allocated to: C-WEBINT
Verification: Test; success criteria: in a browser, the control lists every id in the definitions
  folder, a file added to the folder appears after a reload, and choosing `generic_twin` draws its
  schematic.
Status: Draft
```

### L2-WIN-002

```req
ID: L2-WIN-002
Level: L2
Type: Functional
Statement: The interactive front end shall offer a file upload control that posts the chosen file to
  `POST /api/definitions`.
Rationale: A definition can be uploaded from the browser.
Parent(s): L1-ELA-038
Source: docs/spec.md §6.1
Allocated to: C-WEBINT
Verification: Test; success criteria: uploading a valid file adds its id to the selection control
  with no page reload.
Status: Draft
```

### L2-WIN-003

```req
ID: L2-WIN-003
Level: L2
Type: Functional
Statement: The interactive front end shall show a message naming the conflict when an upload returns
  HTTP 409.
Rationale: The engineer needs to know the upload was not stored.
Parent(s): L1-ELA-038
Source: DD-016
Allocated to: C-WEBINT
Verification: Test; success criteria: uploading a second file named `generic_twin.json` shows a
  message containing that name, and the selection control is unchanged.
Status: Draft
```

### L2-WIN-004

```req
ID: L2-WIN-004
Level: L2
Type: Functional
Statement: The interactive front end shall display every validation error with its JSON path and
  message when a definition is rejected.
Rationale: This is the measurable form of "show errors clearly".
Parent(s): L1-ELA-007
Source: docs/spec.md §6.1
Allocated to: C-WEBINT
Verification: Test; success criteria: opening or uploading a file with 3 errors shows 3 visible
  entries, each holding its path and message.
Status: Draft
```

### L2-WIN-005

```req
ID: L2-WIN-005
Level: L2
Type: Functional
Statement: The interactive front end shall draw no schematic for a definition rejected with HTTP
  422.
Rationale: An invalid file is not opened.
Parent(s): L1-ELA-008
Source: docs/spec.md §6.1
Allocated to: C-WEBINT
Verification: Test; success criteria: selecting an invalid stored definition leaves the drawing area
  holding no element of that definition, and the status panel shows no verdict for it.
Status: Draft
```

### L2-WIN-006

```req
ID: L2-WIN-006
Level: L2
Type: Functional
Statement: The interactive front end shall display every warning returned with an opened definition.
Rationale: Warnings are shown but do not block loading.
Parent(s): L1-ELA-009
Source: docs/spec.md §5.2; DD-017
Allocated to: C-WEBINT
Verification: Test; success criteria: opening a definition with an unknown key draws the schematic
  and shows a warning holding the key's path and message.
Status: Draft
```

### L2-WIN-007

```req
ID: L2-WIN-007
Level: L2
Type: Functional
Statement: The interactive front end shall open each definition with an empty state map, so that all
  components are at default and every crew switch is on.
Rationale: The switch is on at the start of every simulation.
Parent(s): L1-ELA-017
Source: docs/spec.md §4.9
Allocated to: C-WEBINT
Verification: Test; success criteria: opening the sample shows the DC BAT switch on, and the analyse
  request body holds no state entries.
Status: Draft
```

### L2-WIN-008

```req
ID: L2-WIN-008
Level: L2
Type: Functional
Statement: The interactive front end shall reset component states, band selection, scenario
  selection and view position when the definition is switched.
Rationale: Switching definition files resets the interactive view.
Parent(s): L1-ELA-039
Source: docs/spec.md §6.1
Allocated to: C-WEBINT
Verification: Test; success criteria: after failing a generator, choosing the 5 s band and panning,
  switching definition shows default states, Continuous, no selected scenario and the initial view.
Status: Draft
```

<!-- END SECTION WIN-DEFINITIONS -->

<!-- BEGIN SECTION WIN-SCHEMATIC -->

### L2-WIN-009

```req
ID: L2-WIN-009
Level: L2
Type: Functional
Statement: The interactive front end shall render the schematic as SVG at the coordinates returned
  by the API.
Rationale: Layout is computed in the back end, so the front end holds no layout logic.
Parent(s): L1-ELA-040
Source: docs/spec.md §7.1; docs/spec.md §7.3
Allocated to: C-WEBINT
Verification: Test; success criteria: the drawing is an `svg` element, each item's rendered position
  matches the layout coordinates within 1 px under the current view transform, and a bus bar's drawn
  top edge equals its `y` within 1 px.
Status: Draft
```

### L2-WIN-010

```req
ID: L2-WIN-010
Level: L2
Type: Functional
Statement: The interactive front end shall draw generators as a circle with "G", batteries with a
  battery symbol, TRUs as a box and buses as thick horizontal bars.
Rationale: These icons are listed in the specification.
Parent(s): L1-ELA-040
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: in the sample drawing, each element kind uses its own SVG
  symbol, the generator symbol holds a circle and the text "G", and each bus bar is wider than it is
  tall.
Status: Draft
```

### L2-WIN-011

```req
ID: L2-WIN-011
Level: L2
Type: Functional
Statement: The interactive front end shall draw, on the `<bus>_switch` item adjacent to each
  crew-switched bus bar, a switch symbol that shows on or off graphically.
Rationale: The switch has to be visible to be clicked.
Parent(s): L1-ELA-048
Source: docs/spec.md §4.9; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: the DC BAT bus has a `[data-id="<bus>_switch"]` symbol whose
  shape differs between `on` and `off`, and no other bus has one.
Status: Draft
```

### L2-WIN-012

```req
ID: L2-WIN-012
Level: L2
Type: Constraint
Statement: The interactive front end shall draw no element for an individual load or circuit
  breaker.
Rationale: Individual loads and circuit breakers are not drawn.
Parent(s): L1-ELA-042
Source: docs/spec.md §2; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: for the sample, the SVG holds no element with an id or text
  equal to any load id or load name.
Status: Draft
```

### L2-WIN-013

```req
ID: L2-WIN-013
Level: L2
Type: Functional
Statement: The interactive front end shall pan the schematic when the engineer drags on it.
Rationale: Pan is required for larger systems.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: a mouse drag of 100 px moves an item's on-screen position by
  100 px in that direction.
Status: Draft
```

### L2-WIN-014

```req
ID: L2-WIN-014
Level: L2
Type: Functional
Statement: The interactive front end shall zoom the schematic when the engineer turns the mouse
  wheel over it.
Rationale: Zoom is required for larger systems.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: wheel events in each direction increase and decrease an item's
  on-screen size.
Status: Draft
```

### L2-WIN-015

```req
ID: L2-WIN-015
Level: L2
Type: Functional
Statement: The interactive front end shall change no component state on a drag that starts or ends
  on a clickable element, treating pointer movement under 5 px as a click.
Rationale: Panning must not fail a component by accident.
Parent(s): L1-ELA-048
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: a 100 px drag starting on a generator and one ending on a
  generator each send no analyse request and leave its state unchanged, and a press and release 3 px
  apart toggles it.
Status: Draft
```

### L2-WIN-016

```req
ID: L2-WIN-016
Level: L2
Type: Usability
Statement: The interactive front end shall show every item of a 50-item schematic inside a drawing
  area of at least 1000 × 560 px at a 1366 × 768 px viewport at the initial view, with label text at
  least 10 px high.
Rationale: This is the measurable form of "readable on a laptop screen". The fit uses the drawing
  area, as L2-LAY-018 does. The figures are project choices.
Parent(s): L1-ELA-041
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: at that viewport with a 50-item fixture, the drawing area
  measures at least 1000 × 560 px, each item's bounding box lies inside it, and each text element's
  rendered height is at least 10 px.
Status: Draft
```

<!-- END SECTION WIN-SCHEMATIC -->

<!-- BEGIN SECTION WIN-COLOURS -->

### L2-WIN-017

```req
ID: L2-WIN-017
Level: L2
Type: Functional
Statement: The interactive front end shall colour each energised element that is not overloaded
  green.
Rationale: Green is the energised colour.
Parent(s): L1-ELA-043
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: an energised bus, source, TRU and closed contactor each have a
  computed colour of hue 90° to 150°.
Status: Draft
```

### L2-WIN-018

```req
ID: L2-WIN-018
Level: L2
Type: Functional
Statement: The interactive front end shall colour each de-energised element dark grey, at a contrast
  of at least 3:1 against the drawing background.
Rationale: De-energised elements stay visible. The contrast figure is a project choice that makes
  "still visible" testable.
Parent(s): L1-ELA-043
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: a de-energised bus and an open contactor have a computed
  colour of saturation at most 15 % and the stated contrast.
Status: Draft
```

### L2-WIN-019

```req
ID: L2-WIN-019
Level: L2
Type: Functional
Statement: The interactive front end shall colour amber each element overloaded in any band,
  whichever band is displayed.
Rationale: Amber shows an overload in any band.
Parent(s): L1-ELA-043
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: a bus overloaded only in `transient` has a computed colour of
  hue 30° to 50° under each of the 3 band selections.
Status: Draft
```

### L2-WIN-020

```req
ID: L2-WIN-020
Level: L2
Type: Functional
Statement: The interactive front end shall draw each failed source and failed TRU dark grey with a
  failure mark.
Rationale: This separates a failed unit from one that is merely unfed.
Parent(s): L1-ELA-043
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: a failed generator and a failed TRU each show the dark grey
  colour and a visible mark, and a de-energised operative TRU and an unavailable RAT output show no
  mark.
Status: Draft
```

### L2-WIN-021

```req
ID: L2-WIN-021
Level: L2
Type: Functional
Statement: The interactive front end shall show each contactor's open or closed state by symbol
  shape, in addition to colour.
Rationale: State has to be readable without relying on colour alone.
Parent(s): L1-ELA-043
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: with colours compared as equal, the rendered path geometry of
  a contactor differs between `open` and `closed`.
Status: Draft
```

<!-- END SECTION WIN-COLOURS -->

<!-- BEGIN SECTION WIN-LABELS -->

### L2-WIN-022

```req
ID: L2-WIN-022
Level: L2
Type: Functional
Statement: The interactive front end shall show on each energised bus a label with voltage in V,
  current in A to 2 decimals and bus demand as power for the selected band.
Rationale: Label values use throughput under DD-002, not own-load power.
Parent(s): L1-ELA-044
Source: docs/spec.md §3.7; docs/spec.md §6.2; DD-002
Allocated to: C-WEBINT
Verification: Test; success criteria: each energised sample bus shows the three values, the power
  equals the bus's throughput demand for the band, and 2500 W on a 115 V 3-phase bus shows `7.25 A`.
Status: Draft
```

### L2-WIN-023

```req
ID: L2-WIN-023
Level: L2
Type: Functional
Statement: The interactive front end shall show no value label on a de-energised bus.
Rationale: Labels are shown only on energised buses.
Parent(s): L1-ELA-044
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: after failing all sources, no bus shows a value label.
Status: Draft
```

### L2-WIN-024

```req
ID: L2-WIN-024
Level: L2
Type: Functional
Statement: The interactive front end shall offer a band selector showing the three band labels, with
  Continuous selected by default, that sets the band shown in bus labels.
Rationale: Labels come from `settings.bands`.
Parent(s): L1-ELA-044
Source: docs/spec.md §6.2; DD-010
Allocated to: C-WEBINT
Verification: Test; success criteria: the selector shows Transient, 5 s and Continuous for the
  sample with Continuous selected, and choosing another band changes every label to that band's
  values with no analyse request.
Status: Draft
```

### L2-WIN-025

```req
ID: L2-WIN-025
Level: L2
Type: Functional
Statement: The interactive front end shall display power, after rounding to the nearest watt, as an
  integer in W below 1000 W and in kW with two decimals from 1000 W.
Rationale: The threshold is in the specification and applies after rounding, so 999.6 W never shows
  as `1000 W`. The number formats are a project choice.
Parent(s): L1-ELA-031
Source: docs/spec.md §3.7
Allocated to: C-WEBINT
Verification: Test; success criteria: 999 W displays as `999 W`, 1000 W as `1.00 kW`, 12340 W as
  `12.34 kW` and 999.6 W as `1.00 kW`.
Status: Draft
```

### L2-WIN-026

```req
ID: L2-WIN-026
Level: L2
Type: Functional
Statement: The interactive front end shall name, by its band label, in the label of an overloaded
  element every failed band that is not the displayed band.
Rationale: Labels come from `settings.bands`. A contactor has no value label, so it gets a label
  only while overloaded.
Parent(s): L1-ELA-045
Source: docs/spec.md §6.2; DD-010
Allocated to: C-WEBINT
Verification: Test; success criteria: a bus overloaded in `transient` and `short_term` with
  Continuous displayed names `Transient` and `5 s`, and with Transient displayed names `5 s` alone.
Status: Draft
```

### L2-WIN-027

```req
ID: L2-WIN-027
Level: L2
Type: Functional
Statement: The interactive front end shall show in a tooltip the demand, demand with margin,
  capacity and remaining margin in W with its percentage, of the element for all three bands.
Rationale: The tooltip is the only view of all three bands together.
Parent(s): L1-ELA-046
Source: docs/spec.md §6.2; DD-011
Allocated to: C-WEBINT
Verification: Test; success criteria: the tooltip of a rated bus shows 12 values equal to the
  analysis result, with remaining margin in W with its percentage, and that of an unrated element
  shows its demand with `no capacity` in place of capacity and margin.
Status: Draft
```

### L2-WIN-028

```req
ID: L2-WIN-028
Level: L2
Type: Functional
Statement: The interactive front end shall show in a tooltip the element's `name` and, for a bus,
  its `role` and its own-load power for all three bands.
Rationale: Names are not drawn for every item, the role is used for display, and bus labels show
  throughput only.
Parent(s): L1-ELA-046
Source: docs/spec.md §4; docs/spec.md §4.5; docs/spec.md §6.2; DD-002
Allocated to: C-WEBINT
Verification: Test; success criteria: the tooltip of AC ESS shows its name, `essential` and its
  own-load power in each band.
Status: Draft
```

### L2-WIN-029

```req
ID: L2-WIN-029
Level: L2
Type: Functional
Statement: The interactive front end shall open the tooltip of any drawn element on mouse hover.
Rationale: Hover is the main way to reach the detail.
Parent(s): L1-ELA-046
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: hovering over one source, bus, TRU, contactor and crew switch
  each opens that element's tooltip.
Status: Draft
```

### L2-WIN-030

```req
ID: L2-WIN-030
Level: L2
Type: Functional
Statement: The interactive front end shall open the tooltip of any drawn element on a touch tap.
Rationale: DD-022 rules that a tap on a clickable element both toggles it and shows its tooltip, so
  the tooltip shows the new state.
Parent(s): L1-ELA-046
Source: docs/spec.md §6.2; DD-022
Allocated to: C-WEBINT
Verification: Test; success criteria: with touch emulation, a tap on a bus opens its tooltip, and a
  tap on a contactor toggles it and opens its tooltip.
Status: Draft
```

### L2-WIN-031

```req
ID: L2-WIN-031
Level: L2
Type: Functional
Statement: The interactive front end shall show on each energised source and TRU its load and its
  percentage of capacity to at most 2 decimals for the selected band.
Rationale: This shows how hard each supply is working.
Parent(s): L1-ELA-047
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: an energised generator at 45000 W of 90000 W capacity shows
  `45.00 kW` and `50 %`, a TRU at 28.33 % shows `28.33 %`, and a failed generator shows neither.
Status: Draft
```

<!-- END SECTION WIN-LABELS -->

<!-- BEGIN SECTION WIN-INTERACTION -->

### L2-WIN-032

```req
ID: L2-WIN-032
Level: L2
Type: Functional
Statement: The interactive front end shall toggle a generator, APU generator, battery or TRU between
  `operative` and `failed` on each click.
Rationale: Failing a generator represents an engine shutdown or generator loss.
Parent(s): L1-ELA-048
Source: docs/spec.md §4.1; docs/spec.md §4.2; docs/spec.md §4.4; docs/spec.md §4.7; docs/spec.md
  §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: one click on each of the 4 kinds gives `failed`, and a second
  click gives `operative`.
Status: Draft
```

### L2-WIN-033

```req
ID: L2-WIN-033
Level: L2
Type: Functional
Statement: The interactive front end shall toggle each emergency generator output separately between
  `available` and `unavailable` on each click.
Rationale: Each RAT output is its own source, clicked independently.
Parent(s): L1-ELA-048
Source: docs/spec.md §4.3; docs/spec.md §6.2; DD-008
Allocated to: C-WEBINT
Verification: Test; success criteria: with AC and DC outputs defined, a click on one changes that
  output's state alone.
Status: Draft
```

### L2-WIN-034

```req
ID: L2-WIN-034
Level: L2
Type: Functional
Statement: The interactive front end shall toggle a contactor or bus tie between `closed` and `open`
  on each click.
Rationale: Contactors are clickable.
Parent(s): L1-ELA-048
Source: docs/spec.md §4.8; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: one click each on a source contactor, a TRU contactor and a
  bus tie gives `open`, and a second click gives `closed`.
Status: Draft
```

### L2-WIN-035

```req
ID: L2-WIN-035
Level: L2
Type: Functional
Statement: The interactive front end shall toggle a crew switch between `on` and `off` on each click
  of the switch symbol.
Rationale: The crew switch is clickable.
Parent(s): L1-ELA-048
Source: docs/spec.md §4.9; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: one click on the DC BAT switch gives `off` and the bus
  tooltip's own-load power becomes 0 W, and a second click restores it.
Status: Draft
```

### L2-WIN-036

```req
ID: L2-WIN-036
Level: L2
Type: Functional
Statement: The interactive front end shall change no state when the engineer clicks a bus bar.
Rationale: Only components marked clickable can be changed.
Parent(s): L1-ELA-048
Source: docs/spec.md §4; docs/spec.md §4.10
Allocated to: C-WEBINT
Verification: Test; success criteria: clicking each sample bus bar, away from any switch symbol,
  sends no analyse request.
Status: Draft
```

### L2-WIN-037

```req
ID: L2-WIN-037
Level: L2
Type: Functional
Statement: The interactive front end shall send the new state map to the analyse endpoint and redraw
  the schematic after each state-changing click, with no other user action.
Rationale: This replaces "instantly" with what can be tested. Each click recomputes the analysis.
Parent(s): L1-ELA-049
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: each click produces exactly one analyse request, and the
  display reflects its response with no further input.
Status: Draft
```

### L2-WIN-038

```req
ID: L2-WIN-038
Level: L2
Type: Performance
Statement: The interactive front end shall complete the round trip from click to finished redraw
  within 1 second on the sample definition.
Rationale: The 1 second figure is a project choice that gives "instantly" a testable limit.
Parent(s): L1-ELA-049
Source: docs/spec.md §1; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: over 20 clicks on the sample with the server on the local
  machine, the slowest time from click to redraw is at most 1000 ms.
Status: Draft
```

### L2-WIN-039

```req
ID: L2-WIN-039
Level: L2
Type: Constraint
Statement: The interactive front end shall offer no control that adds, removes or changes a
  component or load in the definition.
Rationale: The JSON file is edited by hand.
Parent(s): L1-ELA-053
Source: docs/spec.md §2
Allocated to: C-WEBINT
Verification: Test; success criteria: the page has no input for component or load values, and the
  stored definition file is byte-identical after a session of clicks.
Status: Draft
```

<!-- END SECTION WIN-INTERACTION -->

<!-- BEGIN SECTION WIN-STATUS -->

### L2-WIN-040

```req
ID: L2-WIN-040
Level: L2
Type: Functional
Statement: The interactive front end shall return all components, including crew switches, to their
  default states when the Reset button is pressed, keeping the band selection and clearing the
  scenario selection.
Rationale: This gives a known starting point.
Parent(s): L1-ELA-050
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: after several clicks, a band change and a scenario selection,
  Reset gives the same component states and verdict as a freshly opened definition, with the band
  unchanged and no scenario selected.
Status: Draft
```

### L2-WIN-041

```req
ID: L2-WIN-041
Level: L2
Type: Functional
Statement: The interactive front end shall list every scenario of the open definition in a Load
  scenario dropdown.
Rationale: The dropdown reaches any planned configuration.
Parent(s): L1-ELA-051
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: the dropdown has one entry per scenario in the sample, showing
  its name.
Status: Draft
```

### L2-WIN-042

```req
ID: L2-WIN-042
Level: L2
Type: Functional
Statement: The interactive front end shall set the state map to exactly the chosen scenario's
  `states` when a scenario is selected, clearing that selection on any later state-changing click on
  the schematic.
Rationale: Anything not listed uses its default, so earlier clicks do not carry over. After a click
  the schematic no longer shows the scenario, so the selection would be stale.
Parent(s): L1-ELA-051
Source: docs/spec.md §5.2; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: failing a generator, then selecting a scenario that does not
  list it, shows that generator operative and the scenario's batch verdict, and a further click on a
  contactor leaves no scenario selected.
Status: Draft
```

### L2-WIN-043

```req
ID: L2-WIN-043
Level: L2
Type: Functional
Statement: The interactive front end shall show PASS or FAIL for the current configuration in a
  status panel.
Rationale: The verdict is the main result.
Parent(s): L1-ELA-052
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: the panel shows PASS for the sample default and FAIL after
  selecting a designed-to-fail scenario.
Status: Draft
```

### L2-WIN-044

```req
ID: L2-WIN-044
Level: L2
Type: Functional
Statement: The interactive front end shall list in the status panel every overload with element,
  band label, demand with margin and capacity.
Rationale: The engineer sees exactly what failed.
Parent(s): L1-ELA-052
Source: docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: an element overloaded in 2 bands gives 2 entries, each with
  the 4 values from the analysis result and the band shown by its label.
Status: Draft
```

### L2-WIN-045

```req
ID: L2-WIN-045
Level: L2
Type: Functional
Statement: The interactive front end shall list in the status panel every configuration error with
  its message.
Rationale: A configuration error can fail a configuration with no overload.
Parent(s): L1-ELA-052
Source: docs/spec.md §3.5; docs/spec.md §6.2
Allocated to: C-WEBINT
Verification: Test; success criteria: on the sample, closing the tie between AC BUS 1 and AC BUS 2
  with both engine generators live lists a message containing "AC sources paralleled".
Status: Draft
```

### L2-WIN-046

```req
ID: L2-WIN-046
Level: L2
Type: Functional
Statement: The interactive front end shall list in the status panel every unpowered essential load
  by name.
Rationale: Each one is reported.
Parent(s): L1-ELA-052
Source: DD-001
Allocated to: C-WEBINT
Verification: Test; success criteria: on the sample, setting the DC BAT switch `off` lists each
  essential load on that bus by name.
Status: Draft
```

### L2-WIN-047

```req
ID: L2-WIN-047
Level: L2
Type: Functional
Statement: The interactive front end shall show `meshed_island` warnings in the status panel with no
  effect on the verdict.
Rationale: The warning keeps the assumption visible.
Parent(s): L1-ELA-023
Source: DD-004
Allocated to: C-WEBINT
Verification: Test; success criteria: closing a loop of ties shows the warning naming the omitted
  contactor, and the verdict equals the analysis verdict.
Status: Draft
```

<!-- END SECTION WIN-STATUS -->

<!-- BEGIN SECTION WIN-STACK -->

### L2-WIN-048

```req
ID: L2-WIN-048
Level: L2
Type: Constraint
Statement: The interactive front end shall use plain HTML, CSS and JavaScript with no framework.
Rationale: This keeps the front end free of a build chain.
Parent(s): L1-ELA-062
Source: docs/spec.md §7.3
Allocated to: C-WEBINT
Verification: Inspection; success criteria: the front-end files reference no framework such as
  React, Vue, Angular or Svelte.
Status: Draft
```

### L2-WIN-049

```req
ID: L2-WIN-049
Level: L2
Type: Constraint
Statement: The interactive front end shall load as ES modules directly from the source files, with
  no build step.
Rationale: No build step is permitted.
Parent(s): L1-ELA-062
Source: docs/spec.md §7.3; DD-003
Allocated to: C-WEBINT
Verification: Inspection; success criteria: `web/index.html` loads `app.js` with `type="module"`,
  and the repository holds no `package.json` and no bundler configuration.
Status: Draft
```

### L2-WIN-050

```req
ID: L2-WIN-050
Level: L2
Type: Constraint
Statement: The interactive front end shall be implemented in `web/index.html`, `web/app.js`,
  `web/schematic.js` and `web/styles.css`.
Rationale: The files are fixed by docs/plan.md.
Parent(s): L1-ELA-062
Source: docs/spec.md §7.1
Allocated to: C-WEBINT
Verification: Test; success criteria: the 4 files exist and are each served with status 200 by the
  running tool.
Status: Draft
```

### L2-WIN-053

```req
ID: L2-WIN-053
Level: L2
Type: Interface
Statement: The interactive front end shall expose the hooks `[data-id="X"]` on the SVG group of
  element X, `data-state` holding its state and being empty on a bus with no crew switch,
  `[data-label="X"]` on its value label, and the ids `definition-select`, `definition-upload`,
  `band-select`, `scenario-select`, `reset`, `status-verdict`, `status-list`, `tooltip`, `message`,
  `warnings` and `schematic`.
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-066
Source: DD-024
Allocated to: C-WEBINT
Verification: Test; success criteria: on the sample page, each named id exists exactly once, each
  displayed element has a `data-id` group with a `data-state` attribute, and that attribute is empty
  on a bus with no crew switch.
Status: Draft
```

### L2-WIN-051

```req
ID: L2-WIN-051
Level: L2
Type: Constraint
Statement: The interactive front end test suite shall verify every requirement on page behaviour in
  C-WEBINT with Playwright browser tests driven from pytest.
Rationale: Every user interface requirement gets a repeatable test.
Parent(s): L1-ELA-066
Source: DD-003
Allocated to: C-WEBINT
Verification: Test; success criteria: `pytest tests -m "e2e and not meta"`, run in a subprocess,
  runs the browser tests against the running tool and passes, and each such requirement has at least
  one `e2e` test.
Status: Draft
```

### L2-WIN-052

```req
ID: L2-WIN-052
Level: L2
Type: Constraint
Statement: The interactive front end shall ship with no dependency on Playwright.
Rationale: Playwright is a dev-only dependency. This rests only on the project ruling.
Parent(s): Derived(DD-003)
Source: DD-003
Allocated to: C-WEBINT
Verification: Test; success criteria: `pyproject.toml` lists Playwright only in a development
  dependency group, and no file in `web/` refers to it.
Status: Draft
```

<!-- END SECTION WIN-STACK -->

## C-WEBBAT: batch front end

<!-- BEGIN SECTION WBT-RUN -->

### L2-WBT-001

```req
ID: L2-WBT-001
Level: L2
Type: Functional
Statement: The batch front end shall offer a Run all scenarios button that requests `POST
  /api/definitions/{id}/batch` for the open definition.
Rationale: This starts batch verification from the browser.
Parent(s): L1-ELA-054
Source: docs/spec.md §6.3
Allocated to: C-WEBBAT
Verification: Test; success criteria: pressing the button on the sample sends one such request and
  fills the results table.
Status: Draft
```

### L2-WBT-002

```req
ID: L2-WBT-002
Level: L2
Type: Functional
Statement: The batch front end shall show in a results table one row per scenario, with columns for
  scenario id, name, PASS or FAIL, worst element and band, smallest remaining margin to at most 2
  decimals, number of overloads counted as element-band entries, configuration errors and unpowered
  essential loads.
Rationale: These are the columns of §6.3 with the DD-001 addition.
Parent(s): L1-ELA-055
Source: docs/spec.md §6.3; DD-001
Allocated to: C-WEBBAT
Verification: Test; success criteria: the table for the sample has one row per scenario, every cell
  equals the batch result, and margins of 56 %, 12 % and -46.67 % show as `56`, `12` and `-46.67`.
Status: Draft
```

### L2-WBT-003

```req
ID: L2-WBT-003
Level: L2
Type: Functional
Statement: The batch front end shall show an empty value marker in the worst element and margin
  cells of a scenario with nothing checked.
Rationale: DD-011 gives null in that case.
Parent(s): L1-ELA-055
Source: DD-011
Allocated to: C-WEBBAT
Verification: Test; success criteria: a row for a scenario with all sources failed shows `—` in
  those cells, with no `null` or `undefined` text.
Status: Draft
```

### L2-WBT-004

```req
ID: L2-WBT-004
Level: L2
Type: Functional
Statement: The batch front end shall clear the results table when the definition is switched.
Rationale: Results of one aircraft must not be read against another.
Parent(s): L1-ELA-054
Source: docs/spec.md §6.1
Allocated to: C-WEBBAT
Verification: Test; success criteria: after a run, switching definition leaves the table with no
  result rows.
Status: Draft
```

### L2-WBT-005

```req
ID: L2-WBT-005
Level: L2
Type: Constraint
Statement: The batch front end shall be implemented in `web/batch.js` as an ES module with no
  framework.
Rationale: The file is fixed by docs/plan.md.
Parent(s): L1-ELA-062
Source: docs/spec.md §7.1; docs/spec.md §7.3
Allocated to: C-WEBBAT
Verification: Test; success criteria: `web/batch.js` is served with status 200 and is loaded through
  an ES module import.
Status: Draft
```

### L2-WBT-013

```req
ID: L2-WBT-013
Level: L2
Type: Interface
Statement: The batch front end shall expose the ids `run-batch`, `batch-table`, `export-csv` and
  `export-json`.
Rationale: DD-024 makes these names binding so that tests can be written before the code.
Parent(s): L1-ELA-066
Source: DD-024
Allocated to: C-WEBBAT
Verification: Test; success criteria: on the page, each named id exists exactly once.
Status: Draft
```

### L2-WBT-006

```req
ID: L2-WBT-006
Level: L2
Type: Constraint
Statement: The batch front end test suite shall verify every requirement on page behaviour in
  C-WEBBAT with Playwright browser tests driven from pytest.
Rationale: Every user interface requirement gets a repeatable test.
Parent(s): L1-ELA-066
Source: DD-003
Allocated to: C-WEBBAT
Verification: Test; success criteria: `pytest tests -m "e2e and not meta"`, run in a subprocess,
  runs the batch browser tests against the running tool and passes, and each such requirement has at
  least one `e2e` test.
Status: Draft
```

<!-- END SECTION WBT-RUN -->

<!-- BEGIN SECTION WBT-DRILLDOWN -->

### L2-WBT-007

```req
ID: L2-WBT-007
Level: L2
Type: Functional
Statement: The batch front end shall show, when a row's expand control is activated, every failing
  element and band, every configuration error message, every unpowered essential load and every
  warning of that scenario.
Rationale: The row shows only the worst element.
Parent(s): L1-ELA-056
Source: docs/spec.md §6.3; DD-001
Allocated to: C-WEBBAT
Verification: Test; success criteria: expanding a scenario with 3 failing element-band pairs lists
  all 3, and expanding a looped scenario lists its `meshed_island` warning.
Status: Draft
```

### L2-WBT-008

```req
ID: L2-WBT-008
Level: L2
Type: Functional
Statement: The batch front end shall give each row an expand control that is separate from the row's
  open action.
Rationale: DD-022 rules that a row has a separate expand control.
Parent(s): L1-ELA-056
Source: docs/spec.md §6.3; DD-022
Allocated to: C-WEBBAT
Verification: Test; success criteria: activating the expand control shows the detail, and the view
  remains the batch results with no interactive state change.
Status: Draft
```

### L2-WBT-009

```req
ID: L2-WBT-009
Level: L2
Type: Functional
Statement: The batch front end shall open a scenario in interactive mode when its row is clicked
  outside the expand control.
Rationale: The engineer inspects a failed scenario on the schematic. DD-022 gives the rest of the
  row this action.
Parent(s): L1-ELA-057
Source: docs/spec.md §6.3; DD-022
Allocated to: C-WEBBAT
Verification: Test; success criteria: clicking a failing row shows the schematic with that scenario
  selected and with the verdict equal to the row's verdict.
Status: Draft
```

<!-- END SECTION WBT-DRILLDOWN -->

<!-- BEGIN SECTION WBT-EXPORT -->

### L2-WBT-010

```req
ID: L2-WBT-010
Level: L2
Type: Functional
Statement: The batch front end shall offer an export control that downloads the last results as CSV.
Rationale: Results are needed outside the tool.
Parent(s): L1-ELA-058
Source: docs/spec.md §6.3
Allocated to: C-WEBBAT
Verification: Test; success criteria: activating the control downloads a file whose content equals
  the API's CSV export.
Status: Draft
```

### L2-WBT-011

```req
ID: L2-WBT-011
Level: L2
Type: Functional
Statement: The batch front end shall offer an export control that downloads the last results as
  JSON.
Rationale: Results are needed outside the tool.
Parent(s): L1-ELA-058
Source: docs/spec.md §6.3
Allocated to: C-WEBBAT
Verification: Test; success criteria: activating the control downloads a file whose content equals
  the API's JSON export.
Status: Draft
```

### L2-WBT-012

```req
ID: L2-WBT-012
Level: L2
Type: Functional
Statement: The batch front end shall enable both export controls only while the results table shows
  results.
Rationale: Export before any run has nothing to return, and exports must not outlive a table cleared
  by L2-WBT-004.
Parent(s): L1-ELA-058
Source: DD-016
Allocated to: C-WEBBAT
Verification: Test; success criteria: before a run both controls are disabled, after a run both are
  enabled, and after switching definition both are disabled.
Status: Draft
```

<!-- END SECTION WBT-EXPORT -->

## C-DOCS: user documentation

<!-- BEGIN SECTION DOC-README -->

### L2-DOC-001

```req
ID: L2-DOC-001
Level: L2
Type: Usability
Statement: The README shall give installation steps using uv in `README.md` at the repository root.
Rationale: Installation is a listed README topic.
Parent(s): L1-ELA-064
Source: docs/spec.md §7.1; docs/spec.md §8; DD-018
Allocated to: C-DOCS
Verification: Test; success criteria: `README.md` has an installation heading, and its commands run
  on a clean checkout with exit code 0.
Status: Draft
```

### L2-DOC-002

```req
ID: L2-DOC-002
Level: L2
Type: Usability
Statement: The README shall state the one-command start of the tool and the local address to open.
Rationale: Running is a listed README topic.
Parent(s): L1-ELA-060
Source: docs/spec.md §7.3; docs/spec.md §8
Allocated to: C-DOCS
Verification: Test; success criteria: the running section holds `uvicorn ela.api:app`, and the
  address it gives serves the tool after that command.
Status: Draft
```

### L2-DOC-003

```req
ID: L2-DOC-003
Level: L2
Type: Usability
Statement: The README shall describe the batch command with its `--csv` and `--json` options and
  exit codes 0, 1 and 2.
Rationale: Automation users rely on these.
Parent(s): L1-ELA-064
Source: docs/spec.md §6.3; docs/spec.md §8; DD-018
Allocated to: C-DOCS
Verification: Test; success criteria: the running section holds the command, both options and each
  exit code with its meaning.
Status: Draft
```

### L2-DOC-004

```req
ID: L2-DOC-004
Level: L2
Type: Usability
Statement: The README shall give a JSON format reference naming every key of the definition schema,
  with its units.
Rationale: The file is edited by hand.
Parent(s): L1-ELA-064
Source: docs/spec.md §5; docs/spec.md §8
Allocated to: C-DOCS
Verification: Test; success criteria: every key in the model's generated schema appears in the
  reference section, which also states watts, volts and decimals.
Status: Draft
```

### L2-DOC-005

```req
ID: L2-DOC-005
Level: L2
Type: Usability
Statement: The README shall state the meaning of each of the three bands.
Rationale: Authors have to know what figure belongs in each band.
Parent(s): L1-ELA-011
Source: docs/spec.md §3.1
Allocated to: C-DOCS
Verification: Test; success criteria: the reference section names `transient`, `short_term` and
  `continuous`, with inrush peak, first 5 seconds and steady state respectively.
Status: Draft
```

### L2-DOC-006

```req
ID: L2-DOC-006
Level: L2
Type: Usability
Statement: The README shall state that band ordering is typical and is not enforced.
Rationale: Authors can then give a load that departs from the typical pattern.
Parent(s): L1-ELA-012
Source: docs/spec.md §3.1
Allocated to: C-DOCS
Verification: Test; success criteria: the reference section states that the tool does not enforce
  `transient ≥ short_term ≥ continuous`.
Status: Draft
```

### L2-DOC-007

```req
ID: L2-DOC-007
Level: L2
Type: Usability
Statement: The README shall give the steps for adding a new aircraft.
Rationale: Adding an aircraft is a listed README topic.
Parent(s): L1-ELA-064
Source: docs/spec.md §8
Allocated to: C-DOCS
Verification: Test; success criteria: a section with that subject exists and names the
  `definitions/` folder and the validation step.
Status: Draft
```

<!-- END SECTION DOC-README -->
