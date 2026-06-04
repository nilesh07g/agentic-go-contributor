"""Gemini function-calling declarations for each agent tool."""
from __future__ import annotations

import google.generativeai as genai
from google.generativeai.types import content_types

FunctionDeclaration = content_types.protos.FunctionDeclaration
Schema = content_types.protos.Schema
Type = content_types.protos.Type


def _str(desc: str) -> Schema:
    return Schema(type=Type.STRING, description=desc)


def _int(desc: str) -> Schema:
    return Schema(type=Type.INTEGER, description=desc)


def tool_declarations() -> list[FunctionDeclaration]:
    return [
        FunctionDeclaration(
            name="list_dir",
            description="List entries in a directory relative to the repo root. Use to explore project layout.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={"path": _str("Repo-relative path, e.g. '.', 'cmd', 'internal/foo'")},
                required=["path"],
            ),
        ),
        FunctionDeclaration(
            name="read_file",
            description="Read a file from the repo. Default reads first 200 lines; pass line_start/line_end for a slice.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "path": _str("Repo-relative file path"),
                    "line_start": _int("1-indexed start line (optional, default 1)"),
                    "line_end": _int("1-indexed end line (optional)"),
                },
                required=["path"],
            ),
        ),
        FunctionDeclaration(
            name="grep",
            description="Search for a regex pattern in source files. Use to locate symbols, error strings, or related code.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "pattern": _str("Python regex pattern (e.g. 'AddCommand', 'panic.*nil')"),
                    "path": _str("Optional repo-relative directory or file to limit the search to. Default '.'."),
                },
                required=["pattern"],
            ),
        ),
        FunctionDeclaration(
            name="edit_file",
            description="Replace exactly one occurrence of old_str with new_str in a file. Fails if old_str is not unique.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "path": _str("Repo-relative file path to edit"),
                    "old_str": _str("Exact text to find (include enough surrounding lines to be unique)"),
                    "new_str": _str("Replacement text"),
                },
                required=["path", "old_str", "new_str"],
            ),
        ),
        FunctionDeclaration(
            name="git_diff",
            description="Show the current uncommitted diff in the workspace. Call AFTER editing and BEFORE validation to self-review your patch: did you touch only the files you planned? Is it minimal? Any whitespace churn?",
            parameters=Schema(type=Type.OBJECT, properties={}),
        ),
        FunctionDeclaration(
            name="run_build",
            description="Run 'go build ./...' in the repo. Use after editing to confirm code compiles.",
            parameters=Schema(type=Type.OBJECT, properties={}),
        ),
        FunctionDeclaration(
            name="run_tests",
            description="Run 'go test' in the repo. Pass a package path or default './...' for the full suite.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={"package": _str("Go package path, default './...'")},
            ),
        ),
        FunctionDeclaration(
            name="finish",
            description="Call when the fix is complete and validated. Provide a concise PR title and a markdown PR body.",
            parameters=Schema(
                type=Type.OBJECT,
                properties={
                    "pr_title": _str("Conventional PR title, <= 72 chars"),
                    "pr_body": _str("Markdown body: Problem / Fix / Test Plan sections"),
                },
                required=["pr_title", "pr_body"],
            ),
        ),
    ]
