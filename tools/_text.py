"""Shared text utilities for agent tools."""
from __future__ import annotations


def truncate(s: str, limit: int, note: str = "") -> str:
    """Truncate s to ~limit chars by keeping the head and the tail halves.

    A marker line is inserted between the kept halves. The optional `note`
    appears inside the marker so callers can hint at *why* the text is long
    (for example: "diff is large — consider shrinking the edit").
    """
    if len(s) <= limit:
        return s
    head = s[: limit // 2]
    tail = s[-limit // 2 :]
    extra = f"; {note}" if note else ""
    return f"{head}\n... (truncated {len(s) - limit} chars{extra}) ...\n{tail}"
