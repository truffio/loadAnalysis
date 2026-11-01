# Example definitions

Ten fictional aircraft for the ELA tool, one file each. **All figures are illustrative. None comes from any real aircraft, and no file describes a real type.** Each `meta.description` states the architecture.

| File | Aircraft class | Sources | Buses | TRUs | Loads | Scenarios | Passes | Designed failures | Tightest margin |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `regional_turboprop.json` | 2-engine regional turboprop | 3 | 7 | 2 | 46 | 11 | 7 | 4 (2 O, 1 P, 1 U) | 16.01 % (GEN2, transient, S03) |
| `regional_jet.json` | 2-engine regional jet | 5 | 7 | 3 | 51 | 15 | 12 | 3 (1 O, 1 P, 1 U) | 6.35 % (APUGEN, transient, S06) |
| `narrowbody_twin.json` | Single-aisle twin | 5 | 9 | 3 | 57 | 14 | 11 | 3 (1 O, 1 P, 1 U) | 11.69 % (GAL2, continuous, S01) |
| `widebody_twin.json` | Long-haul twin | 6 | 10 | 4 | 59 | 15 | 11 | 4 (2 O, 1 P, 1 U) | 9.42 % (APUGEN, transient, S06) |
| `trijet_freighter.json` | 3-engine freighter | 5 | 9 | 3 | 57 | 13 | 10 | 3 (1 O, 1 P, 1 U) | 5.96 % (GEN2, transient, S04) |
| `quad_airliner.json` | 4-engine airliner | 7 | 9 | 4 | 60 | 15 | 11 | 4 (2 O, 1 P, 1 U) | 23.42 % (RAT_AC, transient, S10) |
| `military_transport.json` | 4-engine turboprop transport | 6 | 10 | 3 | 57 | 15 | 11 | 4 (2 O, 1 P, 1 U) | 4.30 % (TRU2, continuous, S09) |
| `heavy_eight_engine.json` | 8-engine heavy transport | 9 | 12 | 4 | 59 | 15 | 12 | 3 (1 O, 1 P, 1 U) | 7.22 % (TRU2, transient, S10) |
| `business_jet.json` | Long-range business jet | 6 | 9 | 3 | 49 | 14 | 11 | 3 (1 O, 1 P, 1 U) | 16.01 % (RAT_AC, transient, S09) |
| `twin_helicopter.json` | Twin-engine utility helicopter | 3 | 8 | 2 | 42 | 10 | 6 | 4 (2 O, 1 P, 1 U) | 9.36 % (GEN2, transient, S04) |

- **Sources** counts generators, RAT outputs and batteries.
- **Designed failures** are the scenarios meant to fail: O overload, P AC sources paralleled, U unpowered essential load.
- **Tightest margin** is the smallest remaining margin over the passing scenarios, with its element, band and scenario.

The default state of every file passes. A failing scenario says so in its description. Run a file with `uv run ela batch definitions/<file>`. It exits with 1 because each file holds designed failures.
