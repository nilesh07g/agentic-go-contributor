"""Filesystem tools: list_dir, read_file, edit_file. Paths are repo-relative."""
from __future__ import annotations

from pathlib import Path

MAX_LIST_ENTRIES = 100
DEFAULT_READ_LINES = 200
LARGE_EDIT_LINES = 30
LARGE_EXPANSION_RATIO = 3.0


def _resolve(repo_root: Path, rel_path: str) -> Path:
    rel = (rel_path or ".").lstrip("/\\")
    p = (repo_root / rel).resolve()
    root = repo_root.resolve()
    if root != p and root not in p.parents:
        raise ValueError(f"path escapes repo root: {rel_path}")
    return p


def list_dir(repo_root: Path, path: str = ".") -> str:
    target = _resolve(repo_root, path)
    if not target.exists():
        return f"ERROR: path does not exist: {path}"
    if not target.is_dir():
        return f"ERROR: not a directory: {path}"

    entries = sorted(target.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower()))
    lines = []
    for i, e in enumerate(entries):
        if i >= MAX_LIST_ENTRIES:
            lines.append(f"... ({len(entries) - i} more entries truncated)")
            break
        suffix = "/" if e.is_dir() else ""
        lines.append(f"{e.name}{suffix}")
    if not lines:
        return f"(empty directory: {path})"
    return "\n".join(lines)


def read_file(repo_root: Path, path: str, line_start: int = 1, line_end: int | None = None) -> str:
    target = _resolve(repo_root, path)
    if not target.exists():
        return f"ERROR: file does not exist: {path}"
    if not target.is_file():
        return f"ERROR: not a file: {path}"

    try:
        text = target.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return f"ERROR: could not read file: {e}"

    lines = text.splitlines()
    total = len(lines)
    start = max(1, int(line_start))
    end = total if line_end is None else min(total, int(line_end))
    if end < start:
        return f"ERROR: line_end ({end}) < line_start ({start})"
    if line_end is None and total - start + 1 > DEFAULT_READ_LINES:
        end = start + DEFAULT_READ_LINES - 1

    out = [f"# {path} (lines {start}-{end} of {total})"]
    width = len(str(end))
    for i in range(start, end + 1):
        out.append(f"{str(i).rjust(width)}: {lines[i-1]}")
    if end < total:
        out.append(f"... ({total - end} more lines, call read_file with line_start={end+1} to continue)")
    return "\n".join(out)


def edit_file(repo_root: Path, path: str, old_str: str, new_str: str) -> str:
    target = _resolve(repo_root, path)
    if not target.exists():
        return f"ERROR: file does not exist: {path}"
    if not target.is_file():
        return f"ERROR: not a file: {path}"

    text = target.read_text(encoding="utf-8")
    count = text.count(old_str)
    if count == 0:
        return (
            f"ERROR: old_str not found in {path}. "
            "Read the file again to get the exact text including whitespace."
        )
    if count > 1:
        return (
            f"ERROR: old_str matches {count} places in {path}. "
            "Include more surrounding context to make it unique."
        )

    new_text = text.replace(old_str, new_str, 1)
    target.write_text(new_text, encoding="utf-8")

    removed = old_str.count("\n") + 1
    added = new_str.count("\n") + 1

    warnings: list[str] = []
    net_added = added - removed
    if net_added > LARGE_EDIT_LINES:
        warnings.append(
            f"net +{net_added} lines added — large edit. Confirm this is minimal and aligned with the issue."
        )
    old_size = max(len(old_str), 1)
    if len(new_str) > old_size * LARGE_EXPANSION_RATIO and added > 5:
        warnings.append(
            f"new_str is {len(new_str)/old_size:.1f}x the size of old_str — verify you're not over-expanding."
        )

    msg = f"OK: edited {path} (removed {removed} line(s), added {added} line(s))"
    if warnings:
        msg += "\nWARNING: " + " ".join(warnings) + " Call git_diff() to review."
    return msg
