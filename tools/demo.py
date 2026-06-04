"""Behavioral verification tools.

The agent can write a small standalone program that exercises the buggy feature,
then run it to compare observable behavior before and after a fix. This catches
classes of incomplete fixes that build + existing tests would miss.
"""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

DEMO_DIR_NAME = "agent_demo"
MAX_OUTPUT_CHARS = 4000
RUN_TIMEOUT = 60
_SAFE_NAME = re.compile(r"^[A-Za-z0-9_]+\.go$")


def _truncate(s: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(s) <= limit:
        return s
    head = s[: limit // 2]
    tail = s[-limit // 2 :]
    return f"{head}\n... (truncated {len(s) - limit} chars) ...\n{tail}"


def _demo_dir(repo_root: Path) -> Path:
    """Demo programs live in a sibling directory of the repo workspace.

    Using a sibling (not a subdirectory of the repo) avoids accidentally
    polluting the agent's git_diff with demo files and keeps the repo clean.
    """
    return repo_root.parent / f"{repo_root.name}__{DEMO_DIR_NAME}"


def write_demo(repo_root: Path, name: str, content: str) -> str:
    """Write a Go program that exercises the issue.

    The file lives in a sibling directory (not inside the repo) and uses a
    go.mod with `replace` pointing at the repo so the demo always links the
    current patched code.
    """
    if not _SAFE_NAME.match(name):
        return f"ERROR: name must match [A-Za-z0-9_]+.go (got {name!r})"

    ddir = _demo_dir(repo_root)
    ddir.mkdir(parents=True, exist_ok=True)

    # Detect the repo's go module so the demo can import its packages.
    go_mod_path = repo_root / "go.mod"
    module_path = None
    if go_mod_path.is_file():
        for line in go_mod_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line.startswith("module "):
                module_path = line.split(None, 1)[1].strip()
                break

    demo_mod = ddir / "go.mod"
    if module_path:
        rel_repo = "../" + repo_root.name
        demo_mod.write_text(
            f"module {DEMO_DIR_NAME}\n\n"
            f"go 1.21\n\n"
            f"require {module_path} v0.0.0\n\n"
            f"replace {module_path} => {rel_repo}\n",
            encoding="utf-8",
        )
    else:
        demo_mod.write_text(f"module {DEMO_DIR_NAME}\n\ngo 1.21\n", encoding="utf-8")

    (ddir / name).write_text(content, encoding="utf-8")
    return f"OK: wrote demo {name} ({len(content)} chars). Linked module: {module_path or '(none detected)'}. Call run_demo({name!r}) to execute."


def run_demo(repo_root: Path, name: str) -> str:
    """Build and run the demo program. Returns combined stdout+stderr."""
    if not _SAFE_NAME.match(name):
        return f"ERROR: name must match [A-Za-z0-9_]+.go (got {name!r})"

    ddir = _demo_dir(repo_root)
    target = ddir / name
    if not target.is_file():
        return f"ERROR: demo not found: {name}. Call write_demo first."

    # `go mod tidy` so the demo picks up the repo's transitive deps.
    tidy = subprocess.run(
        ["go", "mod", "tidy"], cwd=ddir, capture_output=True, text=True, timeout=120
    )
    if tidy.returncode != 0:
        return f"ERROR: go mod tidy failed:\n{_truncate(tidy.stdout + tidy.stderr)}"

    try:
        r = subprocess.run(
            ["go", "run", name],
            cwd=ddir,
            capture_output=True,
            text=True,
            timeout=RUN_TIMEOUT,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return f"TIMEOUT after {RUN_TIMEOUT}s running demo {name}"
    except FileNotFoundError as e:
        return f"ERROR: go not found: {e}"

    out = (r.stdout or "") + (r.stderr or "")
    status = "OK" if r.returncode == 0 else f"EXIT {r.returncode}"
    return f"DEMO {status}:\n{_truncate(out)}"
