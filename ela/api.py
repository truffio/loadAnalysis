"""HTTP API and static front end (docs/spec.md §6.1 and §7, DD-009, DD-016, DD-024).

`uvicorn ela.api:app` serves the six routes under `/api/definitions` and the `web/` folder at `/`.
Uvicorn binds to 127.0.0.1 unless told otherwise, which is what the tool wants (DD-016). There is no
authentication, so a request must come from this machine by `Host` and `Origin` (DD-029). No route
changes or deletes a stored definition: an upload only adds a file.

Every error answer has the shape `{"errors": [{"path", "message"}], "warnings": [...]}`.
"""

import contextlib
import mimetypes
import os
import re
from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import Depends, FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from starlette.datastructures import Headers

from ela.batch import run_batch, to_csv, to_json
from ela.engine import analyse
from ela.layout import layout
from ela.validate import Issue, check_states, parse_json, validate

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DEFAULT_DEFINITIONS_DIR = ROOT / "definitions"
RESERVED_STEMS = {"CON", "PRN", "AUX", "NUL"}
RESERVED_STEMS |= {f"COM{n}" for n in range(1, 10)} | {f"LPT{n}" for n in range(1, 10)}
LOCAL_HOSTS = {"localhost", "127.0.0.1", "[::1]"}
TEST_HOST = "testserver"  # the Host header of FastAPI's TestClient
MAX_BODY = 10_000_000  # bytes (DD-028)
MULTIPART_ROOM = 65_536  # for the boundaries and part headers around an uploaded file

# Last batch results per stored file, held in memory only (L2-API-015).
_last_batch: dict[Path, list[dict]] = {}


def definitions_dir() -> Path:
    """The definitions folder, read from the environment on every call (L2-API-026)."""
    value = os.environ.get("ELA_DEFINITIONS_DIR")
    return Path(value) if value else DEFAULT_DEFINITIONS_DIR


def _issues(issues) -> list[dict]:
    return [{"path": i.path, "message": i.message} for i in issues]


def _failure(status, errors, warnings=()) -> JSONResponse:
    return JSONResponse(
        status_code=status, content={"errors": _issues(errors), "warnings": _issues(warnings)}
    )


def _stored_files() -> dict[str, Path]:
    folder = definitions_dir()
    if not folder.is_dir():
        return {}
    return {p.stem: p for p in sorted(folder.glob("*.json")) if p.is_file()}


def _too_large() -> JSONResponse:
    return _failure(413, [Issue("$", f"the request is over the limit of {MAX_BODY} bytes")])


def _host_name(authority: str) -> str | None:
    """The lower-case host of `host` or `host:port`, an IPv6 address keeping its brackets."""
    match = re.fullmatch(r"(\[[0-9A-Fa-f:.]*\]|[^:\[\]]*)(:\d*)?", authority)
    return match.group(1).lower() if match else None


def _is_local_origin(origin: str) -> bool:
    parts = urlsplit(origin)
    return parts.scheme in ("http", "https") and _host_name(parts.netloc) in LOCAL_HOSTS


