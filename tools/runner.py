"""Run Go build and tests inside the workspace repo."""
from __future__ import annotations

from pathlib import Path

from tools._proc import run_capture
from tools._text import truncate

MAX_OUTPUT_CHARS = 4000
BUILD_TIMEOUT = 120
TEST_TIMEOUT = 240


def run_build(repo_root: Path) -> str:
    code, out = run_capture(["go", "build", "./..."], repo_root, BUILD_TIMEOUT, MAX_OUTPUT_CHARS)
    if code == 0:
        return "BUILD OK"
    return f"BUILD FAILED (exit {code}):\n{out}"


def run_tests(repo_root: Path, package: str = "./...") -> str:
    code, out = run_capture(["go", "test", "-count=1", package], repo_root, TEST_TIMEOUT, MAX_OUTPUT_CHARS)
    if code == 0:
        return f"TESTS PASS ({package}):\n{truncate(out, 1500)}"
    return f"TESTS FAILED ({package}, exit {code}):\n{out}"
