"""Generate docs/traceability.md: one row per requirement, from the documents and the tests.

Reads docs/requirements.md (requirements, their level, component and section), the verification
matrix in docs/test-cases.md (which cases verify which requirements), the tests' own
`@pytest.mark.tc(...)` marks (parsed, not run) and docs/issues.json (issue numbers).

An L0 requirement belongs to the acceptance issue, an L1 requirement to the system verification
issue, and an L2 requirement to the issue of its section. A requirement verified by Inspection
shows its automated case like any other.

Usage:  python tools/trace_report.py          write docs/traceability.md
        python tools/trace_report.py --check  exit 1 if the committed file is out of date
"""

import ast
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REQUIREMENTS = ROOT / "docs" / "requirements.md"
TEST_CASES = ROOT / "docs" / "test-cases.md"
ISSUES = ROOT / "docs" / "issues.json"
TESTS = ROOT / "tests"
OUTPUT = ROOT / "docs" / "traceability.md"

LEVEL_ISSUE = {"L0": "ACC", "L1": "SYS"}


def parse_requirements():
    """Requirement records in file order: id, level, component, method and section."""
    text = REQUIREMENTS.read_text("utf-8")
    records = []
    for section in re.finditer(
        r"<!-- BEGIN SECTION (\S+) -->(.*?)<!-- END SECTION \1 -->", text, re.DOTALL
    ):
        name = section.group(1)
        if name == "ASSUMPTIONS":
            continue
        for block in re.findall(r"```req\n(.*?)```", section.group(2), re.DOTALL):
            fields, key = {}, None
            for line in block.splitlines():
                if line[:1] in " \t" and key:
                    fields[key] += " " + line.strip()
                elif ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()
            records.append(
                {
                    "id": fields["ID"],
                    "level": fields["Level"],
                    "component": fields["Allocated to"],
                    "method": re.split(r"[;,]", fields["Verification"])[0].strip(),
                    "section": name,
                }
            )
    return records


def parse_matrix():
    """Requirement id to the case ids that verify it, from the verification matrix."""
    text = TEST_CASES.read_text("utf-8")
    cases = {}
    for case, verifies in re.findall(r"^\| (TC-[A-Z]+-\d+) \| ([^|]*) \|", text, re.MULTILINE):
        cases[case] = re.findall(r"L\d-[A-Z]+-\d+", verifies)
    by_requirement = defaultdict(list)
    for case, requirements in cases.items():
        for requirement in requirements:
            by_requirement[requirement].append(case)
    return cases, by_requirement


def _tc_ids(decorator):
    """Case ids of a decorator `pytest.mark.tc("TC-...", ...)`, else an empty list."""
    if (
        isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and decorator.func.attr == "tc"
        and isinstance(decorator.func.value, ast.Attribute)
        and decorator.func.value.attr == "mark"
    ):
        return [a.value for a in decorator.args if isinstance(a, ast.Constant)]
    return []


def parse_test_marks():
    """Case id to the set of test functions (`file::name`) that carry its mark."""
    marked = defaultdict(set)
    for path in sorted(TESTS.rglob("test_*.py")):
        for node in ast.walk(ast.parse(path.read_text("utf-8"))):
            if isinstance(node, ast.FunctionDef) and node.name.startswith("test"):
                for decorator in node.decorator_list:
                    for case in _tc_ids(decorator):
                        marked[case].add(f"{path.name}::{node.name}")
    return marked


def issue_number(record, issues):
    key = LEVEL_ISSUE.get(record["level"], record["section"])
    return issues["sections"][key]["number"]


def build_rows():
    records = parse_requirements()
    cases, by_requirement = parse_matrix()
    marked = parse_test_marks()
    issues = json.loads(ISSUES.read_text("utf-8"))
    rows = []
    for record in records:
        verifying = sorted(by_requirement.get(record["id"], []))
        tests = set()
        for case in verifying:
            tests |= marked.get(case, set())
        rows.append({**record, "cases": verifying, "tests": len(tests),
                     "issue": issue_number(record, issues)})
    return rows, cases, marked


def render():
    """The whole document as text."""
    rows, cases, marked = build_rows()
    levels = Counter(r["level"] for r in rows)
    methods = Counter(r["method"] for r in rows)
    with_case = sum(1 for r in rows if r["cases"])
    with_test = sum(1 for r in rows if r["tests"])
    functions = set().union(*marked.values()) if marked else set()
    cases_with_test = sum(1 for c in cases if marked.get(c))

    lines = [
        "# Traceability",
        "",
        (
            "Generated by `tools/trace_report.py` from `docs/requirements.md`, the verification "
            "matrix in `docs/test-cases.md`, the `@pytest.mark.tc` marks in `tests/` and "
            "`docs/issues.json`. Do not edit by hand. Run `uv run python tools/trace_report.py` "
            "to regenerate it. A test fails if this file is out of date."
        ),
        "",
        "## Summary",
        "",
        "| Measure | Count |",
        "| --- | --- |",
        f"| Requirements | {len(rows)} |",
        *(f"| {level} requirements | {levels[level]} |" for level in sorted(levels)),
        *(f"| Verified by {method} | {methods[method]} |" for method in sorted(methods)),
        f"| Requirements with a verifying case | {with_case} |",
        f"| Requirements with no verifying case | {len(rows) - with_case} |",
        f"| Requirements with at least one test | {with_test} |",
        f"| Requirements with no test | {len(rows) - with_test} |",
        f"| Test cases | {len(cases)} |",
        f"| Test cases with at least one test | {cases_with_test} |",
        f"| Test cases with no test | {len(cases) - cases_with_test} |",
        f"| Test functions carrying a case mark | {len(functions)} |",
        "",
        (
            "Test count is the number of distinct test functions that carry the mark of any case "
            "verifying the requirement. A parametrized test counts once. A requirement verified "
            "by Inspection shows its automated case and tests like any other."
        ),
        "",
        "## Requirements",
        "",
        "| ID | Level | Component | Verifying cases | Tests | Issue |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in rows:
        cases_text = ", ".join(r["cases"]) or "none"
        lines.append(
            f"| {r['id']} | {r['level']} | {r['component']} | {cases_text} | {r['tests']} "
            f"| #{r['issue']} |"
        )
    return "\n".join(lines) + "\n"


def main(argv=None):
    argv = sys.argv[1:] if argv is None else argv
    text = render()
    if "--check" in argv:
        current = OUTPUT.read_text("utf-8") if OUTPUT.exists() else ""
        if current.replace("\r\n", "\n") != text:
            print("docs/traceability.md is out of date: run tools/trace_report.py", file=sys.stderr)
            return 1
        return 0
    with open(OUTPUT, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)
    print(f"wrote {OUTPUT.relative_to(ROOT)}: {len(text.splitlines())} lines")
    return 0


if __name__ == "__main__":
    sys.exit(main())
