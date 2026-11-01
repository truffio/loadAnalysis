"""C-API cases from docs/test-cases.md, through the FastAPI TestClient (H-CLIENT) or a uvicorn
subprocess (H-SERVER). The harness fixtures are in tests/conftest.py.
"""

import asyncio
import hashlib
import inspect
import json
import re
import socket
import subprocess
import sys

import httpx
import pytest
from conftest import REPO, fx, put_def, setp
from fastapi import FastAPI
from fastapi.testclient import TestClient

import ela.api
from ela.batch import run_batch, to_csv, to_json
from ela.engine import analyse
from ela.layout import layout
from ela.validate import validate

BASE = "/api/definitions"
WEB = REPO / "web"


def upload(client, doc, name):
    """POST a fixture document, or raw text or bytes, as the multipart field `file`."""
    if isinstance(doc, bytes):
        body = doc
    elif isinstance(doc, str):
        body = doc.encode("utf-8")
    else:
        body = json.dumps(doc).encode("utf-8")
    return client.post(BASE, files={"file": (name, body, "application/json")})


def listed(client):
    return {d["id"]: d for d in client.get(BASE).json()["definitions"]}


def tree(folder):
    return sorted(p.name for p in folder.iterdir())


def serialised(obj):
    return json.loads(json.dumps(obj))


def assert_rejection(response, count=None):
    assert response.status_code == 422
    body = response.json()
    assert isinstance(body["warnings"], list)
    assert body["errors"]
    if count is not None:
        assert len(body["errors"]) == count
    for e in body["errors"]:
        assert e["path"] and e["message"]
    return body


# --- Definitions ---------------------------------------------------------------------------------


@pytest.mark.tc("TC-API-001")
def test_list_definitions_by_file_stem(client, defs_dir):
    put_def(defs_dir, fx("FX-SINGLE"), "other.json")
    put_def(defs_dir, "{not json", "raw.json")
    put_def(defs_dir, "notes", "notes.txt")
    response = client.get(BASE)
    assert response.status_code == 200
    entries = {d["id"]: d for d in response.json()["definitions"]}
    assert set(entries) == {"generic_twin", "other", "raw"}
    twin_meta = json.loads((defs_dir / "generic_twin.json").read_text("utf-8"))["meta"]
    assert entries["generic_twin"] == {
        "id": "generic_twin",
        "aircraft": twin_meta["aircraft"],
        "revision": twin_meta["revision"],
    }
    assert entries["other"] == {"id": "other", "aircraft": "Test", "revision": "A"}
    assert entries["raw"] == {"id": "raw", "aircraft": None, "revision": None}


@pytest.mark.tc("TC-API-002")
def test_definition_with_layout_and_warnings(client, defs_dir):
    put_def(defs_dir, fx("FX-WARN"), "fx_warn.json")
    twin = client.get(f"{BASE}/generic_twin")
    assert twin.status_code == 200
    body = twin.json()
    assert set(body) == {"id", "definition", "layout", "warnings"}
    assert body["id"] == "generic_twin"
    assert body["definition"]["meta"]["aircraft"]
    assert body["layout"]["items"] and body["layout"]["connectors"]
    assert isinstance(body["warnings"], list)
    for w in body["warnings"]:
        assert w["path"] and w["message"]
    defn = validate(json.loads((defs_dir / "generic_twin.json").read_text("utf-8"))).definition
    assert body["layout"] == serialised(layout(defn))

    warn = client.get(f"{BASE}/fx_warn")
    assert warn.status_code == 200
    assert "$.zzz" in [w["path"] for w in warn.json()["warnings"]]


@pytest.mark.tc("TC-API-003")
def test_invalid_stored_file_is_refused_with_all_errors(client, defs_dir):
    put_def(defs_dir, fx("FX-THREEERR"), "fx_threeerr.json")
    put_def(defs_dir, "{not json", "raw.json")
    first = client.get(f"{BASE}/fx_threeerr")
    body = assert_rejection(first, 3)
    assert "layout" not in body
    second = client.get(f"{BASE}/raw")
    body = assert_rejection(second)
    assert [e["path"] for e in body["errors"]] == ["$"]


