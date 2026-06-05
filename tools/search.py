"""Grep tool. Uses Python re — no external dependency on ripgrep."""
from __future__ import annotations

import re
from pathlib import Path

from tools._paths import resolve

MAX_MATCHES = 50
SKIP_DIRS = {".git", "vendor", "node_modules", ".idea", ".vscode"}
TEXT_EXTENSIONS = {".go", ".md", ".mod", ".sum", ".yaml", ".yml", ".txt", ".json", ".toml"}


def grep(repo_root: Path, pattern: str, path: str = ".") -> str:
    try:
        regex = re.compile(pattern)
    except re.error as e:
        return f"ERROR: invalid regex {pattern!r}: {e}"

    try:
        start = resolve(repo_root, path)
    except ValueError as e:
        return f"ERROR: {e}"
    if not start.exists():
        return f"ERROR: path does not exist: {path}"

    matches: list[str] = []
    files_to_scan: list[Path] = []
    if start.is_file():
        files_to_scan = [start]
    else:
        for p in start.rglob("*"):
            if not p.is_file():
                continue
            if any(part in SKIP_DIRS for part in p.relative_to(repo_root).parts):
                continue
            if p.suffix.lower() not in TEXT_EXTENSIONS:
                continue
            files_to_scan.append(p)

    for fp in files_to_scan:
        try:
            with fp.open("r", encoding="utf-8", errors="replace") as f:
                for ln, line in enumerate(f, 1):
                    if regex.search(line):
                        rel_path = fp.relative_to(repo_root).as_posix()
                        matches.append(f"{rel_path}:{ln}: {line.rstrip()}")
                        if len(matches) >= MAX_MATCHES:
                            break
        except Exception:
            continue
        if len(matches) >= MAX_MATCHES:
            break

    if not matches:
        return f"(no matches for {pattern!r} under {path})"
    out = matches[:MAX_MATCHES]
    if len(matches) >= MAX_MATCHES:
        out.append(f"... (truncated at {MAX_MATCHES} matches; refine the pattern)")
    return "\n".join(out)
