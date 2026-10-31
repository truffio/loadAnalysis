"""Create the GitHub epics and implementation issues from docs/requirements.md.

One epic issue per delivery epic, and one sub-issue per L2 section. Requirement and
test case lists are read from the documents, so the issues match the baseline.

Usage:  python tools/create_issues.py [--dry-run]
Output: docs/issues.json, mapping epics and sections to issue numbers.
"""

import json
import re
import subprocess
import sys
import time
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
REPO = "truffio/loadAnalysis"

EPICS = [
    ("E1", "Definition schema and validation", ["MOD", "VAL"], "C-MODEL, C-VALID",
     "Load a JSON definition and return every error at once with its path."),
    ("E2", "Analysis engine", ["ENG"], "C-ENGINE",
     "Energisation, demand, flow, source rules and capacity checks, as a pure package."),
    ("E3", "Sample definition", ["SMP"], "C-SAMPLE",
     "A generic twin definition with hand-calculated expected results."),
    ("E4", "Batch runner and CLI", ["BAT", "CLI"], "C-BATCH, C-CLI",
     "Run every scenario, export the results and give a usable exit code."),
    ("E5", "Schematic layout", ["LAY"], "C-LAYOUT",
     "Compute a layered, readable schematic with no coordinates in the definition."),
    ("E6", "HTTP API", ["API"], "C-API",
     "Serve definitions, analysis, batch runs and the static front end."),
    ("E7", "Interactive front end", ["WIN"], "C-WEBINT",
     "Draw the schematic and recompute on every click."),
    ("E8", "Batch front end", ["WBT"], "C-WEBBAT",
     "Show batch results, drill down, open a scenario and export."),
    ("E9", "Documentation and system verification", ["DOC"], "C-DOCS",
     "README, plus the L1 and L0 test cases and the final trace."),
]

LABELS = {
    "epic": ("5319e7", "Delivery epic with allocated requirements"),
    "implementation": ("0e8a16", "Implements one L2 requirement section"),
    "verification": ("1d76db", "System and acceptance verification"),
    **{f"comp:{p.lower()}": ("c5def5", f"Requirements with prefix {p}")
       for e in EPICS for p in e[2]},
}


def parse_requirements():
    text = (ROOT / "docs/requirements.md").read_text(encoding="utf-8")
    sections, records = {}, {}
    for m in re.finditer(r"<!-- BEGIN SECTION (\S+) -->(.*?)<!-- END SECTION \1 -->", text, re.DOTALL):
        ids = []
        for block in re.findall(r"```req\n(.*?)```", m.group(2), re.DOTALL):
            fields, key = {}, None
            for line in block.splitlines():
                if line[:1] in " \t" and key:
                    fields[key] += " " + line.strip()
                elif ":" in line:
                    key, value = line.split(":", 1)
                    fields[key.strip()] = value.strip()
            records[fields["ID"]] = fields
            ids.append(fields["ID"])
        sections[m.group(1)] = ids
    return sections, records


def parse_tests():
    text = (ROOT / "docs/test-cases.md").read_text(encoding="utf-8")
    by_req = defaultdict(list)
    all_cases = {}
    for m in re.finditer(r"^\| (TC-[A-Z]+-\d+) \| ([^|]+) \| (L\d) \| (\w+) \|", text, re.MULTILINE):
        all_cases[m.group(1)] = re.findall(r"L\d-[A-Z]+-\d+", m.group(2))
        for req in all_cases[m.group(1)]:
            by_req[req].append(m.group(1))
    return by_req, all_cases


def gh(*args, stdin=None):
    done = subprocess.run(["gh", *args], input=stdin, capture_output=True, text=True,
                          encoding="utf-8", check=False)
    if done.returncode:
        raise RuntimeError(f"gh {' '.join(args[:4])}: {done.stderr}")
    return done.stdout


def create_issue(title, body, labels, dry):
    if dry:
        print(f"[dry] {title} ({len(body)} chars)")
        return {"number": 0, "node_id": "dry"}
    payload = json.dumps({"title": title, "body": body, "labels": labels})
    out = json.loads(gh("api", f"repos/{REPO}/issues", "--input", "-", stdin=payload))
    time.sleep(1.2)
    return {"number": out["number"], "node_id": out["node_id"]}


