"""Run Go build and tests inside the workspace repo."""
from __future__ import annotations

import subprocess
from pathlib import Path

MAX_OUTPUT_CHARS = 4000
BUILD_TIMEOUT = 120
TEST_TIMEOUT = 240


def _truncate(s: str, limit: int = MAX_OUTPUT_CHARS) -> str:
    if len(s) <= limit:
        return s
    head = s[: limit // 2]
    tail = s[-limit // 2 :]
    return f"{head}\n... (truncated {len(s) - limit} chars) ...\n{tail}"


def _run(cmd: list[str], cwd: Path, timeout: int) -> tuple[int, str]:
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return 1, f"TIMEOUT after {timeout}s running: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 1, f"ERROR: command not found: {e}"
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, _truncate(out)


def run_build(repo_root: Path) -> str:
    code, out = _run(["go", "build", "./..."], repo_root, BUILD_TIMEOUT)
    if code == 0:
        return "BUILD OK"
    return f"BUILD FAILED (exit {code}):\n{out}"


def run_tests(repo_root: Path, package: str = "./...") -> str:
    code, out = _run(["go", "test", "-count=1", package], repo_root, TEST_TIMEOUT)
    if code == 0:
        return f"TESTS PASS ({package}):\n{_truncate(out, 1500)}"
    return f"TESTS FAILED ({package}, exit {code}):\n{out}"
