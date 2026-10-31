"""Enforces the traceability rules in docs/plan.md.

Each epic adds its test case prefixes to IMPLEMENTED_PREFIXES. docs/test-cases.md has no case for
this harness itself. Its checks are the "map test marks to cases and cases to requirements" step of
TC-VAL-007, so they carry that mark.
"""

import ast
import re
import subprocess
import sys
from pathlib import Path

import pytest

pytestmark = pytest.mark.meta

# Test case prefixes built so far. The next epics append to this list.
IMPLEMENTED_PREFIXES = ["MOD", "VAL", "ENG", "SMP", "BAT", "CLI", "LAY", "API"]

# Cases of an implemented prefix that cannot run yet, with what they wait for. An entry must go as
# soon as a test carries that case. TC-ENG-013, TC-ENG-041 and TC-ENG-059 are not here: their tests
# run on the sample through `configurations()` in tests/test_engine.py. TC-LAY-017 has a browser
# half of its own for E7 to add.
DEFERRED_CASES = {
    "TC-LAY-018": "needs H-PAGE, which is the API (E6) and the front end (E7)",
}

ROOT = Path(__file__).resolve().parent.parent
TESTS = ROOT / "tests"
REQUIREMENTS = ROOT / "docs" / "requirements.md"
TEST_CASES = ROOT / "docs" / "test-cases.md"


def requirement_ids():
    return set(re.findall(r"^### (L\d-[A-Z]+-\d+)\s*$", REQUIREMENTS.read_text("utf-8"), re.MULTILINE))


def matrix():
    """Case id to the requirement ids it verifies, from the verification matrix."""
    rows = re.findall(r"^\| (TC-[A-Z]+-\d+) \| ([^|]*) \|", TEST_CASES.read_text("utf-8"), re.MULTILINE)
    return {case: re.findall(r"L\d-[A-Z]+-\d+", verifies) for case, verifies in rows}


def case_headings():
    return set(re.findall(r"^#### (TC-[A-Z]+-\d+) ", TEST_CASES.read_text("utf-8"), re.MULTILINE))


def _is_mark(node, name):
    """True for an expression `pytest.mark.<name>`."""
    return (
        isinstance(node, ast.Attribute)
        and node.attr == name
        and isinstance(node.value, ast.Attribute)
        and node.value.attr == "mark"
    )


def _is_meta_module(tree):
    for node in tree.body:
        if isinstance(node, ast.Assign) and any(
            isinstance(t, ast.Name) and t.id == "pytestmark" for t in node.targets
        ):
            return _is_mark(node.value, "meta")
    return False


def all_test_functions():
    """Every test function under tests/: (file name, function name, case ids, is meta)."""
    found = []
    for path in sorted(TESTS.rglob("test_*.py")):
        tree = ast.parse(path.read_text("utf-8"))
        module_meta = _is_meta_module(tree)
        for node in ast.walk(tree):
            if not isinstance(node, ast.FunctionDef) or not node.name.startswith("test"):
                continue
            cases, meta = [], module_meta
            for decorator in node.decorator_list:
                if isinstance(decorator, ast.Call) and _is_mark(decorator.func, "tc"):
                    cases += [a.value for a in decorator.args if isinstance(a, ast.Constant)]
                meta = meta or _is_mark(decorator, "meta")
            found.append((path.name, node.name, cases, meta))
    return found


def cases_with_tests():
    return {case for _, _, cases, _ in all_test_functions() for case in cases}


def collected_not_meta():
    """(file name, function name) of each test `pytest -m "not meta"` collects."""
    out = subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "--collect-only", "-q", "-m", "not meta"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    pairs = re.findall(r"^tests[/\\](?:.*[/\\])?(test_\w+\.py)::(\w+)", out.stdout, re.MULTILINE)
    return set(pairs)


def covered_requirements():
    """Requirement ids with at least one collected, non-meta test through a case."""
    collected = collected_not_meta()
    verifies = matrix()
    covered = set()
    for file, name, cases, _ in all_test_functions():
        if (file, name) in collected:
            for case in cases:
                covered.update(verifies.get(case, ()))
    return covered


@pytest.fixture(scope="module")
def not_meta_run():
    """One subprocess run of `pytest tests -m "not meta"`, shared by the cases that need it."""
    return subprocess.run(
        [sys.executable, "-m", "pytest", "tests", "-m", "not meta", "-q", "-p", "no:cacheprovider"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


@pytest.mark.tc("TC-VAL-007")
def test_matrix_and_case_headings_agree():
    assert set(matrix()) == case_headings()


@pytest.mark.tc("TC-VAL-007")
def test_every_requirement_has_a_case():
    verified = {r for reqs in matrix().values() for r in reqs}
    assert sorted(requirement_ids() - verified) == []


@pytest.mark.tc("TC-VAL-007")
def test_every_case_verifies_a_real_requirement():
    known = requirement_ids()
    for case, reqs in matrix().items():
        assert reqs, f"{case} verifies nothing"
        assert sorted(set(reqs) - known) == [], case


@pytest.mark.tc("TC-VAL-007")
def test_every_test_function_carries_a_mark():
    unmarked = [f"{file}::{name}" for file, name, cases, _ in all_test_functions() if not cases]
    assert unmarked == []


@pytest.mark.tc("TC-VAL-007")
def test_every_mark_names_a_real_case():
    assert sorted(cases_with_tests() - set(matrix())) == []


@pytest.mark.tc("TC-VAL-007")
def test_every_implemented_case_has_a_test():
    wanted = {c for c in matrix() if c.split("-")[1] in IMPLEMENTED_PREFIXES}
    assert sorted(wanted - cases_with_tests() - set(DEFERRED_CASES)) == []


@pytest.mark.tc("TC-VAL-007")
def test_deferred_cases_are_still_deferred():
    assert sorted(set(DEFERRED_CASES) & cases_with_tests()) == []
    assert sorted(set(DEFERRED_CASES) - set(matrix())) == []


@pytest.mark.tc("TC-VAL-007")
def test_every_validator_condition_has_a_passing_test(not_meta_run):
    conditions = {f"L2-VAL-{n:03d}" for n in [*range(7, 31), 32, 33]}
    assert sorted(conditions - covered_requirements()) == []
    assert not_meta_run.returncode == 0, not_meta_run.stdout[-2000:]


@pytest.mark.tc("TC-ENG-072")
def test_every_engine_topic_has_a_passing_test(not_meta_run):
    topics = {
        "energisation": {f"L2-ENG-{n:03d}" for n in range(3, 11)},
        "TRU efficiency": {"L2-ENG-016"},
        "bus ties": {"L2-ENG-017", "L2-ENG-021"},
        "source failures": {"L2-ENG-003", "L2-ENG-009"},
        "AC paralleling detection": {"L2-ENG-028"},
        "DC sharing": {"L2-ENG-033", "L2-ENG-034", "L2-ENG-038"},
        "battery priority": {"L2-ENG-035", "L2-ENG-036", "L2-ENG-037"},
        "safety margin": {"L2-ENG-041", "L2-ENG-043"},
        "crew switch": {"L2-ENG-002", "L2-ENG-013"},
    }
    covered = covered_requirements()
    assert [topic for topic, reqs in topics.items() if not reqs <= covered] == []
    assert not_meta_run.returncode == 0, not_meta_run.stdout[-2000:]
