# Implementation plan

Baseline: `docs/spec.md` v1.0, with the rulings in `docs/decisions.md`.

## Process

The project follows a V-model. Each level on the way down has a matching verification level on the way up.

| Left side | Document | Right side | Evidence |
| --- | --- | --- | --- |
| L0 stakeholder requirements | `docs/requirements.md` | System validation | End-to-end sample tests |
| L1 system requirements | `docs/requirements.md` | System verification | CLI, API and browser tests |
| L2 component requirements | `docs/requirements.md` | Component verification | Unit tests, and browser tests for C-WEBINT and C-WEBBAT (DD-003) |

- Requirements are in one file, test cases in another (`docs/test-cases.md`).
- Both files follow the ReqViewer format, so `reqviewer --root .` renders the whole trace.
- Every test function carries `@pytest.mark.tc("TC-...")`. `tests/test_traceability.py` fails the suite if a requirement has no test case, a test case verifies nothing or has no test, or a test names an unknown case.
- Each L2 section in `docs/requirements.md` is one implementation issue. Issues are grouped under epics as native GitHub sub-issues.

## Components

| ID | Component | Files | Epic |
| --- | --- | --- | --- |
| C-MODEL | Definition schema | `ela/model.py` | E1 |
| C-VALID | Validator | `ela/validate.py` | E1 |
| C-ENGINE | Analysis engine | `ela/engine.py` | E2 |
| C-SAMPLE | Sample definition | `definitions/generic_twin.json` | E3 |
| C-BATCH | Batch runner and export | `ela/batch.py` | E4 |
| C-CLI | Command line | `ela/cli.py`, `ela/__main__.py` | E4 |
| C-LAYOUT | Schematic layout | `ela/layout.py` | E5 |
| C-API | HTTP API | `ela/api.py` | E6 |
| C-WEBINT | Interactive front end | `web/index.html`, `web/app.js`, `web/schematic.js`, `web/styles.css` | E7 |
| C-WEBBAT | Batch front end | `web/batch.js` | E8 |
| C-DOCS | User documentation | `README.md` | E9 |

## Delivery order

E1 → E2 → E3, E4, E5 → E6 → E7, E8 → E9. Each epic is one branch and one pull request, merged when the full test suite passes.

## Agent roster

| Role | Work | Model |
| --- | --- | --- |
| Systems engineer | Requirements | Opus |
| Verification engineer, independent of the requirements author | Test cases | Opus |
| Back-end engineer, analysis | E1, E2 | Opus |
| Electrical systems engineer | E3 sample and hand calculations | Opus |
| Application engineer | E4, E6 | Sonnet |
| Algorithm engineer | E5 layout | Opus |
| Front-end engineer | E7, E8 | Sonnet |
| Technical writer | E9 | Sonnet |
| Independent auditor | Final conformance review | Opus |
