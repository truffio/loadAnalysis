"""Command line: `ela batch <definition>` (docs/spec.md §6.3, DD-018).

Exit codes: 0 every scenario passes, 1 at least one fails, 2 invalid definition or bad usage.
Standard output holds one tab-separated line per scenario. Everything else goes to standard error.
"""

import argparse
import json
import sys

from ela.batch import run_batch, summary_cells, write_csv, write_json
from ela.format import NULL_TEXT
from ela.validate import validate

EXIT_PASS, EXIT_FAIL, EXIT_INVALID = 0, 1, 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ela", description="Electrical load analysis tool.")
    commands = parser.add_subparsers(dest="command", required=True, metavar="{batch}")
    batch = commands.add_parser("batch", help="run every scenario of a definition file")
    batch.add_argument("path", help="definition file (JSON)")
    batch.add_argument("--csv", metavar="PATH", help="write the results as CSV")
    batch.add_argument("--json", metavar="PATH", help="write the results as JSON")
    return parser


def _one_line(text) -> str:
    return " ".join(str(text).split())


def _error(message) -> int:
    print(f"ela: {_one_line(message)}", file=sys.stderr)
    return EXIT_INVALID


def _cell(text: str) -> str:
    return _one_line(text) if text else NULL_TEXT


def _batch(args) -> int:
    try:
        with open(args.path, encoding="utf-8") as f:
            doc = json.load(f)
    except OSError as exc:
        return _error(f"cannot read {args.path}: {exc.strerror or exc}")
    except (ValueError, RecursionError) as exc:  # bad UTF-8 and bad JSON are both ValueError
        return _error(f"{args.path} is not valid JSON: {exc}")

    validation = validate(doc)
    if validation.errors:
        for issue in validation.errors:
            print(f"{issue.path}: {_one_line(issue.message)}", file=sys.stderr)
        return EXIT_INVALID
    for issue in validation.warnings:
        print(f"warning: {issue.path}: {_one_line(issue.message)}", file=sys.stderr)

    results = run_batch(validation.definition)
    for result in results:
        print("\t".join(_cell(c) for c in summary_cells(result)))
        for w in result["warnings"]:
            print(
                f"warning: {result['scenario_id']}: {w['code']}: {_one_line(w['message'])}",
                file=sys.stderr,
            )
    try:
        if args.csv:
            write_csv(args.csv, results)
        if args.json:
            write_json(args.json, results)
    except OSError as exc:
        return _error(f"cannot write export: {exc.strerror or exc}")
    return EXIT_FAIL if any(r["result"] != "PASS" for r in results) else EXIT_PASS


def main(argv=None) -> int:
    """Run the CLI and return the exit code."""
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="backslashreplace")
    try:
        args = _parser().parse_args(argv)
    except SystemExit as exc:  # argparse: 0 for --help, 2 for bad usage
        return exc.code if isinstance(exc.code, int) else EXIT_INVALID
    return _batch(args)
