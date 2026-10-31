"""Helpers for the cases that follow the README: parse it, copy the repository, run its commands.

Not a test module. `TC-DOC-*`, `TC-SYS-040`, `TC-SYS-043` and `TC-ACC-007` use it.
"""

import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
README = REPO / "README.md"
START_MARKER = "uvicorn ela.api:app"


def readme_text():
    return README.read_text("utf-8")


def sections(text=None):
    """Level-2 sections of the README: heading text to the body below it, up to the next `## `."""
    text = readme_text() if text is None else text
    found = {}
    parts = re.split(r"^## (.+)$", text, flags=re.MULTILINE)
    for heading, body in zip(parts[1::2], parts[2::2], strict=True):
        found[heading.strip()] = body
    return found


def section(word, text=None):
    """(heading, body) of the first level-2 section whose heading holds `word`, ignoring case."""
    for heading, body in sections(text).items():
        if word.lower() in heading.lower():
            return heading, body
    raise KeyError(word)


def fenced_blocks(body):
    """(language, text) of each fenced block in `body`."""
    return [(lang, code) for lang, code in re.findall(r"^```(\w*)\n(.*?)^```", body, re.MULTILINE | re.DOTALL)]


def fenced_commands(body):
    """Each command line in the `sh` blocks of `body`, in order. Other blocks are not run."""
    commands = []
    for lang, code in fenced_blocks(body):
        if lang == "sh":
            commands += [line.strip() for line in code.splitlines() if line.strip()]
    return commands


def is_start_command(command):
    return START_MARKER in command


def documented_address():
    """The local address the running section gives, as `http://host:port`."""
    _, body = section("Running")
    match = re.search(r"http://127\.0\.0\.1:(\d+)", body)
    assert match, "the running section gives no local address"
    return match.group(0)


def clean_env(**extra):
    """The environment of a user's shell: nothing from this test run's virtual environment."""
    env = {
        k: v
        for k, v in os.environ.items()
        if k not in ("VIRTUAL_ENV", "ELA_DEFINITIONS_DIR", "UV_PROJECT_ENVIRONMENT")
        and not k.startswith("PYTEST_")
    }
    env.update(extra)
    return env


def snapshot(dest):
    """Copy the repository as a checkout would hold it, tracked files and new unignored ones."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "--cached", "--others", "--exclude-standard"],
        cwd=REPO,
        capture_output=True,
        check=True,
    ).stdout
    dest = Path(dest)
    for name in listing.decode("utf-8").split("\0"):
        source = REPO / name
        if name and source.is_file():
            target = dest / name
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
    return dest


def run_command(command, cwd, timeout=600):
    """Run one documented command line without a shell and return the finished process."""
    return subprocess.run(
        shlex.split(command),
        cwd=cwd,
        env=clean_env(),
        capture_output=True,
        encoding="utf-8",
        errors="replace",
        timeout=timeout,
        check=False,
    )


def free_port():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def stop_tree(proc):
    """Stop a process and everything it started. `uv run` starts the server as a child."""
    if proc.poll() is None:
        if sys.platform == "win32":
            subprocess.run(
                ["taskkill", "/F", "/T", "/PID", str(proc.pid)], capture_output=True, check=False
            )
        else:
            proc.terminate()
        try:
            proc.wait(timeout=15)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()


class DocumentedServer:
    """The README's start command, run in `cwd` with a free port added."""

    def __init__(self, cwd, log_path):
        _, body = section("Running")
        (command,) = [c for c in fenced_commands(body) if is_start_command(c)]
        self.port = free_port()
        self.url = f"http://127.0.0.1:{self.port}"
        self.log_path = Path(log_path)
        self.log = self.log_path.open("wb")
        self.proc = subprocess.Popen(
            [*shlex.split(command), "--port", str(self.port)],
            cwd=cwd,
            env=clean_env(),
            stdout=self.log,
            stderr=subprocess.STDOUT,
        )
        deadline = time.monotonic() + 90
        while True:
            try:
                urllib.request.urlopen(self.url + "/api/definitions", timeout=1).close()
                return
            except OSError:
                if self.proc.poll() is not None or time.monotonic() > deadline:
                    self.stop()
                    raise RuntimeError("the documented command did not start the server") from None
                time.sleep(0.2)

    def output(self):
        self.log.flush()
        return self.log_path.read_text("utf-8", errors="replace")

    def stop(self):
        stop_tree(self.proc)
        self.log.close()
