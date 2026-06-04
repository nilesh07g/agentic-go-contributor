"""Fetch GitHub issues via the REST API."""
from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Optional

import requests


@dataclass
class Issue:
    number: int
    owner: str
    repo: str
    title: str
    body: str
    comments: list[str]
    url: str

    def render(self) -> str:
        parts = [
            f"Repo: {self.owner}/{self.repo}",
            f"Issue #{self.number}: {self.title}",
            f"URL: {self.url}",
            "",
            "Body:",
            self.body or "(no body)",
        ]
        if self.comments:
            parts.append("")
            parts.append("Comments:")
            for i, c in enumerate(self.comments, 1):
                parts.append(f"--- comment {i} ---")
                parts.append(c)
        return "\n".join(parts)


_ISSUE_URL_RE = re.compile(
    r"https?://github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/issues/(?P<number>\d+)"
)


def parse_issue_url(url: str) -> tuple[str, str, int]:
    m = _ISSUE_URL_RE.search(url)
    if not m:
        raise ValueError(f"Not a valid GitHub issue URL: {url}")
    return m["owner"], m["repo"], int(m["number"])


def fetch_issue(url: str, token: Optional[str] = None) -> Issue:
    owner, repo, number = parse_issue_url(url)
    token = token or os.environ.get("GITHUB_TOKEN")

    headers = {"Accept": "application/vnd.github+json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    api = f"https://api.github.com/repos/{owner}/{repo}/issues/{number}"
    r = requests.get(api, headers=headers, timeout=20)
    r.raise_for_status()
    data = r.json()

    comments: list[str] = []
    if data.get("comments", 0) > 0:
        c = requests.get(data["comments_url"], headers=headers, timeout=20)
        c.raise_for_status()
        for item in c.json():
            user = item.get("user", {}).get("login", "?")
            body = item.get("body", "") or ""
            comments.append(f"[{user}] {body}")

    return Issue(
        number=number,
        owner=owner,
        repo=repo,
        title=data.get("title", ""),
        body=data.get("body", "") or "",
        comments=comments,
        url=url,
    )
