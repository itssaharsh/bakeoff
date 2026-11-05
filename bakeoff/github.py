"""GitHub facts for a contest. GitHub is the source of truth; nothing is inferred by a model."""

from __future__ import annotations

import os
import re
import time
import subprocess
from dataclasses import dataclass, field

import httpx

from .donewhen import parse_done_when, parse_scope
from .matrix import PR, Matrix, Reading, build_matrix

API = "https://api.github.com"
_KEYWORD = r"\b(?:close[sd]?|fix(?:e[sd])?|resolve[sd]?)\s*:?\s+"
_REF = re.compile(_KEYWORD + r"(?:https://github\.com/(?P<urepo>[\w.-]+/[\w.-]+)/issues/|(?P<repo>[\w.-]+/[\w.-]+)?#)(?P<n>\d+)\b",
                  re.IGNORECASE)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_AGENT_TITLE = re.compile(r"^\s*\[([^\]]+)\]")
_AGENT_BODY = re.compile(r"^\s*(?:written by|agent)\s*:\s*(.+?)\s*$", re.IGNORECASE | re.MULTILINE)


def closed_issues(body: str | None, repo: str | None = None) -> set[int]:
    """Issue numbers in this repo that a PR body says it closes (comments ignored; other repos ignored)."""
    out: set[int] = set()
    for m in _REF.finditer(_COMMENT.sub("", body or "")):
        other = m.group("urepo") or m.group("repo")
        if other and repo and other.lower() != repo.lower():
            continue
        if m.group("urepo") and not repo:
            continue
        out.add(int(m.group("n")))
    return out


def closes_issue(body: str | None, issue: int, repo: str | None = None) -> bool:
    return issue in closed_issues(body, repo)


def agent_of(title: str, body: str | None) -> str:
    if m := _AGENT_TITLE.match(title or ""):
        return m.group(1).strip()
    if body and (m := _AGENT_BODY.search(body)):
        return m.group(1).strip()
    return ""


def ci_conclusion(check_runs: list[dict], statuses: list[dict]) -> tuple[str, list[str]]:
    """success | failure | pending | none, plus the names of failing checks.
    The newest run of each check name counts; a PR whose checks were all skipped has no result."""
    newest: dict[str, dict] = {}
    for r in check_runs:
        name = r.get("name", "check")
        if name not in newest or r.get("id", 0) >= newest[name].get("id", 0):
            newest[name] = r
    failing, pending, passed = [], False, False
    for name, r in newest.items():
        if r.get("status") != "completed":
            pending = True
        elif r.get("conclusion") in ("failure", "cancelled", "timed_out", "action_required", "startup_failure"):
            failing.append(name)
        elif r.get("conclusion") == "success":
            passed = True
    for s in statuses:
        if s.get("state") in ("failure", "error"):
            failing.append(s.get("context", "status"))
        elif s.get("state") == "pending":
            pending = True
        elif s.get("state") == "success":
            passed = True
    if failing:
        return "failure", failing
    if pending:
        return "pending", []
    return ("success", []) if passed else ("none", [])


