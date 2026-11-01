# How requirements are constructed and tested

This report explains how the ELA tool's requirements were built from the specification and how each one is verified. The counts below are for baseline `main` at `d694112`, before the audit corrections in epic E10.

| Item | Count | File |
| --- | --- | --- |
| Design decisions | 34 | `docs/decisions.md` |
| Requirements | 378 | `docs/requirements.md` |
| Test cases | 339 | `docs/test-cases.md` |
| Generated trace | One row per requirement | `docs/traceability.md` |

## Construction

**Start from one authority.** The specification (`docs/spec.md`) states what the tool must do. Where it was silent or ambiguous, a numbered decision settles the point and records why. Decisions take precedence over the specification.

**Decompose in three levels.** Each level answers a narrower question, and every record links to its parent.

| Level | Question | Count | Example |
| --- | --- | --- | --- |
| L0, stakeholder | What must the tool achieve for an engineer? | 9 | Show that power is sufficient in every planned configuration |
| L1, system | How does the whole tool behave from outside? | 66 | A configuration fails if demand with margin exceeds capacity |
| L2, component | What must each part do? | 303 | The engine evaluates the capacity criterion in each band |

**Allocate each L2 requirement to one component.** There are 11 components, such as `C-ENGINE`, `C-API` and `C-WEBINT`. L2 sections group related records, and each section became one GitHub issue under an epic.

**Write each record the same way.** A record has one "shall", a rationale, its parent, its source, its allocated component and a measurable success criterion. For example:

```text
ID: L2-ENG-041
Statement: The engine shall evaluate demand × (1 + safety_margin) ≤ capacity
  for each checked element in each of the three bands, treating an excess
  within 1e-6 W as satisfying it.
Parent(s): L1-ELA-024
Source: docs/spec.md §3.6; DD-023
Allocated to: C-ENGINE
Verification: Test; success criteria: with demand 1000 W and margin 0.10, the
  check holds at capacity 1100 W and fails at capacity 1099 W ...
```

## Testing

**Test cases come from a separate author.** A verification engineer who did not write the requirements wrote the test cases. Writing them exposed 11 high-severity defects before any code existed. For example, floating-point rounding would have failed a case exactly at the limit, and one bus formula counted TRU power twice.

**Expected values are worked by hand.** Numerical cases state their arithmetic in the case text, derived from the requirements and not from the code. The case for `L2-ENG-041` is an example:

> 3000 × 1.10 = 3300, so at capacity 3300 G1 is not overloaded. In IEEE doubles `3000 * 1.1` is 3300.0000000000005, so a bare `<=` fails this case.

**Each level has its own test method.**

| Level | Verified through | Test files |
| --- | --- | --- |
| L2 back end | Unit tests | `test_model`, `test_validate`, `test_engine`, `test_layout`, `test_batch`, `test_cli`, `test_api`, `test_sample` |
| L2 front end | Playwright in real Chromium | `test_web_interactive`, `test_web_batch` |
| L1 system | Black-box through the CLI, API and browser, without importing the engine | `test_system` |
| L0 acceptance | End to end on the sample aircraft | `test_acceptance` |

Of the 378 requirements, 375 are verified by test. The other 3 are verified by inspection, and each of those also has an automated check.

**The sample has a separate calculation.** `tools/hand_calc_sample.py` works out expected results without importing the engine, and they must agree on all 15 sample scenarios.

## Keeping the trace intact

Every test carries a mark naming its case:

```python
@pytest.mark.tc("TC-ENG-044")
def test_equality_survives_binary_rounding(): ...
```

The chain runs from requirement to case, from case to test, and from test to code. `tests/test_traceability.py` fails the suite if:

- a requirement has no test case
- a test case verifies nothing, or has no test
- a test names a case that does not exist
- `docs/traceability.md` is out of date

## Independent checks

Passing tests show only what the tests look for, so three further checks were applied:

- **Re-running on `main`.** Each agent's report was checked by running the suite again. This caught an intermittent failure that one report had missed.
- **Audit.** An auditor who took no part in the build compared the running tool with the specification, using hand-calculated aircraft and 9,000 random configurations. It found no wrong figures or verdicts. It did find 16 findings of other kinds, recorded in `docs/audit.md`.
- **Injected faults.** The auditor added 72 deliberate faults to copies of the code, and 7 got past the tests. Tests that catch them are part of epic E10.

## Known limits

- The authors of the hand calculation and the audit oracle had both read the engine first, so neither is fully blind. Only a reviewer who has not seen the code can close this.
- Some readability requirements use measurable stand-ins, such as minimum text size and no overlaps. These approximate "readable" and do not prove it.
- The tool follows MIL-E-7016F as reference methodology. Compliance with that standard is not verified.