@pytest.mark.tc("TC-API-004")
def test_unknown_id_gives_404_on_every_route(client):
    assert client.get(f"{BASE}/nosuch").status_code == 404
    assert client.post(f"{BASE}/nosuch/analyse", json={"states": {}}).status_code == 404
    assert client.post(f"{BASE}/nosuch/batch").status_code == 404
    assert client.get(f"{BASE}/nosuch/batch/export", params={"format": "csv"}).status_code == 404


@pytest.mark.tc("TC-API-005")
def test_path_traversal_in_the_id(client, defs_dir):
    secret = fx("FX-SINGLE")
    secret["meta"]["aircraft"] = "OUTSIDE-SECRET"
    put_def(defs_dir.parent, secret, "outside.json")
    for path in ("..%2Foutside", "..%5Coutside", "%2e%2e%2foutside"):
        response = client.get(f"{BASE}/{path}")
        assert 400 <= response.status_code < 500, path
        assert "OUTSIDE-SECRET" not in response.text, path


# --- Upload --------------------------------------------------------------------------------------


@pytest.mark.tc("TC-API-006")
def test_valid_upload_is_stored_and_answered_201(client, defs_dir):
    response = upload(client, fx("FX-WARN"), "new_def.json")
    assert response.status_code == 201
    body = response.json()
    assert body["id"] == "new_def"
    assert "$.zzz" in [w["path"] for w in body["warnings"]]
    assert (defs_dir / "new_def.json").is_file()
    assert "new_def" in listed(client)


@pytest.mark.tc("TC-API-023")
def test_analyse_body_and_upload_field_names(client, defs_dir):
    put_def(defs_dir, fx("FX-SINGLE"), "fx_single.json")
    response = client.post(f"{BASE}/fx_single/analyse", json={"states": {"G1": "failed"}})
    assert response.status_code == 200
    assert response.json()["el"]["G1"]["state"] == "failed"
    assert upload(client, fx("FX-SINGLE"), "field_test.json").status_code == 201


@pytest.mark.tc("TC-API-007")
def test_invalid_upload_stores_nothing(client, defs_dir):
    before = tree(defs_dir)
    assert_rejection(upload(client, fx("FX-THREEERR"), "bad.json"), 3)
    body = assert_rejection(upload(client, "{not json", "bad.json"))
    assert [e["path"] for e in body["errors"]] == ["$"]
    assert tree(defs_dir) == before


@pytest.mark.tc("TC-API-008")
def test_traversal_empty_and_reserved_upload_names(client, defs_dir):
    stored = {
        "../../evil name.json": "evil_name.json",
        "..\\..\\evil2.json": "evil2.json",
        "/abs/evil3.json": "evil3.json",
    }
    for name, expected in stored.items():
        assert upload(client, fx("FX-SINGLE"), name).status_code == 201, name
        assert (defs_dir / expected).is_file(), name
    refused = [".json", "../.json", "nul.json", "NUL.json", "con.json", "COM1.json", "lpt9.json"]
    refused += ["é.json", "__.json", "日本語.json"]
    after_good = tree(defs_dir)
    for name in refused:
        body = assert_rejection(upload(client, fx("FX-SINGLE"), name))
        assert "usable file name" in body["errors"][0]["message"], name
    assert tree(defs_dir) == after_good
    assert all(re.fullmatch(r"[A-Za-z0-9_-]+\.json", n) for n in after_good)
    assert tree(defs_dir.parent) == ["defs"]