def default_token() -> str:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    try:
        return subprocess.run(["gh", "auth", "token"], capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return ""


class GitHub:
    def __init__(self, repo: str, token: str | None = None, transport: httpx.BaseTransport | None = None):
        self.repo = repo
        tok = default_token() if token is None else token
        headers = {"Accept": "application/vnd.github+json", "X-GitHub-Api-Version": "2022-11-28",
                   "User-Agent": "bakeoff"}
        if tok:
            headers["Authorization"] = f"Bearer {tok}"
        self.http = httpx.Client(base_url=API, headers=headers, timeout=30, transport=transport)

    def _get(self, path: str, **params):
        for attempt in range(3):  # GitHub answers 5xx now and then; reads are safe to retry
            r = self.http.get(path, params=params or None)
            if r.status_code < 500:
                break
            time.sleep(1.5 * (attempt + 1))
        r.raise_for_status()
        return r.json()

    def issue(self, n: int) -> dict:
        return self._get(f"/repos/{self.repo}/issues/{n}")

    def open_pulls(self, max_pages: int = 10) -> list[dict]:
        out, url = [], f"/repos/{self.repo}/pulls"
        params = {"state": "open", "per_page": 100}
        for _ in range(max_pages):
            r = self.http.get(url, params=params)
            r.raise_for_status()
            out.extend(r.json())
            nxt = r.links.get("next", {}).get("url")
            if not nxt:
                break
            url, params = nxt, None
        return out

    def pull(self, n: int) -> dict:
        return self._get(f"/repos/{self.repo}/pulls/{n}")

    def pull_files(self, n: int) -> list[str]:
        return [f["filename"] for f in self._get(f"/repos/{self.repo}/pulls/{n}/files", per_page=100)]

    def ci(self, sha: str) -> tuple[str, list[str]]:
        runs = self._get(f"/repos/{self.repo}/commits/{sha}/check-runs", per_page=100).get("check_runs", [])
        statuses = self._get(f"/repos/{self.repo}/commits/{sha}/status").get("statuses", [])
        return ci_conclusion(runs, statuses)

    def diff(self, n: int, limit: int = 60_000) -> str:
        r = self.http.get(f"/repos/{self.repo}/pulls/{n}", headers={"Accept": "application/vnd.github.diff"})
        r.raise_for_status()
        text = r.text
        return text if len(text) <= limit else text[:limit] + f"\n… diff truncated at {limit} characters"

    def file_at(self, path: str, ref: str) -> str:
        import base64
        data = self._get(f"/repos/{self.repo}/contents/{path}", ref=ref)
        return base64.b64decode(data["content"]).decode("utf-8", "replace")

    # writes (used only by merge_pick)
    def merge(self, n: int, title: str, message: str, sha: str | None = None) -> dict:
        """Squash-merge; with sha, GitHub refuses (409) if the PR's head moved since it was read."""
        body = {"merge_method": "squash", "commit_title": title, "commit_message": message}
        if sha:
            body["sha"] = sha
        r = self.http.put(f"/repos/{self.repo}/pulls/{n}/merge", json=body)
        r.raise_for_status()
        return r.json()

    def comment(self, n: int, body: str) -> dict:
        r = self.http.post(f"/repos/{self.repo}/issues/{n}/comments", json={"body": body})
        r.raise_for_status()
        return r.json()

    def close_pull(self, n: int) -> dict:
        r = self.http.patch(f"/repos/{self.repo}/pulls/{n}", json={"state": "closed"})
        r.raise_for_status()
        return r.json()


@dataclass
class Contest:
    repo: str
    issue: int
    title: str
    url: str
    items: list[str]
    scope: list[str]
    prs: list[PR] = field(default_factory=list)

    def matrix(self, readings: list[Reading], agents: list[str] | None = None) -> Matrix:
        return build_matrix(self.issue, self.items, self.prs, readings, self.scope, agents)


def linked_open_pulls(gh: GitHub, issue: int) -> list[dict]:
    return [p for p in gh.open_pulls() if not p.get("draft") and closes_issue(p.get("body"), issue, gh.repo)]


def collect_contest(gh: GitHub, issue: int) -> Contest:
    iss = gh.issue(issue)
    prs = []
    for p in linked_open_pulls(gh, issue):
        n = p["number"]
        ci, failing = gh.ci(p["head"]["sha"])
        detail = gh.pull(n)
        prs.append(PR(number=n, title=p["title"], author=p["user"]["login"], url=p["html_url"], ci=ci,
                      failing_checks=failing, files=gh.pull_files(n), body=p.get("body") or "",
                      head_sha=p["head"]["sha"], mergeable=detail.get("mergeable"),
                      agent=agent_of(p["title"], p.get("body"))))
    return Contest(repo=gh.repo, issue=issue, title=iss.get("title", ""), url=iss.get("html_url", ""),
                   items=parse_done_when(iss.get("body")), scope=parse_scope(iss.get("body")),
                   prs=sorted(prs, key=lambda x: x.number))


def contested_issues(gh: GitHub, minimum: int = 2) -> dict[int, list[int]]:
    """Open issues that two or more open PRs say they close: {issue: [pr numbers]}."""
    found: dict[int, set[int]] = {}
    for p in gh.open_pulls():
        if p.get("draft"):
            continue
        for n in closed_issues(p.get("body"), gh.repo):
            found.setdefault(n, set()).add(p["number"])
    return {i: sorted(ps) for i, ps in found.items() if len(ps) >= minimum}
