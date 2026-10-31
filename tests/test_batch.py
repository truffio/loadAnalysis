"""C-BATCH cases from docs/test-cases.md.

Expected figures are the hand-worked FX-BATCH table in the case text.
"""

import copy
import csv
import io
import json
import subprocess
import sys
from pathlib import Path

import pytest
from conftest import fx

import ela.batch
from ela.batch import SUMMARY_FIELDS, run_batch, to_csv, to_json, write_csv, write_json
from ela.engine import analyse
from ela.format import format_pct
from ela.validate import validate

ROOT = Path(__file__).resolve().parent.parent

# FX-BATCH hand results: result, worst_element, worst_band, margin, overloads, configuration_errors,
# unpowered_essential. The margin is exact where the case text gives a fraction.
TABLE = {
    "S1": ("PASS", "G1", "continuous", 56.0, 0, 0, 0),
    "S2": ("PASS", "G2", "continuous", 12.0, 0, 0, 0),
    "S3": ("FAIL", None, None, None, 0, 1, 0),
    "S4": ("FAIL", None, None, None, 0, 0, 1),
    "S5": ("FAIL", "T13", "transient", -700 / 1500 * 100, 3, 0, 0),
}
NAMES = {
    "S1": "Normal",
    "S2": "G1 lost",
    "S3": "Paralleled",
    "S4": "Dark",
    "S5": 'Overload, tie to "AC3" — T13',
}


def batch(doc):
    result = validate(doc)
    assert result.errors == []
    return run_batch(result.definition)


def by_id(results):
    return {r["scenario_id"]: r for r in results}


def csv_rows(text):
    return list(csv.reader(io.StringIO(text, newline="")))


@pytest.mark.tc("TC-BAT-001")
def test_one_result_per_scenario_in_file_order():
    results = batch(fx("FX-BATCH12"))
    assert [r["scenario_id"] for r in results] == [
        "Z01", "A02", "M03", "B04", "Y05", "C06", "X07", "D08", "W09", "E10", "V11", "F12"
    ]  # fmt: skip


@pytest.mark.tc("TC-BAT-002")
def test_scenarios_are_independent():
    doc = fx("FX-BATCH")
    forward = by_id(batch(doc))
    doc["scenarios"].reverse()
    backward = by_id(batch(doc))
    assert forward == backward
    # G1 failed in S2 does not carry into S3, where G1 stays live and the island is paralleled.
    assert "AC sources paralleled" in forward["S3"]["error_messages"][0]
    assert forward["S1"]["unpowered_essential"] == 0


@pytest.mark.tc("TC-BAT-003")
def test_summary_fields_match_the_hand_table():
    results = by_id(batch(fx("FX-BATCH")))
    assert list(results) == list(TABLE)
    for sid, (verdict, element, band, margin, overloads, errors, unpowered) in TABLE.items():
        r = results[sid]
        assert r["scenario_id"] == sid
        assert r["name"] == NAMES[sid]
        assert r["result"] == verdict
        assert r["worst_element"] == element
        assert r["worst_band"] == band
        if margin is None:
            assert r["smallest_margin_pct"] is None
        else:
            assert r["smallest_margin_pct"] == pytest.approx(margin, abs=1e-6)
        assert r["overloads"] == overloads
        assert r["configuration_errors"] == errors
        assert r["unpowered_essential"] == unpowered
    assert format_pct(results["S5"]["smallest_margin_pct"]) == "-46.67"
    assert format_pct(results["S1"]["smallest_margin_pct"]) == "56"


@pytest.mark.tc("TC-BAT-004")
def test_detail_lists():
    results = by_id(batch(fx("FX-BATCH")))
    s5 = results["S5"]["overload_details"]
    assert len(s5) == 3
    assert {(o["element"], o["band"]) for o in s5} == {
        ("G1", "transient"),
        ("G1", "continuous"),
        ("T13", "transient"),
    }
    t13 = next(o for o in s5 if o["element"] == "T13")
    assert t13["demand_with_margin"] == pytest.approx(2200, abs=1e-6)
    assert t13["capacity"] == 1500
    s3 = results["S3"]["error_messages"]
    assert len(s3) == 1 and "AC sources paralleled" in s3[0]
    s4 = results["S4"]["unpowered_details"]
    assert [u["id"] for u in s4] == ["LA1"]
    s1 = results["S1"]
    assert (s1["overload_details"], s1["error_messages"]) == ([], [])
    assert (s1["unpowered_details"], s1["warnings"]) == ([], [])

    ring = batch(fx("FX-RING"))
    meshed = [w for w in ring[0]["warnings"] if w["code"] == "meshed_island"]
    assert len(meshed) == 1 and "T23" in meshed[0]["element"] + meshed[0]["message"]


@pytest.mark.tc("TC-BAT-005")
def test_batch_uses_the_engine_result(monkeypatch):
    doc = fx("FX-BATCH")
    defn = validate(doc).definition
    results = run_batch(defn)
    for scenario, r in zip(defn.scenarios, results, strict=True):
        direct = analyse(defn, dict(scenario.states))
        assert r["result"] == direct.verdict
        assert r["overloads"] == len(direct.overloads)
        assert [(o["element"], o["band"]) for o in r["overload_details"]] == [
            (o.element, o.band) for o in direct.overloads
        ]
        assert r["worst_element"] == direct.worst.element

    calls = []

    def spy(d, states):
        calls.append(copy.deepcopy(states))
        return analyse(d, states)

    monkeypatch.setattr(ela.batch, "analyse", spy)
    run_batch(defn)
    assert calls == [dict(s.states) for s in defn.scenarios]