@pytest.mark.tc("TC-API-009")
def test_name_collisions(client, defs_dir):
    twin = defs_dir / "generic_twin.json"
    original = twin.read_bytes()
    assert upload(client, fx("FX-SINGLE"), "generic_twin.json").status_code == 409
    assert upload(client, fx("FX-SINGLE"), "GENERIC_TWIN.json").status_code == 409
    assert upload(client, fx("FX-THREEERR"), "generic_twin.json").status_code == 422
    assert twin.read_bytes() == original
    assert upload(client, fx("FX-SINGLE"), "a b.json").status_code == 201
    assert upload(client, fx("FX-SINGLE"), "a_b.json").status_code == 409
    assert sorted(listed(client)) == ["a_b", "generic_twin"]


# --- Analyse -------------------------------------------------------------------------------------


def analyse_url(name):
    return f"{BASE}/{name}/analyse"


def expected_analysis(doc, states):
    return serialised(analyse(validate(doc).definition, states).to_dict())


@pytest.mark.tc("TC-API-010")
def test_analyse_returns_the_engine_result(client, defs_dir):
    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    states = {"G1": "failed", "T12": "closed"}
    response = client.post(analyse_url("fx_batch"), json={"states": states})
    assert response.status_code == 200
    assert response.json() == expected_analysis(fx("FX-BATCH"), states)
    assert response.json()["el"]["G2"]["demand"] == {
        "transient": 2000,
        "short_term": 1800,
        "continuous": 1600,
    }


@pytest.mark.tc("TC-API-011")
def test_analyse_response_fields(client, defs_dir):
    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    fields = ["el", "verdict", "overloads", "config_errors", "unpowered", "warnings"]

    s5 = client.post(analyse_url("fx_batch"), json={"states": {"T13": "closed"}}).json()
    for name in fields:
        assert name in s5
    assert s5["verdict"] == "FAIL"
    assert len(s5["overloads"]) == 3
    assert s5["config_errors"] == []
    for record in s5["el"].values():
        for name in ("energised", "demand", "capacity"):
            assert name in record
    assert s5["el"]["G1"]["energised"] is True
    assert isinstance(s5["warnings"], list)

    s4 = client.post(
        analyse_url("fx_batch"), json={"states": {"G1": "failed", "G2": "failed"}}
    ).json()
    for name in fields:
        assert name in s4
    assert len(s4["unpowered"]) == 1
    assert isinstance(s4["warnings"], list)


@pytest.mark.tc("TC-API-012")
def test_bad_analyse_body(client, defs_dir):
    put_def(defs_dir, fx("FX-SINGLE"), "fx_single.json")
    ghost = client.post(analyse_url("fx_single"), json={"states": {"GHOST": "failed"}})
    assert_rejection(ghost)
    invalid = client.post(analyse_url("fx_single"), json={"states": {"G1": "closed"}})
    assert_rejection(invalid)
    # A body that is not the published shape is refused in the same form.
    assert_rejection(client.post(analyse_url("fx_single"), json={"G1": "failed"}))
    assert_rejection(client.post(analyse_url("fx_single"), content=b"{not json"))
    assert_rejection(client.post(analyse_url("fx_single"), json={"states": ["G1"]}))


@pytest.mark.tc("TC-API-013")
def test_analyse_is_stateless(client, defs_dir):
    from fastapi.testclient import TestClient

    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    failed = client.post(analyse_url("fx_batch"), json={"states": {"G1": "failed"}}).json()
    assert failed["el"]["G1"]["state"] == "failed"
    second = client.post(analyse_url("fx_batch"), json={"states": {}})
    fresh = TestClient(ela.api.app).post(analyse_url("fx_batch"), json={"states": {}})
    assert second.json() == fresh.json()
    assert second.json()["el"]["G1"]["energised"] is True
    assert second.json()["el"]["G1"]["state"] == "operative"
    assert second.json() == expected_analysis(fx("FX-BATCH"), {})


# --- Batch ---------------------------------------------------------------------------------------


