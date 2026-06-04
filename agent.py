"""Agentic AI contributor for Go OSS projects.

Usage:
  python agent.py --issue https://github.com/spf13/cobra/issues/<N>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / ".env")

from github_client import fetch_issue
from llm import GeminiAgent
from tools import fs as fs_tools
from tools import git as git_tools
from tools import runner as run_tools
from tools import search as search_tools
from workspace import ensure_repo, make_patch

MAX_ITERATIONS = int(os.environ.get("MAX_AGENT_ITERATIONS", "15"))
RATE_SLEEP_SEC = 13  # Gemini 2.5-flash free tier: 5 RPM; 13s = ~4.6 RPM (safe, retry handles spikes)


def build_dispatch(repo_dir: Path):
    """Map tool name → callable(args) → str. `repo_dir` is captured via closure."""
    def list_dir(args):
        return fs_tools.list_dir(repo_dir, args.get("path", "."))

    def read_file(args):
        return fs_tools.read_file(
            repo_dir,
            args["path"],
            int(args.get("line_start", 1)),
            int(args["line_end"]) if "line_end" in args and args["line_end"] is not None else None,
        )

    def grep(args):
        return search_tools.grep(repo_dir, args["pattern"], args.get("path", "."))

    def edit_file(args):
        return fs_tools.edit_file(repo_dir, args["path"], args["old_str"], args["new_str"])

    def git_diff(args):
        return git_tools.git_diff(repo_dir)

    def run_build(args):
        return run_tools.run_build(repo_dir)

    def run_tests(args):
        return run_tools.run_tests(repo_dir, args.get("package", "./..."))

    return {
        "list_dir": list_dir,
        "read_file": read_file,
        "grep": grep,
        "edit_file": edit_file,
        "git_diff": git_diff,
        "run_build": run_build,
        "run_tests": run_tests,
    }


def load_system_prompt() -> str:
    return (ROOT / "prompts" / "system.md").read_text(encoding="utf-8")


def first_user_message(issue) -> str:
    return (
        "Solve the following GitHub issue. Follow the workflow in the system prompt.\n\n"
        + issue.render()
    )


def run_agent(issue_url: str, log_path: Path) -> dict:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key or api_key == "your_gemini_key_here":
        raise SystemExit("GEMINI_API_KEY not set. Copy .env.example to .env and fill it in.")

    log_lines: list[str] = []

    def log(msg: str):
        print(msg, flush=True)
        log_lines.append(msg)

    log(f"[1/4] Fetching issue: {issue_url}")
    issue = fetch_issue(issue_url)
    log(f"      {issue.owner}/{issue.repo}#{issue.number}: {issue.title}")

    log(f"[2/4] Preparing workspace for {issue.owner}/{issue.repo} ...")
    repo_dir = ensure_repo(issue.owner, issue.repo, issue.number)
    log(f"      workspace: {repo_dir}")

    log(f"[3/4] Starting agent loop (max {MAX_ITERATIONS} iterations) ...")
    agent = GeminiAgent(api_key=api_key, system_prompt=load_system_prompt())
    dispatch = build_dispatch(repo_dir)

    pr_title = None
    pr_body = None
    next_message: object = first_user_message(issue)

    for step in range(1, MAX_ITERATIONS + 1):
        log(f"\n-- iteration {step} --")
        time.sleep(RATE_SLEEP_SEC)
        try:
            resp = agent.send(next_message)
        except Exception as e:
            log(f"LLM error: {e}")
            break

        if resp.text:
            log(f"agent: {resp.text[:500]}")

        if not resp.tool_calls:
            log("agent produced no tool call and no finish — ending loop.")
            break

        function_parts = []
        finished = False
        for call in resp.tool_calls:
            log(f"  -> tool: {call.name}({json.dumps(call.args)[:200]})")
            if call.name == "finish":
                pr_title = call.args.get("pr_title", "").strip()
                pr_body = call.args.get("pr_body", "").strip()
                log(f"  <- finish called. title: {pr_title!r}")
                finished = True
                break
            handler = dispatch.get(call.name)
            if handler is None:
                result = f"ERROR: unknown tool {call.name}"
            else:
                try:
                    result = handler(call.args)
                except Exception as e:
                    result = f"ERROR: tool raised: {e}"
            log(f"  <- {result[:300]}")
            function_parts.append(GeminiAgent.function_response_part(call.name, result))

        if finished:
            break
        next_message = function_parts

    log("\n[4/4] Writing output ...")
    out_dir = ROOT / "output" / f"{issue.repo}-{issue.number}"
    out_dir.mkdir(parents=True, exist_ok=True)

    patch_path = out_dir / "changes.patch"
    try:
        make_patch(repo_dir, patch_path)
        log(f"      wrote {patch_path}")
    except Exception as e:
        log(f"      WARN: could not write patch: {e}")

    summary_path = out_dir / "pr_summary.md"
    if pr_title or pr_body:
        summary_path.write_text(
            f"# {pr_title or '(no title)'}\n\n{pr_body or '(no body)'}\n",
            encoding="utf-8",
        )
        log(f"      wrote {summary_path}")
    else:
        summary_path.write_text(
            "# (agent did not call finish)\n\nThe agent exited without producing a PR summary.\n",
            encoding="utf-8",
        )
        log(f"      WARN: agent did not call finish; placeholder summary written")

    log_path.parent.mkdir(parents=True, exist_ok=True)
    log_path.write_text("\n".join(log_lines), encoding="utf-8")

    return {
        "issue": f"{issue.owner}/{issue.repo}#{issue.number}",
        "patch": str(patch_path),
        "summary": str(summary_path),
        "log": str(log_path),
        "finished": pr_title is not None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Agentic AI contributor for Go OSS projects.")
    parser.add_argument("--issue", required=True, help="GitHub issue URL")
    args = parser.parse_args()

    issue_number = args.issue.rstrip("/").rsplit("/", 1)[-1]
    log_path = ROOT / "output" / f"run-{issue_number}.log"

    result = run_agent(args.issue, log_path)
    print("\nDone.")
    for k, v in result.items():
        print(f"  {k}: {v}")
    return 0 if result["finished"] else 1


if __name__ == "__main__":
    sys.exit(main())
