"""Batch runner and export (docs/spec.md §6.3).

`run_batch` analyses every scenario of a validated definition with `ela.engine.analyse` and
condenses each result. It does no analysis of its own and imports nothing web-related.
"""

import csv
import io
import json
from dataclasses import asdict

from ela.engine import analyse
from ela.format import format_pct

# The nine summary fields, in column order (L2-BAT-003). The CSV and the CLI use this order.
SUMMARY_FIELDS = (
    "scenario_id",
    "name",
    "result",
    "worst_element",
    "worst_band",
    "smallest_margin_pct",
    "overloads",
    "configuration_errors",
    "unpowered_essential",
)
DETAIL_FIELDS = ("overload_details", "error_messages", "unpowered_details", "warnings")


def run_batch(defn) -> list[dict]:
    """Run every scenario of a validated definition, each from default states, in file order.

    Each result is a dict holding the nine SUMMARY_FIELDS and the DETAIL_FIELDS. `result` is
    "PASS" or "FAIL". `worst_element`, `worst_band` and `smallest_margin_pct` are None when
    nothing was checked. `overloads` counts element-band entries. The detail lists hold plain
    dicts: `overload_details` (element, band, demand_with_margin, capacity), `unpowered_details`
    (id, name, bus), `warnings` (code, element, message), and `error_messages` holds strings.
    """
    results = []
    for scenario in defn.scenarios:
        r = analyse(defn, dict(scenario.states))
        results.append(
            {
                "scenario_id": scenario.id,
                "name": scenario.name,
                "result": r.verdict,
                "worst_element": r.worst.element,
                "worst_band": r.worst.band,
                "smallest_margin_pct": r.worst.margin_pct,
                "overloads": len(r.overloads),
                "configuration_errors": len(r.config_errors),
                "unpowered_essential": len(r.unpowered),
                "overload_details": [asdict(o) for o in r.overloads],
                "error_messages": list(r.config_errors),
                "unpowered_details": [asdict(u) for u in r.unpowered],
                "warnings": [asdict(w) for w in r.warnings],
            }
        )
    return results


def summary_cells(result: dict) -> list[str]:
    """The nine summary fields of one result as display text, with "" for a null value."""
    cells = []
    for name in SUMMARY_FIELDS:
        value = result[name]
        if value is None:
            cells.append("")
        elif name == "smallest_margin_pct":
            cells.append(format_pct(value))
        else:
            cells.append(str(value))
    return cells


def to_csv(results: list[dict]) -> str:
    """One header row and one row per scenario. A null is an empty cell, the margin has at most
    2 decimals (rounded half up), and records end in "\\n"."""
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(SUMMARY_FIELDS)
    for result in results:
        writer.writerow(summary_cells(result))
    return out.getvalue()


def to_json(results: list[dict]) -> str:
    """A JSON array with every field of every result at full precision and None as null."""
    return json.dumps(results, indent=2, ensure_ascii=False) + "\n"


def write_csv(path, results: list[dict]) -> None:
    """Write `to_csv(results)` to `path` as UTF-8."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_csv(results))


def write_json(path, results: list[dict]) -> None:
    """Write `to_json(results)` to `path` as UTF-8."""
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write(to_json(results))
