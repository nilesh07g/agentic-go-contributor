"""Git-based self-review tool for the agent."""
from __future__ import annotations

from pathlib import Path

from tools._proc import run_capture
from tools._text import truncate

MAX_DIFF_CHARS = 3000
DIFF_RAW_CHARS = 50_000  # keep raw diff long enough to count lines accurately


def git_diff(repo_root: Path) -> str:
    """Return the current unstaged + staged diff in the workspace."""
    code, out = run_capture(["git", "diff", "HEAD"], repo_root, timeout=30, max_chars=DIFF_RAW_CHARS)
    if code != 0:
        return f"ERROR: could not run git diff:\n{out}"
    if not out.strip():
        return "(no changes yet — no edits have been made)"

    files_changed = sum(1 for line in out.splitlines() if line.startswith("diff --git "))
    additions = sum(1 for line in out.splitlines() if line.startswith("+") and not line.startswith("+++"))
    deletions = sum(1 for line in out.splitlines() if line.startswith("-") and not line.startswith("---"))

    header = f"Diff summary: {files_changed} file(s) changed, +{additions} -{deletions} lines\n\n"
    return header + truncate(out, MAX_DIFF_CHARS, note="diff is large — consider shrinking the edit")