def add_sub_issue(parent, child, dry):
    if dry:
        return
    gh("api", "graphql", "-f",
       "query=mutation($p:ID!,$c:ID!){addSubIssue(input:{issueId:$p,subIssueId:$c})"
       "{issue{number}}}", "-F", f"p={parent}", "-F", f"c={child}")
    time.sleep(0.3)


def section_title(name):
    prefix, _, rest = name.partition("-")
    return f"{prefix}: {rest.replace('-', ' ').replace('_', ' ').lower()}"


def section_body(name, ids, records, tests, epic):
    lines = [f"**Epic:** {epic}", f"**Section:** `{name}` in `docs/requirements.md`",
             f"**Component:** {records[ids[0]]['Allocated to']}", "", "## Requirements", ""]
    for rid in ids:
        lines.append(f"- [ ] **{rid}**: {records[rid]['Statement']}")
    cases = sorted({c for rid in ids for c in tests.get(rid, [])})
    lines += ["", "## Test cases", "", ", ".join(cases) or "None", "", "## Done when", "",
              ("Every requirement above is implemented, and each listed test case has a passing "
              '`@pytest.mark.tc("...")` test.')]
    return "\n".join(lines)


def main():
    dry = "--dry-run" in sys.argv
    sections, records = parse_requirements()
    tests, all_cases = parse_tests()

    if not dry:
        for name, (color, desc) in LABELS.items():
            gh("label", "create", name, "-R", REPO, "--color", color, "--description", desc,
               "--force")

    result = {"epics": {}, "sections": {}}
    used = set()
    for code, title, prefixes, comps, goal in EPICS:
        names = [n for n in sections if n.split("-")[0] in prefixes]
        used.update(names)
        l2 = [rid for n in names for rid in sections[n]]
        parents = sorted({p for rid in l2
                          for p in re.findall(r"L1-ELA-\d+", records[rid]["Parent(s)"])})
        grand = sorted({p for rid in parents
                        for p in re.findall(r"L0-ELA-\d+", records[rid]["Parent(s)"])})
        body = [f"**Goal:** {goal}", f"**Components:** {comps}", "",
                f"**Allocated L2 requirements:** {len(l2)} in {len(names)} sections",
                f"**Satisfies L1:** {', '.join(parents) or 'None'}",
                f"**Traces to L0:** {', '.join(grand) or 'None'}", "",
                ("Requirements are in `docs/requirements.md` and test cases in "
                "`docs/test-cases.md`. Work is tracked in the sub-issues.")]
        epic = create_issue(f"[{code}] {title}", "\n".join(body), ["epic"], dry)
        result["epics"][code] = {**epic, "prefixes": prefixes}

        for name in names:
            label = f"comp:{name.split('-')[0].lower()}"
            issue = create_issue(f"[{code}] {section_title(name)}",
                                 section_body(name, sections[name], records, tests, f"{code}"),
                                 ["implementation", label], dry)
            add_sub_issue(epic["node_id"], issue["node_id"], dry)
            result["sections"][name] = {**issue, "epic": code}

        if code == "E9":
            for prefix, heading in (("SYS", "L1 system verification"),
                                    ("ACC", "L0 acceptance verification")):
                cases = sorted(c for c in all_cases if c.startswith(f"TC-{prefix}-"))
                reqs = sorted({r for c in cases for r in all_cases[c]})
                text = "\n".join([f"**Epic:** {code}", "", f"**Requirements:** {', '.join(reqs)}",
                                  "", f"**Test cases:** {', '.join(cases)}"])
                issue = create_issue(f"[{code}] {heading}", text, ["verification"], dry)
                add_sub_issue(epic["node_id"], issue["node_id"], dry)
                result["sections"][prefix] = {**issue, "epic": code}

    upper = {"L0", "L1", "ASSUMPTIONS"}
    missing = set(sections) - used - upper
    if missing:
        raise SystemExit(f"Sections with no epic: {sorted(missing)}")
    if not dry:
        (ROOT / "docs/issues.json").write_text(json.dumps(result, indent=2) + "\n",
                                               encoding="utf-8")
    print(f"{len(result['epics'])} epics, {len(result['sections'])} sub-issues")


if __name__ == "__main__":
    main()