class LocalRequestsOnly:
    """Refuses a request that a website, by itself or through DNS rebinding, could make (DD-029).

    Starlette's TrustedHostMiddleware is not used, because it cuts `[::1]:8000` at the first colon
    and answers in plain text. A request with no `Origin` header is not from a web page's script.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] == "http":
            headers = Headers(scope=scope)
            host = headers.get("host", "")
            if _host_name(host) not in LOCAL_HOSTS | {TEST_HOST}:
                refusal = _failure(400, [Issue("$", f"host '{host}' is not local")])
                return await refusal(scope, receive, send)
            for origin in headers.getlist("origin"):
                if not _is_local_origin(origin):
                    refusal = _failure(403, [Issue("$", f"origin '{origin}' is not local")])
                    return await refusal(scope, receive, send)
        await self.app(scope, receive, send)


class BodyLimit:
    """Answers 413 from the declared length, or from the bytes as they arrive (DD-028).

    The body is read here, because a route's own read happens inside FastAPI, which turns any
    failure there into a 400. The cap leaves room for multipart framing, so the routes check the
    exact limit on what they get.
    """

    cap = MAX_BODY + MULTIPART_ROOM

    def __init__(self, app):
        self.app = app

    def _declared_over(self, scope) -> bool:
        try:
            return int(Headers(scope=scope).get("content-length", "0")) > self.cap
        except ValueError:  # not a number, or too long to be one: count what arrives instead
            return False

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if self._declared_over(scope):
            return await _too_large()(scope, receive, send)
        body = bytearray()
        while True:
            message = await receive()
            if message["type"] != "http.request":
                return None  # the client went away
            body += message.get("body", b"")
            if len(body) > self.cap:
                return await _too_large()(scope, receive, send)
            if not message.get("more_body", False):
                break

        delivered = False

        async def replay():
            nonlocal delivered
            if delivered:
                return await receive()
            delivered = True
            return {"type": "http.request", "body": bytes(body), "more_body": False}

        await self.app(scope, replay, send)


def _load(def_id: str):
    """Look up a stored definition by id. Returns (path, validation, None) or (None, None, error
    response). The id is only ever compared with the names found in the folder."""
    path = _stored_files().get(def_id)
    if path is None:
        return None, None, _failure(404, [Issue("$", f"no definition with id '{def_id}'")])
    try:
        raw = path.read_bytes()
    except OSError as exc:
        return None, None, _failure(404, [Issue("$", f"cannot read '{def_id}': {exc.strerror}")])
    doc, problems = parse_json(raw)
    if problems:
        return None, None, _failure(422, problems)
    result = validate(doc)
    if result.errors:
        return None, None, _failure(422, result.errors, result.warnings)
    return path, result, None


def upload_stem(filename: str | None) -> str:
    """The stored stem for an uploaded name (L2-API-008): last path segment, extension dropped,
    every character outside [A-Za-z0-9_-] replaced by an underscore."""
    name = re.split(r"[/\\]", filename or "")[-1]
    if "." in name:
        name = name[: name.rindex(".")]
    return re.sub(r"[^A-Za-z0-9_-]", "_", name)


def _text_or_null(value):
    """Only text is listed from a file that may be invalid. JSON cannot carry an infinity."""
    return value if isinstance(value, str) else None


def list_definitions():
    entries = []
    for stem, path in _stored_files().items():
        meta = {}
        try:
            doc, _ = parse_json(path.read_bytes())
            if isinstance(doc, dict) and isinstance(doc.get("meta"), dict):
                meta = doc["meta"]
        except OSError:
            pass
        entries.append(
            {
                "id": stem,
                "aircraft": _text_or_null(meta.get("aircraft")),
                "revision": _text_or_null(meta.get("revision")),
            }
        )
    return {"definitions": entries}


def upload_definition(file: Annotated[UploadFile, File()]):
    raw = file.file.read()
    if len(raw) > MAX_BODY:
        return _too_large()
    doc, problems = parse_json(raw)
    if problems:
        return _failure(422, problems)
    result = validate(doc)
    if result.errors:
        return _failure(422, result.errors, result.warnings)

    stem = upload_stem(file.filename)
    if not stem.strip("_") or stem.upper() in RESERVED_STEMS:
        problem = (
            f"'{file.filename}' does not give a usable file name: rename it with letters A to Z, "
            "digits, '_' or '-'"
        )
        return _failure(422, [Issue("$", problem)], result.warnings)
    folder = definitions_dir()
    folder.mkdir(parents=True, exist_ok=True)
    taken = {p.name.lower() for p in folder.iterdir()}
    conflict = _failure(409, [Issue("$", f"a definition named '{stem}' already exists")])
    if f"{stem}.json".lower() in taken:
        return conflict
    path = folder / f"{stem}.json"
    try:
        with open(path, "xb") as f:  # "x" never replaces an existing file
            f.write(raw)
    except FileExistsError:
        return conflict
    except OSError:
        with contextlib.suppress(OSError):
            path.unlink()  # a partial file would list as a broken definition
        raise
    return JSONResponse(
        status_code=201, content={"id": stem, "warnings": _issues(result.warnings)}
    )


def get_definition(id: str):
    _, result, failure = _load(id)
    if failure:
        return failure
    return {
        "id": id,
        "definition": result.definition.model_dump(by_alias=True, mode="json"),
        "layout": layout(result.definition),
        "warnings": _issues(result.warnings),
    }


async def _request_body(request: Request) -> bytes:
    return await request.body()


def analyse_definition(id: str, raw: Annotated[bytes, Depends(_request_body)]):
    """A plain `def`, so that FastAPI runs the analysis in its threadpool, off the event loop."""
    if len(raw) > MAX_BODY:
        return _too_large()
    _, result, failure = _load(id)
    if failure:
        return failure
    body, problems = parse_json(raw)
    if problems:
        return _failure(422, problems, result.warnings)
    if not isinstance(body, dict) or "states" not in body:
        return _failure(
            422, [Issue("$.states", 'the body must be {"states": {...}}')], result.warnings
        )
    issues = check_states(result.definition, body["states"])
    if issues:
        return _failure(422, issues, result.warnings)
    return analyse(result.definition, body["states"]).to_dict()


def run_definition_batch(id: str):
    path, result, failure = _load(id)
    if failure:
        return failure
    results = run_batch(result.definition)
    _last_batch[path] = results
    return {"results": results}


def export_batch(id: str, format: str | None = Query(None)):
    path = _stored_files().get(id)
    if path is None:
        return _failure(404, [Issue("$", f"no definition with id '{id}'")])
    if format not in ("csv", "json"):
        return _failure(422, [Issue("$.format", "format must be csv or json")])
    results = _last_batch.get(path)
    if results is None:
        return _failure(404, [Issue("$", f"no batch has been run for '{id}'")])
    if format == "csv":
        return Response(to_csv(results), media_type="text/csv")
    return Response(to_json(results), media_type="application/json")


def _validation_failure(request: Request, exc: RequestValidationError):
    errors = [
        Issue("$." + ".".join(str(p) for p in e["loc"][1:]) if len(e["loc"]) > 1 else "$", e["msg"])
        for e in exc.errors()
    ]
    return _failure(422, errors)


def _filesystem_failure(request: Request, exc: OSError):
    return _failure(500, [Issue("$", f"file system error: {exc.strerror or exc}")])


def create_app(web_dir: Path | str | None = None) -> FastAPI:
    """Build the application. `web_dir` is the folder served at `/`, default `web/`."""
    mimetypes.add_type("text/javascript", ".js")  # Windows registries may say text/plain
    app = FastAPI(title="ELA")
    app.add_exception_handler(RequestValidationError, _validation_failure)
    app.add_exception_handler(OSError, _filesystem_failure)
    app.add_middleware(BodyLimit)
    app.add_middleware(LocalRequestsOnly)  # added last, so it runs first
    base = "/api/definitions"
    for path, method, endpoint in (
        (base, "GET", list_definitions),
        (base, "POST", upload_definition),
        (f"{base}/{{id}}", "GET", get_definition),
        (f"{base}/{{id}}/analyse", "POST", analyse_definition),
        (f"{base}/{{id}}/batch", "POST", run_definition_batch),
        (f"{base}/{{id}}/batch/export", "GET", export_batch),
    ):
        app.add_api_route(path, endpoint, methods=[method])
    # Mounted last, so that the API routes above take precedence over the static files. A missing
    # folder is left unmounted, since Starlette refuses to start on one.
    folder = Path(web_dir or WEB_DIR)
    if folder.is_dir():
        app.mount("/", StaticFiles(directory=folder, html=True), name="web")
    return app


app = create_app()
