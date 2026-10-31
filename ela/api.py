"""HTTP API and static front end (docs/spec.md §6.1 and §7, DD-009, DD-016, DD-024).

`uvicorn ela.api:app` serves the six routes under `/api/definitions` and the `web/` folder at `/`.
Uvicorn binds to 127.0.0.1 unless told otherwise, which is what the tool wants (DD-016). There is no
authentication. No route changes or deletes a stored definition: an upload only adds a file.

Every error answer has the shape `{"errors": [{"path", "message"}], "warnings": [...]}`.
"""

import json
import mimetypes
import os
import re
from pathlib import Path
from typing import Annotated

from fastapi import FastAPI, File, Query, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, Response
from fastapi.staticfiles import StaticFiles

from ela.batch import run_batch, to_csv, to_json
from ela.engine import analyse
from ela.layout import layout
from ela.validate import Issue, check_states, validate

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"
DEFAULT_DEFINITIONS_DIR = ROOT / "definitions"
RESERVED_STEMS = {"CON", "PRN", "AUX", "NUL"}
RESERVED_STEMS |= {f"COM{n}" for n in range(1, 10)} | {f"LPT{n}" for n in range(1, 10)}

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


def _parse(raw: bytes) -> tuple[object, Issue | None]:
    """Parsed JSON of a file or upload, or an error at `$` when it is not JSON."""
    try:
        return json.loads(raw.decode("utf-8-sig")), None
    except (ValueError, RecursionError) as exc:  # bad UTF-8 and bad JSON are both ValueError
        return None, Issue("$", f"not valid JSON: {exc}")


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
    doc, problem = _parse(raw)
    if problem:
        return None, None, _failure(422, [problem])
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


def list_definitions():
    entries = []
    for stem, path in _stored_files().items():
        meta = {}
        try:
            doc, _ = _parse(path.read_bytes())
            if isinstance(doc, dict) and isinstance(doc.get("meta"), dict):
                meta = doc["meta"]
        except OSError:
            pass
        entries.append(
            {"id": stem, "aircraft": meta.get("aircraft"), "revision": meta.get("revision")}
        )
    return {"definitions": entries}


def upload_definition(file: Annotated[UploadFile, File()]):
    raw = file.file.read()
    doc, problem = _parse(raw)
    if problem:
        return _failure(422, [problem])
    result = validate(doc)
    if result.errors:
        return _failure(422, result.errors, result.warnings)

    stem = upload_stem(file.filename)
    if not stem or stem.upper() in RESERVED_STEMS:
        return _failure(
            422, [Issue("$", f"'{file.filename}' does not give a usable file name")], result.warnings
        )
    folder = definitions_dir()
    folder.mkdir(parents=True, exist_ok=True)
    taken = {p.name.lower() for p in folder.iterdir()}
    conflict = _failure(409, [Issue("$", f"a definition named '{stem}' already exists")])
    if f"{stem}.json".lower() in taken:
        return conflict
    try:
        with open(folder / f"{stem}.json", "xb") as f:  # "x" never replaces an existing file
            f.write(raw)
    except FileExistsError:
        return conflict
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


async def analyse_definition(id: str, request: Request):
    _, result, failure = _load(id)
    if failure:
        return failure
    try:
        body = json.loads(await request.body())
    except (ValueError, RecursionError):
        return _failure(422, [Issue("$", "the body is not valid JSON")], result.warnings)
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


def create_app(web_dir: Path | str | None = None) -> FastAPI:
    """Build the application. `web_dir` is the folder served at `/`, default `web/`."""
    mimetypes.add_type("text/javascript", ".js")  # Windows registries may say text/plain
    app = FastAPI(title="ELA")
    app.add_exception_handler(RequestValidationError, _validation_failure)
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
