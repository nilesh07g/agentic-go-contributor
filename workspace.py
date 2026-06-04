"""Clone/reset the target Go repo under ./workspaces/<repo>."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

WORKSPACES = Path(__file__).parent / "workspaces"


def _run(cmd: list[str], cwd: Path) -> str:
    result = subprocess.run(
        cmd, cwd=cwd, capture_output=True, text=True, check=False
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"command failed: {' '.join(cmd)}\nstdout: {result.stdout}\nstderr: {result.stderr}"
        )
    return result.stdout


def ensure_repo(owner: str, repo: str, issue_number: int) -> Path:
    """Clone the repo if missing, reset to clean upstream main, create a fresh issue branch.

    Returns the absolute path to the working tree.
    """
    WORKSPACES.mkdir(exist_ok=True)
    repo_dir = WORKSPACES / repo
    remote = f"https://github.com/{owner}/{repo}.git"

    if not repo_dir.exists():
        _run(["git", "clone", "--depth", "50", remote, str(repo_dir)], cwd=WORKSPACES)
    else:
        try:
            _run(["git", "reset", "--hard"], cwd=repo_dir)
            _run(["git", "clean", "-fd"], cwd=repo_dir)
            _run(["git", "fetch", "origin"], cwd=repo_dir)
        except RuntimeError:
            shutil.rmtree(repo_dir)
            _run(["git", "clone", "--depth", "50", remote, str(repo_dir)], cwd=WORKSPACES)

    default_branch = _detect_default_branch(repo_dir)
    _run(["git", "checkout", default_branch], cwd=repo_dir)
    _run(["git", "reset", "--hard", f"origin/{default_branch}"], cwd=repo_dir)

    branch = f"agent/issue-{issue_number}"
    try:
        _run(["git", "branch", "-D", branch], cwd=repo_dir)
    except RuntimeError:
        pass
    _run(["git", "checkout", "-b", branch], cwd=repo_dir)

    return repo_dir


def _detect_default_branch(repo_dir: Path) -> str:
    out = _run(["git", "remote", "show", "origin"], cwd=repo_dir)
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("HEAD branch:"):
            return line.split(":", 1)[1].strip()
    return "main"


def make_patch(repo_dir: Path, out_path: Path) -> None:
    """Write `git diff` of all uncommitted changes to out_path."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    _run(["git", "add", "-A"], cwd=repo_dir)
    result = subprocess.run(
        ["git", "diff", "--cached"], cwd=repo_dir, capture_output=True, text=True, check=True
    )
    out_path.write_text(result.stdout, encoding="utf-8")
