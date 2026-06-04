"""Repo-rooted path resolution with escape-safety check."""
from __future__ import annotations

from pathlib import Path


def resolve(repo_root: Path, rel_path: str) -> Path:
    """Resolve `rel_path` against `repo_root` and ensure it stays inside the repo.

    Strips leading slashes from `rel_path` so that absolute-looking inputs
    (`/foo`, `\\foo`) are treated as relative. Raises `ValueError` if the
    resolved path lives outside `repo_root` — callers that prefer an error
    string should catch the exception at the call site.
    """
    rel = (rel_path or ".").lstrip("/\\")
    p = (repo_root / rel).resolve()
    root = repo_root.resolve()
    if root != p and root not in p.parents:
        raise ValueError(f"path escapes repo root: {rel_path}")
    return p