@pytest.mark.tc("TC-API-014")
def test_batch_route(client, defs_dir):
    response = client.post(f"{BASE}/generic_twin/batch")
    assert response.status_code == 200
    twin = validate(json.loads((defs_dir / "generic_twin.json").read_text("utf-8"))).definition
    assert response.json() == {"results": serialised(run_batch(twin))}


@pytest.mark.tc("TC-API-015")
def test_last_batch_results_by_definition_in_memory_only(defs_dir, start_server):
    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    put_def(defs_dir, fx("FX-ALLPASS"), "fx_allpass.json")
    server = start_server()
    with httpx.Client(base_url=server.url, timeout=30) as http:
        for name in ("fx_batch", "fx_allpass"):
            assert http.post(f"{BASE}/{name}/batch").status_code == 200
        counts = {}
        for name in ("fx_batch", "fx_allpass"):
            export = http.get(f"{BASE}/{name}/batch/export", params={"format": "json"})
            assert export.status_code == 200
            counts[name] = [r["scenario_id"] for r in export.json()]
        assert counts == {
            "fx_batch": ["S1", "S2", "S3", "S4", "S5"],
            "fx_allpass": ["S1", "S2"],
        }
    server.stop()

    restarted = start_server()
    with httpx.Client(base_url=restarted.url, timeout=30) as http:
        for name in ("fx_batch", "fx_allpass"):
            export = http.get(f"{BASE}/{name}/batch/export", params={"format": "json"})
            assert export.status_code == 404


@pytest.mark.tc("TC-API-016")
def test_export_formats(client, defs_dir):
    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    results = run_batch(validate(fx("FX-BATCH")).definition)
    assert client.post(f"{BASE}/fx_batch/batch").status_code == 200
    csv_response = client.get(f"{BASE}/fx_batch/batch/export", params={"format": "csv"})
    assert csv_response.status_code == 200
    assert csv_response.content.decode("utf-8") == to_csv(results)
    assert csv_response.headers["content-type"].split(";")[0] == "text/csv"
    json_response = client.get(f"{BASE}/fx_batch/batch/export", params={"format": "json"})
    assert json_response.status_code == 200
    assert json_response.content.decode("utf-8") == to_json(results)
    assert json_response.headers["content-type"].split(";")[0] == "application/json"


@pytest.mark.tc("TC-API-017")
def test_export_refusals(client, defs_dir):
    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    export = f"{BASE}/fx_batch/batch/export"
    assert client.get(export, params={"format": "csv"}).status_code == 404
    assert client.get(export, params={"format": "json"}).status_code == 404
    assert client.post(f"{BASE}/fx_batch/batch").status_code == 200
    assert_rejection(client.get(export, params={"format": "xml"}))
    assert_rejection(client.get(export))


# --- Server --------------------------------------------------------------------------------------


@pytest.mark.tc("TC-API-018")
def test_app_serves_the_front_end(client, tmp_path):
    assert isinstance(ela.api.app, FastAPI)
    index = client.get("/")
    assert index.status_code == 200
    assert index.content == (WEB / "index.html").read_bytes()
    # Whichever other front-end files exist in web/ are served as they are.
    for name in ("app.js", "schematic.js", "batch.js", "styles.css"):
        if (WEB / name).is_file():
            response = client.get(f"/{name}")
            assert response.status_code == 200
            assert response.content == (WEB / name).read_bytes()

    # An app made on a folder holding all five files serves each one.
    site = tmp_path / "site"
    site.mkdir()
    contents = {}
    for name in ("index.html", "app.js", "schematic.js", "batch.js", "styles.css"):
        contents[name] = f"/* {name} */\n".encode()
        (site / name).write_bytes(contents[name])
    other = TestClient(ela.api.create_app(web_dir=site))
    assert other.get("/").content == contents["index.html"]
    for name in ("app.js", "schematic.js", "batch.js", "styles.css"):
        response = other.get(f"/{name}")
        assert response.status_code == 200
        assert response.content == contents[name]

    # The API routes take precedence over the static mount, and an empty or absent web folder
    # does not stop the app starting.
    for web_dir in (tmp_path / "empty", tmp_path / "absent"):
        if web_dir.name == "empty":
            web_dir.mkdir()
        bare = TestClient(ela.api.create_app(web_dir=web_dir))
        assert bare.get(BASE).status_code == 200
        assert bare.get(f"{BASE}/generic_twin").status_code == 200
        assert bare.get("/app.js").status_code == 404


