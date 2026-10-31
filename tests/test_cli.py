"""C-CLI cases from docs/test-cases.md, run in subprocesses.

Expected figures are the hand-worked FX-BATCH table in the case text.
"""

import json
import subprocess
import sys
import tomllib
from pathlib import Path

import pytest
from conftest import fx, setp

from ela.batch import run_batch, to_csv, to_json
from ela.validate import validate

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = ROOT / "definitions" / "generic_twin.json"
SCRIPT = Path(sys.executable).with_name("ela.exe" if sys.platform == "win32" else "ela")

NO_SOCKET = """\
import runpy, socket, sys


class NoSocket(socket.socket):
    def connect(self, *a, **k):
        raise RuntimeError("connect attempted")

    def bind(self, *a, **k):
        raise RuntimeError("bind attempted")

    def listen(self, *a, **k):
        raise RuntimeError("listen attempted")


socket.socket = NoSocket
sys.argv = ["ela", *sys.argv[1:]]
runpy.run_module("ela", run_name="__main__", alter_sys=True)
"""


def run(args, command=None):
    """Run the CLI in a subprocess with UTF-8 output. `command` defaults to `python -m ela`."""
    command = command or [sys.executable, "-m", "ela"]
    return subprocess.run(
        [*map(str, command), *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        encoding="utf-8",
        check=False,
    )


def write(tmp_path, doc, name="defn.json"):
    path = tmp_path / name
    path.write_text(json.dumps(doc), encoding="utf-8")
    return path


def lines(text):
    return text.splitlines()


@pytest.mark.tc("TC-CLI-001")
def test_both_command_forms_give_identical_output():
    assert SCRIPT.exists(), SCRIPT
    module = run(["batch", SAMPLE])
    script = run(["batch", SAMPLE], command=[SCRIPT])
    assert module.stdout == script.stdout
    assert len(lines(module.stdout)) == 15
    assert module.returncode == script.returncode == 1


@pytest.mark.tc("TC-CLI-002")
def test_tab_separated_lines_and_warnings_on_stderr(tmp_path):
    out = run(["batch", write(tmp_path, fx("FX-BATCH"))])
    assert out.stderr == ""
    rows = [line.split("\t") for line in lines(out.stdout)]
    assert len(rows) == 5
    assert all(len(r) == 9 for r in rows)
    dash = "—"
    assert rows[0] == ["S1", "Normal", "PASS", "G1", "continuous", "56", "0", "0", "0"]
    assert rows[1] == ["S2", "G1 lost", "PASS", "G2", "continuous", "12", "0", "0", "0"]
    assert rows[2] == ["S3", "Paralleled", "FAIL", dash, dash, dash, "0", "1", "0"]
    assert rows[3] == ["S4", "Dark", "FAIL", dash, dash, dash, "0", "0", "1"]
    assert rows[4] == [
        "S5", 'Overload, tie to "AC3" — T13', "FAIL", "T13", "transient", "-46.67", "3", "0", "0"
    ]  # fmt: skip
    assert "−" not in out.stdout

    ring = run(["batch", write(tmp_path, fx("FX-RING"), "ring.json")])
    assert len(lines(ring.stdout)) == 1
    meshed = [line for line in lines(ring.stderr) if "meshed_island" in line]
    assert len(meshed) == 1 and "T23" in meshed[0]
    # The other stderr line is the definition's DD-025 warning, as FX-RING has no essential load.
    others = [line for line in lines(ring.stderr) if line not in meshed]
    assert all(line.startswith("warning: $.loads") for line in others)


@pytest.mark.tc("TC-CLI-003")
def test_export_options(tmp_path):
    path = write(tmp_path, fx("FX-BATCH"))
    out = run(["batch", path, "--csv", tmp_path / "out.csv", "--json", tmp_path / "out.json"])
    assert out.returncode == 1
    results = run_batch(validate(fx("FX-BATCH")).definition)
    assert (tmp_path / "out.csv").read_bytes().decode("utf-8") == to_csv(results)
    assert (tmp_path / "out.json").read_bytes().decode("utf-8") == to_json(results)
    assert json.loads((tmp_path / "out.json").read_text("utf-8"))[4]["worst_element"] == "T13"


@pytest.mark.tc("TC-CLI-004")
def test_cli_modules():
    assert (ROOT / "ela" / "cli.py").exists()
    assert (ROOT / "ela" / "__main__.py").exists()
    out = run(["--help"])
    assert out.returncode == 0
    assert "batch" in out.stdout


@pytest.mark.tc("TC-CLI-005")
def test_runs_with_no_server_and_opens_no_listening_port(tmp_path):
    wrapper = tmp_path / "no_socket.py"
    wrapper.write_text(NO_SOCKET, encoding="utf-8")
    path = write(tmp_path, fx("FX-BATCH"))
    out = run(["batch", path], command=[sys.executable, wrapper])
    assert out.returncode == 1, out.stderr
    assert len(lines(out.stdout)) == 5
    assert "attempted" not in out.stderr
    # The wrapper does fail a program that tries to bind.
    probe = subprocess.run(
        [sys.executable, "-c", NO_SOCKET.split("socket.socket = NoSocket")[0]
         + "socket.socket = NoSocket\nsocket.socket().bind(('127.0.0.1', 0))"],
        capture_output=True,
        text=True,
        check=False,
    )  # fmt: skip
    assert probe.returncode != 0 and "bind attempted" in probe.stderr


@pytest.mark.tc("TC-CLI-006")
def test_exit_code_0(tmp_path):
    out = run(["batch", write(tmp_path, fx("FX-ALLPASS"))])
    assert out.returncode == 0
    assert len(lines(out.stdout)) == 2


@pytest.mark.tc("TC-CLI-007")
def test_exit_code_1(tmp_path):
    assert run(["batch", SAMPLE]).returncode == 1
    assert run(["batch", write(tmp_path, fx("FX-BATCH"))]).returncode == 1


@pytest.mark.tc("TC-CLI-008")
def test_exit_code_2(tmp_path):
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not json", encoding="utf-8")
    good = write(tmp_path, fx("FX-ALLPASS"))
    cases = [
        ["batch", write(tmp_path, fx("FX-THREEERR"), "three.json")],
        ["batch", tmp_path / "missing.json"],
        ["batch", bad_json],
        ["batch"],
        [],
        ["batch", good, "--bogus"],
        ["batch", good, "--csv"],
        ["batch", tmp_path],
    ]
    for args in cases:
        out = run(args)
        assert out.returncode == 2, args
        assert "Traceback" not in out.stderr, args
        assert out.stdout == "", args
    # An export that cannot be written is also reported without a traceback.
    out = run(["batch", good, "--csv", tmp_path / "no_such_dir" / "o.csv"])
    assert out.returncode == 2 and "Traceback" not in out.stderr


@pytest.mark.tc("TC-CLI-009")
def test_validation_errors_on_stderr(tmp_path):
    doc = setp(fx("FX-THREEERR"), "$.zzz", 1)
    assert validate(doc).warnings  # the unknown key does warn
    out = run(["batch", write(tmp_path, doc)])
    assert out.returncode == 2
    assert out.stdout == ""
    err = lines(out.stderr)
    assert len(err) == 3
    for path in ("$.loads[0].power", "$.trus[0].efficiency", "$.loads[1].bus"):
        matching = [line for line in err if line.startswith(path + ": ")]
        assert len(matching) == 1 and len(matching[0]) > len(path) + 2
    assert not any("zzz" in line or "warning" in line.lower() for line in err)


@pytest.mark.tc("TC-CLI-010")
def test_warnings_do_not_stop_a_run(tmp_path):
    doc = setp(fx("FX-ALLPASS"), "$.zzz", 1)
    out = run(["batch", write(tmp_path, doc)])
    assert out.returncode == 0
    assert len(lines(out.stdout)) == 2
    warned = [line for line in lines(out.stderr) if "zzz" in line]
    assert len(warned) == 1 and warned[0].startswith("warning: ")


@pytest.mark.tc("TC-CLI-011")
def test_runtime_and_dependency_management():
    project = tomllib.loads((ROOT / "pyproject.toml").read_text("utf-8"))
    assert project["project"]["requires-python"] == ">=3.12"
    assert (ROOT / "uv.lock").exists()
    out = subprocess.run(
        ["uv", "sync", "--locked"], cwd=ROOT, capture_output=True, text=True, check=False
    )
    assert out.returncode == 0, out.stderr
