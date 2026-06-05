"""Shared subprocess wrapper for tools that capture command output."""
from __future__ import annotations

import subprocess
from pathlib import Path

from tools._text import truncate


def run_capture(
    cmd: list[str],
    cwd: Path,
    timeout: int,
    max_chars: int,
) -> tuple[int, str]:
    """Run `cmd` in `cwd`, capture stdout+stderr, return (exit_code, output).

    Handles the two common subprocess failure modes:
      - TimeoutExpired → returns exit 1 with a TIMEOUT marker
      - FileNotFoundError → returns exit 1 with an ERROR marker
    Output is truncated to `max_chars` to keep tool returns bounded.
    """
    try:
        r = subprocess.run(
            cmd, cwd=cwd, capture_output=True, text=True, timeout=timeout, check=False
        )
    except subprocess.TimeoutExpired:
        return 1, f"TIMEOUT after {timeout}s running: {' '.join(cmd)}"
    except FileNotFoundError as e:
        return 1, f"ERROR: command not found: {e}"
    out = (r.stdout or "") + (r.stderr or "")
    return r.returncode, truncate(out, max_chars)