def listening_addresses(port):
    """Local addresses of the TCP sockets listening on `port`, from netstat."""
    out = subprocess.run(
        ["netstat", "-an"], capture_output=True, text=True, check=True, timeout=30
    ).stdout
    found = set()
    for line in out.splitlines():
        # A listening row has an empty remote address. The state word is localised, so ignore it.
        match = re.match(
            r"\s*tcp\S*\s+(?:\d+\s+\d+\s+)?(\S+):(\d+)\s+\S+:[0*]\s",
            line,
            re.IGNORECASE,
        )
        if match and int(match.group(2)) == port:
            found.add(match.group(1))
    if sys.platform == "win32":
        # netstat can miss a socket that Get-NetTCPConnection reports for the same port.
        query = f"Get-NetTCPConnection -LocalPort {port} | ForEach-Object {{ $_.LocalAddress }}"
        shell = subprocess.run(
            ["powershell", "-NoProfile", "-Command", query],
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        found |= {line.strip() for line in shell.stdout.splitlines() if line.strip()}
    return found


def non_loopback_address():
    candidates = []
    try:
        candidates += [i[4][0] for i in socket.getaddrinfo(socket.gethostname(), None, socket.AF_INET)]
    except OSError:
        pass
    try:
        with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
            s.connect(("192.0.2.1", 9))  # no packet is sent by a UDP connect
            candidates.append(s.getsockname()[0])
    except OSError:
        pass
    return next((a for a in candidates if not a.startswith("127.") and a != "0.0.0.0"), None)


@pytest.mark.tc("TC-API-019")
def test_one_command_loopback_only(start_server):
    server = start_server()
    with httpx.Client(base_url=server.url, timeout=30) as http:
        assert http.get("/").status_code == 200
        assert http.get(BASE).status_code == 200
    address = non_loopback_address()
    if address is not None:
        with pytest.raises(OSError), socket.create_connection((address, server.port), timeout=5):
            pass
    assert listening_addresses(server.port) == {"127.0.0.1"}


@pytest.mark.tc("TC-API-020")
def test_no_authentication(client, defs_dir):
    from fastapi.routing import APIRoute

    put_def(defs_dir, fx("FX-BATCH"), "fx_batch.json")
    checked = 0
    for route in ela.api.app.routes:
        path = route.path.replace("{id}", "generic_twin") or "/"
        if isinstance(route, APIRoute) or hasattr(route, "methods") and route.methods:
            methods = sorted(route.methods - {"HEAD", "OPTIONS"})
        else:
            methods = ["GET"]  # the static mount
        for method in methods:
            if method == "GET":
                response = client.get(path)
            else:
                response = client.request(method, path, json={"states": {}})
            assert response.status_code not in (401, 403), (method, path)
            checked += 1
    assert checked >= 7


@pytest.mark.tc("TC-API-021")
def test_no_route_edits_a_definition():
    api = {
        (method, route.path)
        for route in ela.api.app.routes
        if route.path.startswith("/api")
        for method in route.methods
    }
    assert api == {
        ("GET", "/api/definitions"),
        ("POST", "/api/definitions"),
        ("GET", "/api/definitions/{id}"),
        ("POST", "/api/definitions/{id}/analyse"),
        ("POST", "/api/definitions/{id}/batch"),
        ("GET", "/api/definitions/{id}/batch/export"),
    }
    assert not {m for m, _ in api} & {"PUT", "PATCH", "DELETE"}


@pytest.mark.tc("TC-API-022")
def test_definitions_folder_comes_from_the_environment(tmp_path, start_server):
    def digest():
        h = hashlib.sha256()
        for p in sorted((REPO / "definitions").rglob("*")):
            h.update(p.name.encode())
            if p.is_file():
                h.update(p.read_bytes())
        return h.hexdigest()

    other = tmp_path / "other"
    other.mkdir()
    put_def(other, fx("FX-SINGLE"), "fx_single.json")
    before = digest()

    server = start_server(env_dir=other)
    with httpx.Client(base_url=server.url, timeout=30) as http:
        ids = {d["id"] for d in http.get(BASE).json()["definitions"]}
        assert "fx_single" in ids
        assert "generic_twin" not in ids
        body = json.dumps(fx("FX-WARN")).encode()
        assert http.post(BASE, files={"file": ("up.json", body)}).status_code == 201
    server.stop()
    assert (other / "up.json").is_file()
    assert digest() == before

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    unset = start_server(env_dir=None, cwd=elsewhere)
    with httpx.Client(base_url=unset.url, timeout=30) as http:
        ids = {d["id"] for d in http.get(BASE).json()["definitions"]}
        assert "generic_twin" in ids
    assert digest() == before


# --- Local requests only (DD-029) ----------------------------------------------------------------


ALL_ROUTES = [
    ("GET", "/"),
    ("GET", "/app.js"),
    ("GET", BASE),
    ("POST", BASE),
    ("GET", f"{BASE}/generic_twin"),
    ("POST", f"{BASE}/generic_twin/analyse"),
    ("POST", f"{BASE}/generic_twin/batch"),
    ("GET", f"{BASE}/generic_twin/batch/export?format=csv"),
]


def assert_error_shape(response, status):
    assert response.status_code == status
    body = response.json()
    assert set(body) == {"errors", "warnings"}
    assert body["errors"][0]["path"] and body["errors"][0]["message"]


@pytest.mark.tc("TC-API-024")
@pytest.mark.parametrize(
    "host", ["localhost", "localhost:8000", "127.0.0.1:8000", "[::1]", "[::1]:8000", "LOCALHOST"]
)
def test_local_hosts_are_served(client, host):
    assert client.get(BASE, headers={"host": host}).status_code == 200


@pytest.mark.tc("TC-API-024")
@pytest.mark.parametrize(
    "host",
    [
        "evil.example",
        "evil.example:8000",
        "localhost.evil.example",
        "127.0.0.1.evil.example",
        "[::2]:8000",
        "[::1].evil.example",
        "0.0.0.0:8000",
        "",
    ],
)
@pytest.mark.parametrize("method, path", ALL_ROUTES)
def test_other_hosts_are_refused(client, host, method, path):
    assert_error_shape(client.request(method, path, headers={"host": host}), 400)


@pytest.mark.tc("TC-API-024")
def test_a_real_server_refuses_another_host(start_server):
    server = start_server()
    with httpx.Client(base_url=server.url, timeout=30) as http:
        assert http.get(BASE).status_code == 200
        assert_error_shape(http.get(BASE, headers={"host": "evil.example"}), 400)


@pytest.mark.tc("TC-API-025")
@pytest.mark.parametrize(
    "origin",
    ["http://127.0.0.1:8000", "http://localhost:5173", "http://[::1]:8000", "https://localhost"],
)
def test_local_origins_are_served(client, origin):
    assert client.post(f"{BASE}/generic_twin/batch", headers={"origin": origin}).status_code == 200


@pytest.mark.tc("TC-API-025")
@pytest.mark.parametrize(
    "origin",
    [
        "https://evil.example",
        "http://127.0.0.1.evil.example",
        "http://localhost.evil.example:8000",
        "http://localhost@evil.example",
        "http://[::2]:8000",
        "null",
        "file://",
        "ftp://localhost",
    ],
)
@pytest.mark.parametrize("method, path", ALL_ROUTES)
def test_other_origins_are_refused(client, defs_dir, origin, method, path):
    before = tree(defs_dir)
    assert_error_shape(client.request(method, path, headers={"origin": origin}), 403)
    assert tree(defs_dir) == before


@pytest.mark.tc("TC-API-025")
@pytest.mark.parametrize("method, path", ALL_ROUTES[:3] + ALL_ROUTES[4:5])
def test_no_origin_header_is_allowed(client, method, path):
    assert client.request(method, path).status_code == 200


# --- Limits (DD-028) -----------------------------------------------------------------------------


def padded(doc, size):
    """A definition's JSON text padded with spaces to exactly `size` bytes."""
    text = json.dumps(doc).encode("utf-8")
    return text + b" " * (size - len(text))


@pytest.mark.tc("TC-API-026")
def test_upload_at_the_limit_is_stored_and_over_it_is_refused(client, defs_dir):
    limit = ela.api.MAX_BODY
    assert limit == 10_000_000
    assert upload(client, padded(fx("FX-SINGLE"), limit), "at_limit.json").status_code == 201
    assert (defs_dir / "at_limit.json").stat().st_size == limit
    refused = upload(client, padded(fx("FX-SINGLE"), limit + 1), "over.json")
    assert_error_shape(refused, 413)
    assert not (defs_dir / "over.json").exists()


@pytest.mark.tc("TC-API-026")
def test_analyse_body_over_the_limit_is_refused(client):
    limit = ela.api.MAX_BODY
    url = analyse_url("generic_twin")
    assert client.post(url, content=padded({"states": {}}, limit)).status_code == 200
    assert_error_shape(client.post(url, content=padded({"states": {}}, limit + 1)), 413)


@pytest.mark.tc("TC-API-026")
def test_declared_length_is_refused_before_reading(client):
    reads = []

    async def receive():
        reads.append(1)
        return {"type": "http.request", "body": b"", "more_body": False}

    sent = []

    async def send(message):
        sent.append(message)

    async def never_called(scope, receive, send):
        raise AssertionError("the application ran")

    scope = {
        "type": "http",
        "method": "POST",
        "path": BASE,
        "headers": [(b"content-length", str(ela.api.BodyLimit.cap + 1).encode())],
    }
    asyncio.run(ela.api.BodyLimit(never_called)(scope, receive, send))
    assert sent[0]["status"] == 413
    assert reads == []


@pytest.mark.tc("TC-API-026")
def test_stream_with_no_length_is_cut_off_while_reading():
    chunk = 1_000_000
    reads = []

    async def receive():
        reads.append(1)
        return {"type": "http.request", "body": b"x" * chunk, "more_body": True}

    sent = []

    async def send(message):
        sent.append(message)

    async def never_called(scope, receive, send):
        raise AssertionError("the application ran")

    scope = {"type": "http", "method": "POST", "path": BASE, "headers": []}
    asyncio.run(ela.api.BodyLimit(never_called)(scope, receive, send))
    assert sent[0]["status"] == 413
    assert json.loads(sent[1]["body"])["errors"]
    assert len(reads) == ela.api.BodyLimit.cap // chunk + 1


@pytest.mark.tc("TC-API-026")
def test_chunked_request_through_the_client(client):
    def chunks():
        for _ in range(11):
            yield b" " * 1_000_000

    response = client.post(analyse_url("generic_twin"), content=chunks())
    assert_error_shape(response, 413)


@pytest.mark.tc("TC-API-027")
def test_analysis_runs_off_the_event_loop(client, monkeypatch):
    assert not inspect.iscoroutinefunction(ela.api.analyse_definition)
    for route in (ela.api.get_definition, ela.api.run_definition_batch, ela.api.upload_definition):
        assert not inspect.iscoroutinefunction(route)
    loops = []
    real = ela.api.analyse

    def spy(definition, states):
        try:
            loops.append(asyncio.get_running_loop())
        except RuntimeError:
            loops.append(None)
        return real(definition, states)

    monkeypatch.setattr(ela.api, "analyse", spy)
    assert client.post(analyse_url("generic_twin"), json={"states": {}}).status_code == 200
    assert loops == [None]


@pytest.mark.tc("TC-API-028")
def test_definitions_path_that_is_a_file_gives_the_json_shape(tmp_path, monkeypatch):
    blocker = tmp_path / "blocker"
    blocker.write_text("not a folder", encoding="utf-8")
    monkeypatch.setenv("ELA_DEFINITIONS_DIR", str(blocker))
    client = TestClient(ela.api.app)
    assert_error_shape(upload(client, fx("FX-SINGLE"), "new.json"), 500)


@pytest.mark.tc("TC-API-028")
def test_failed_write_gives_the_json_shape_and_leaves_no_file(client, defs_dir, monkeypatch):
    real_open = open

    def full_disk(path, mode):
        handle = real_open(path, mode)

        class Full:
            def __enter__(self):
                return self

            def __exit__(self, *exc):
                handle.close()

            def write(self, data):
                handle.write(data[:10])
                raise OSError(28, "No space left on device")

        return Full()

    monkeypatch.setattr(ela.api, "open", full_disk, raising=False)
    response = upload(client, fx("FX-SINGLE"), "partial.json")
    assert_error_shape(response, 500)
    assert "No space left" in response.json()["errors"][0]["message"]
    assert not (defs_dir / "partial.json").exists()


@pytest.mark.tc("TC-API-029")
def test_loader_is_shared_by_upload_store_and_analyse(client, defs_dir):
    repeated = b'{"meta": {"aircraft": "A", "aircraft": "B"}}'
    body = assert_rejection(upload(client, repeated, "repeat.json"))
    assert [e["path"] for e in body["errors"]] == ["$.meta.aircraft"]
    assert not (defs_dir / "repeat.json").exists()

    put_def(defs_dir, repeated.decode(), "stored.json")
    assert [e["path"] for e in assert_rejection(client.get(f"{BASE}/stored"))["errors"]] == [
        "$.meta.aircraft"
    ]

    states = b'{"states": {"GEN1": "failed", "GEN1": "operative"}}'
    response = client.post(analyse_url("generic_twin"), content=states)
    assert [e["path"] for e in assert_rejection(response)["errors"]] == ["$.states.GEN1"]

    marked = b"\xef\xbb\xbf" + json.dumps({"states": {}}).encode()
    assert client.post(analyse_url("generic_twin"), content=marked).status_code == 200
    bom_file = b"\xef\xbb\xbf" + json.dumps(fx("FX-SINGLE")).encode()
    assert upload(client, bom_file, "bom.json").status_code == 201
    assert client.get(f"{BASE}/bom").status_code == 200


@pytest.mark.tc("TC-API-029")
def test_extreme_values_give_an_answer_not_a_crash(client, defs_dir):
    doc = fx("FX-SINGLE")
    doc["sources"][0]["capacity"] = {"transient": 1e-300, "short_term": 1e-300, "continuous": 1}
    doc["trus"][0]["efficiency"] = 1e-300
    put_def(defs_dir, doc, "extreme.json")
    response = client.post(analyse_url("extreme"), json={"states": {}})
    assert response.status_code == 200
    assert response.json()["verdict"] == "FAIL"
    over = setp(fx("FX-SINGLE"), "$.loads[0].power.transient", 1e13)
    assert_rejection(upload(client, over, "over_cap.json"))


@pytest.mark.tc("TC-API-029")
def test_list_survives_a_stored_file_with_an_infinity(client, defs_dir):
    put_def(defs_dir, '{"meta": {"aircraft": 1e999, "revision": "A"}}', "inf.json")
    entry = listed(client)["inf"]
    assert (entry["aircraft"], entry["revision"]) == (None, "A")
