# Independent audit, 31 October 2026

Audit of `main` at `cc2a9fd`. No wrong figure or wrong verdict was found against the rulings: over 100 hand-calculated values, and 9,000 random configurations against an independent re-implementation. The auditor had read the engine before writing its oracle.

Rulings are in `docs/decisions.md`. Line numbers refer to the audited commit.

## Findings

| # | Severity | Location | Finding | Disposition |
| --- | --- | --- | --- | --- |
| 1 | High | `ela/engine.py:303`, `:393`, `README.md:302` | The verdict of a rated bus on a loop depends on its id. | DD-026 |
| 2 | High | `ela/layout.py:774`, `web/app.js:178` | Id `<bus>_switch` removes the crew switch and redirects clicks. | DD-027 |
| 3 | High | `web/schematic.js:527` | At about 50 items with realistic names, labels are dropped or clipped. | Fix: ellipsis, not dropping; reserve width; test text overlap and clipping with real names |
| 4 | Medium | `web/app.js:230` | A failed analysis leaves the old verdict on screen. | DD-031 |
| 5 | Medium | `ela/cli.py:44`, `ela/api.py:63` | Repeated JSON keys are dropped silently. | DD-028 |
| 6 | Medium | `ela/layout.py:220` | Reversed TRU contactors are drawn in the wrong rows. | Fix: choose the row from the joined bus, as `ela/engine.py:176` does |
| 7 | Medium | `ela/api.py:113`, `:159` | Upload and analyse bodies are unbounded, and analysis blocks the event loop. | DD-028; run analysis off the event loop |
| 8 | Medium | `ela/api.py:206` | Any website can drive the local server. | DD-029 |
| 9, 10 | Low | `ela/model.py:25`, `ela/engine.py:471`, `web/schematic.js:43` | Extreme values crash analysis and the page. | DD-028 |
| 11 | Low | `ela/cli.py:43` | The CLI rejects a byte order mark that the web accepts. | DD-028 |
| 12 | Low | `ela/api.py:127`, `:133` | Filesystem failures give plain-text 500. | DD-028 |
| 13 | Low | `ela/engine.py:252` | No mesh warning on a paralleled island. | Fix per DD-004's wording, overriding the narrower reading in L2-ENG-025 |
| 14 | Low | `ela/batch.py:79` | Formula injection in CSV. | DD-034 |
| 15 | Low | `ela/cli.py:73` | No scenarios gives exit 0 silently. | DD-028 |
| 16 | Low | `ela/api.py:93` | `é.json` becomes stem `_`, then a confusing 409. | Fix: a stem of only underscores is rejected with 422 and a clear message |

## Surviving injected faults

7 of 72 survived. Each needs a test that fails on it.

| Fault | Behaviour | Test needed |
| --- | --- | --- |
| W01 | "5 s" shows Transient and vice versa | Pick each option by visible label and assert that band's value |
| W03 | Bus current always shows continuous | Assert amps for all three bands |
| W13 | A stale definition open wins | Hold the first GET, open a second definition, release, assert the second is shown |
| F22 | Generators ordered by id, not engine number | Engine numbers against id order |
| S02 | A contactor needs both ends live | A closed contactor to a failed generator on a live bus is energised |
| S11 | Spanning-tree root is the highest id | Multi-source meshed island with exact flows on each tie |
| S25 | All DC buses share the main row | Assert main above essential above emergency or battery by `y` |

## Weak tests

- `tests/test_system.py:177`, `:385`, `:509` assert arithmetic only.
- `tests/test_web_interactive.py:895` takes its expected verdict from `run_batch`.
- `tests/test_acceptance.py:32` allows 1 W of error against hand figures.
- `returncode in (0, 1)` at `tests/test_acceptance.py:39`, `:79`, `:237` and `tests/test_system.py:161`, `:874`.

## Corrections to documents

- `README.md:302`: "Totals per bus and source are not affected" is false for bus throughput.
- `README.md:118`: omits two batteries sharing under DD-006.
- README omissions: UTF-8, `<bus>_switch` reserved, TRU contactors in steps 5 and 6, upload names sanitised, long bus names truncated.
- `ela/layout.py:15`: "never shares a line" is wrong. Add a property test that any shared segment ends on one node.
- TC-WIN-014: say that a real mouse cannot produce the pan-then-hit path, so the case uses synthetic events.
- TC-CLI-002: one `meshed_island` line plus the DD-025 warning.

## Accepted limitations

- The hand-calculation and audit oracles were both written after reading the engine. Only a reviewer who has not seen the code can close this.
- One random topology in 800 lays out with two connectors sharing 3 px on one bus.
- Squash commit `942195d` lacks the commit trailers. Its PR records them.
