"""Git-based self-review tool for the agent."""
from __future__ import annotations

import subprocess
from pathlib import Path

MAX_DIFF_CHARS = 3000


def _truncate(s: str, limit: int = MAX_DIFF_CHARS) -> str:
    if len(s) <= limit:
        return s
    head = s[: limit // 2]
    tail = s[-limit // 2 :]
    return f"{head}\n... (truncated {len(s) - limit} chars; diff is large — consider shrinking the edit) ...\n{tail}"


def git_diff(repo_root: Path) -> str:
    """Return the current unsteged + staged diff in the workspace."""
    try:
        r = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
            timeout=30,
        )
    except (subprocess.TimeoutExpired, FileNotFoundError) as e:
        return f"ERROR: could not run git diff: {e}"

    out = r.stdout or ""
    if not out.strip():
        return "(no changes yet — no edits have been made)"

    files_changed = sum(1 for line in out.splitlines() if line.startswith("diff --git "))
    additions = sum(1 for line in out.splitlines() if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in out.splitlines() if line.startswith("-") and not line.startswith("---"))

    header = f"Diff summary: {files_changed} file(s) changed, +{additions} -{deletions} lines\n\n"
    return header + _truncate(out)
