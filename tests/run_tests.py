#!/usr/bin/env python3
"""Run the kanban-gantt backend tests cross-platform (Windows + Linux + macOS).

This is the Python twin of the old bash ``run_tests.sh``: it manages an
isolated test virtualenv (pytest + the same fastapi/httpx stack), points
``hermes_cli`` at the hermes-agent checkout via ``PYTHONPATH``, runs the
standalone ``move_integration.py`` script, then pytest. It uses only the
standard library plus (optionally) ``uv`` for fast venv/dependency handling,
so it works on any OS with no bash/POSIX assumptions.

Paths / env overrides (same contract as the shell version):
  HERMES_AGENT_HOME  — hermes-agent checkout containing hermes_cli/
                       (default: ~/.hermes/hermes-agent, then the repo sibling)
  PYTEST_PYTHON      — a python that already has the deps; skips venv mgmt
  KG_TEST_VENV       — where to put/reuse the test venv (default: <repo>/.test-venv)
"""

from __future__ import annotations

import importlib
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Every import the backend test path pulls in. Kept in one place so a new
# hermes_cli import shows up as a missing dep here instead of a stack trace.
# Importable modules (what the tests import) and the distribution names that
# provide them.
MODULES = ["pytest", "fastapi", "httpx", "uvicorn", "pydantic", "yaml", "ruamel.yaml"]
PKGS = ["pytest", "fastapi", "httpx", "uvicorn", "pydantic", "pyyaml", "ruamel.yaml"]

REPO_ROOT = Path(__file__).resolve().parent.parent


def _hermes_agent_home() -> Path:
    """The hermes-agent checkout holding hermes_cli/, or raise."""
    env = os.environ.get("HERMES_AGENT_HOME")
    cands = [env] if env else []
    # Two conventional layouts: ~/.hermes/hermes-agent, and the clone's sibling
    # under a/minus root that some setups use.
    home = Path.home()
    cands += [
        str(home / ".hermes" / "hermes-agent"),
        "/opt/data/git/hermes-agent",
    ]
    for c in cands:
        if c and (Path(c) / "hermes_cli").is_dir():
            return Path(c)
    raise SystemExit(
        "ERROR: hermes_cli not found. Set HERMES_AGENT_HOME to your "
        "hermes-agent checkout (a dir containing hermes_cli/)."
    )


def _venv_python(venv_dir: Path) -> Path:
    """Path to the venv's python, POSIX or Windows layout."""
    bin_dir = venv_dir / ("Scripts" if os.name == "nt" else "bin")
    exe = "python.exe" if os.name == "nt" else "python"
    return bin_dir / exe


def _has_modules(py: str) -> bool:
    """True iff every module in MODULES imports cleanly under ``py``."""
    probe = (
        "import importlib,sys\n"
        "for m in sys.argv[1].split(): importlib.import_module(m)\n"
    )
    try:
        r = subprocess.run(
            [py, "-c", probe, " ".join(MODULES)],
            capture_output=True,
            text=True,
        )
        return r.returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def _resolve_python(agent_home: Path) -> str:
    """Pick the interpreter to run pytest with.

    1. PYTEST_PYTHON wins (caller supplies a ready python). 2. A test venv is
    created/updated with uv (fast) or stdlib venv + pip, installing PKGS. 3. If
    the venv still lacks deps, borrow the hermes-agent venv's site-packages via
    PYTHONPATH (pure-python deps import across interpreters; compiled ones are
    reported, not faked).
    """
    env_py = os.environ.get("PYTEST_PYTHON")
    if env_py:
        if not _has_modules(env_py):
            print(
                f"warning: PYTEST_PYTHON ({env_py}) missing some deps; "
                "will try to borrow from hermes-agent.", file=sys.stderr,
            )
        return env_py

    venv_dir = Path(os.environ.get("KG_TEST_VENV", str(REPO_ROOT / ".test-venv")))
    py = str(_venv_python(venv_dir))
    needs_install = not _has_modules(py)
    uv = shutil.which("uv")
    if uv:
        if not venv_dir.exists():
            print("Creating test venv with uv...", file=sys.stderr)
            _run([uv, "venv", str(venv_dir), "--python", "3.13"])
        if needs_install:
            print("Installing test deps with uv...", file=sys.stderr)
            _run([uv, "pip", "install", "--python", py, *PKGS])
    else:
        # stdlib venv + pip fallback (slower, needs a system python).
        if not venv_dir.exists():
            python = sys.executable or shutil.which("python")
            if not python:
                raise SystemExit("ERROR: no python found and no uv available")
            print("Creating test venv with python -m venv...", file=sys.stderr)
            _run([python, "-m", "venv", str(venv_dir)])
        if needs_install:
            print("Installing test deps with pip...", file=sys.stderr)
            _run([py, "-m", "pip", "install", "--upgrade", "pip"])
            _run([py, "-m", "pip", "install", *PKGS])

    # Last resort: borrow deps from the hermes-agent venv via PYTHONPATH.
    if not _has_modules(py):
        for site in sorted((agent_home / "venv" / "lib").glob("python*/site-packages")):
            os.environ["PYTHONPATH"] = os.pathsep.join(
                [str(agent_home), str(site)] + os.environ.get("PYTHONPATH", "").split(os.pathsep)
            )
            if _has_modules(py):
                print(f"note: borrowed missing deps from {site}", file=sys.stderr)
                break
        else:
            raise SystemExit(
                "ERROR: test interpreter has none of: %s. Retry with network "
                "(uv pip install), or set PYTEST_PYTHON to a python that has them."
                % " ".join(MODULES)
            )
    return py


def _run(cmd: list[str]) -> None:
    print("+ " + " ".join(cmd), file=sys.stderr)
    subprocess.run(cmd, check=True)


def main() -> int:
    agent_home = _hermes_agent_home()
    os.environ.setdefault("PYTHONPATH", str(agent_home))
    py = _resolve_python(agent_home)

    # The move test is a standalone script — its own temp kanban home, real
    # board DBs and real blob files — so pytest never collects it. Run it
    # explicitly: it is where the cross-board attachment-path assertions live.
    # It asserts; a non-zero exit stops the suite here.
    move = REPO_ROOT / "tests" / "move_integration.py"
    prev = os.environ.get("PYTHONPATH", "")
    os.environ["PYTHONPATH"] = os.pathsep.join(
        [str(REPO_ROOT / "dashboard"), prev]
    )
    try:
        _run([py, str(move)])
    finally:
        os.environ["PYTHONPATH"] = prev

    # Clean the env vars that would pin/contaminate the sandbox.
    for var in ("HERMES_DELEGATED_CHILD_CONTEXT", "HERMES_KANBAN_DB", "HERMES_KANBAN_BOARD"):
        os.environ.pop(var, None)

    args = ["-m", "pytest", str(REPO_ROOT / "tests"), *sys.argv[1:]]
    return subprocess.call([py, *args])


if __name__ == "__main__":
    sys.exit(main())
