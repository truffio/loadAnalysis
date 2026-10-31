"""C-DOCS cases from docs/test-cases.md: the README, checked against the tool itself.

The commands in the README are run in a fresh copy of the repository (the `fresh_clone` fixture),
so a command that only works on the author's machine fails here.
"""

import re
import urllib.request

import pytest
import readme_tools as rt

from ela.model import Definition


def schema_property_names(node, found=None):
    """Every property name in a JSON schema, including those in `$defs`."""
    found = set() if found is None else found
    if isinstance(node, dict):
        for key, value in node.items():
            if key == "properties" and isinstance(value, dict):
                found.update(value)
            schema_property_names(value, found)
    elif isinstance(node, list):
        for item in node:
            schema_property_names(item, found)
    return found


@pytest.mark.tc("TC-DOC-001")
def test_installation_section(fresh_clone):
    heading, body = rt.section("Installation")
    assert heading.strip().lower().startswith("install")
    commands = rt.fenced_commands(body)
    assert commands
    assert all(command.split()[0] == "uv" for command in commands), commands
    assert [c for c, *_ in fresh_clone.installed] == commands
    for command, code, output in fresh_clone.installed:
        assert code == 0, f"{command} exited {code}:\n{output[-2000:]}"
    assert (fresh_clone.path / ".venv").is_dir()


@pytest.mark.tc("TC-DOC-002")
def test_running_section(fresh_clone, tmp_path):
    _, body = rt.section("Running")
    starts = [c for c in rt.fenced_commands(body) if rt.is_start_command(c)]
    assert len(starts) == 1
    assert starts[0].endswith("uvicorn ela.api:app")
    assert [code for _, code, _ in fresh_clone.installed] == [0] * len(fresh_clone.installed)
    address = rt.documented_address()
    server = rt.DocumentedServer(fresh_clone.path, tmp_path / "server.log")
    try:
        url = re.sub(r":\d+", f":{server.port}", address, count=1) + "/"
        with urllib.request.urlopen(url, timeout=10) as reply:
            page = reply.read().decode("utf-8")
            assert reply.status == 200
        assert "<title>" in page and 'id="schematic"' in page
    finally:
        server.stop()


@pytest.mark.tc("TC-DOC-003")
def test_batch_command_reference():
    _, body = rt.section("Running")
    assert "ela batch" in body
    assert "--csv" in body and "--json" in body
    rows = dict(re.findall(r"^\| ([012]) \| (.+?) \|$", body, re.MULTILINE))
    assert sorted(rows) == ["0", "1", "2"]
    assert "pass" in rows["0"].lower()
    assert "fail" in rows["1"].lower()
    assert "invalid" in rows["2"].lower()


@pytest.mark.tc("TC-DOC-004")
def test_json_format_reference():
    _, body = rt.section("JSON format")
    names = schema_property_names(Definition.model_json_schema())
    assert {"safety_margin", "from", "crew_switch", "essential"} <= names
    missing = sorted(n for n in names if f"`{n}`" not in body)
    assert missing == []
    lowered = body.lower()
    for unit in ("watts", "volts", "decimals"):
        assert unit in lowered, unit


@pytest.mark.tc("TC-DOC-005")
def test_band_meanings_and_ordering():
    _, body = rt.section("JSON format")
    meanings = {
        "transient": "inrush peak",
        "short_term": "first 5 seconds",
        "continuous": "steady state",
    }
    for band, phrase in meanings.items():
        rows = [line for line in body.splitlines() if line.startswith(f"| `{band}` |")]
        assert rows, band
        assert phrase in rows[0].lower(), (band, rows[0])
    assert re.search(r"does not enforce\s+`transient ≥ short_term ≥ continuous`", body)


@pytest.mark.tc("TC-DOC-006")
def test_adding_an_aircraft():
    heading, body = rt.section("Adding a new aircraft")
    assert "aircraft" in heading.lower()
    assert "`definitions/`" in body
    assert "ela batch definitions/" in body
    assert re.search(r"validate", body, re.IGNORECASE)
    assert "exit code is 2" in body