@pytest.mark.tc("TC-BAT-006")
def test_batch_has_no_web_dependency():
    assert (ROOT / "ela" / "batch.py").exists()
    code = (
        "import sys, ela.batch; "
        "print([m for m in ('fastapi', 'starlette', 'uvicorn') if m in sys.modules])"
    )
    out = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, capture_output=True, text=True, check=True
    )
    assert out.stdout.strip() == "[]"


@pytest.mark.tc("TC-BAT-011")
def test_run_batch_entry_point_and_fields():
    doc = fx("FX-BATCH")
    doc["scenarios"] = doc["scenarios"][:1]
    results = batch(doc)
    assert len(results) == 1
    assert set(results[0]) == {
        "scenario_id", "name", "result", "worst_element", "worst_band", "smallest_margin_pct",
        "overloads", "configuration_errors", "unpowered_essential", "overload_details",
        "error_messages", "unpowered_details", "warnings",
    }  # fmt: skip


@pytest.mark.tc("TC-BAT-007")
def test_csv_shape():
    rows = csv_rows(to_csv(batch(fx("FX-BATCH12"))))
    assert len(rows) == 13
    assert rows[0] == [
        "scenario_id", "name", "result", "worst_element", "worst_band", "smallest_margin_pct",
        "overloads", "configuration_errors", "unpowered_essential",
    ]  # fmt: skip
    assert tuple(rows[0]) == SUMMARY_FIELDS
    assert all(len(row) == 9 for row in rows)


@pytest.mark.tc("TC-BAT-008")
def test_csv_keeps_commas_quotes_and_non_ascii(tmp_path):
    results = batch(fx("FX-BATCH"))
    path = tmp_path / "out.csv"
    path.write_bytes(to_csv(results).encode("utf-8"))
    with open(path, encoding="utf-8", newline="") as f:
        rows = list(csv.reader(f))
    assert len(rows) == 6  # header and 5 records, no blank rows
    s5 = rows[5]
    assert len(s5) == 9
    assert s5[1] == 'Overload, tie to "AC3" — T13'
    assert s5[5].startswith("-") and s5[5] == "-46.67"
    assert "−" not in path.read_text("utf-8")


@pytest.mark.tc("TC-BAT-009")
def test_json_holds_every_field_and_detail():
    results = batch(fx("FX-BATCH"))
    parsed = json.loads(to_json(results))
    assert [r["scenario_id"] for r in parsed] == list(TABLE)
    for r in parsed:
        verdict, element, band, margin, overloads, errors, unpowered = TABLE[r["scenario_id"]]
        assert r["name"] == NAMES[r["scenario_id"]]
        assert (r["result"], r["worst_element"], r["worst_band"]) == (verdict, element, band)
        assert (r["overloads"], r["configuration_errors"], r["unpowered_essential"]) == (
            overloads,
            errors,
            unpowered,
        )
        for key in ("overload_details", "error_messages", "unpowered_details", "warnings"):
            assert isinstance(r[key], list)
        assert len(r["overload_details"]) == overloads
        assert len(r["error_messages"]) == errors
        assert len(r["unpowered_details"]) == unpowered
        if margin is not None:
            assert r["smallest_margin_pct"] == pytest.approx(margin, abs=1e-6)
    s5 = parsed[4]["smallest_margin_pct"]
    assert isinstance(s5, float) and s5 == results[4]["smallest_margin_pct"]  # full precision
    assert "−" not in to_json(results)


@pytest.mark.tc("TC-BAT-010")
def test_null_worst_values_in_exports(tmp_path):
    results = batch(fx("FX-BATCH"))
    rows = {row[0]: row for row in csv_rows(to_csv(results))[1:]}
    parsed = by_id(json.loads(to_json(results)))
    for sid in ("S3", "S4"):
        assert rows[sid][3:6] == ["", "", ""]
        r = parsed[sid]
        assert (r["worst_element"], r["worst_band"], r["smallest_margin_pct"]) == (None,) * 3
    # The file writers produce the same text as the serialisers.
    write_csv(tmp_path / "a.csv", results)
    write_json(tmp_path / "a.json", results)
    assert (tmp_path / "a.csv").read_bytes().decode("utf-8") == to_csv(results)
    assert (tmp_path / "a.json").read_bytes().decode("utf-8") == to_json(results)


@pytest.mark.tc("TC-CLI-002")
@pytest.mark.parametrize(
    ("value", "text"),
    [
        (76.625, "76.63"),  # round() and :.2f give 76.62
        (76.62499, "76.62"),
        (-46.666666667, "-46.67"),
        (-0.004, "0"),
        (12.0, "12"),
        (56, "56"),
        (0.1, "0.1"),
        (1e-7, "0"),
        (-2.675, "-2.68"),
        (None, "—"),
    ],
)
def test_format_pct_rounds_half_up_with_ascii_minus(value, text):
    assert format_pct(value) == text
