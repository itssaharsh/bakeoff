"""Bakeoff MCP server: the tools Switch agents use in a contest room.

Every agent gets the reading tools. Only an agent started with BAKEOFF_ALLOW_MERGE=1
gets merge_pick, so the agents that judge cannot merge and the agent that merges does
not judge. The agent's own name comes from BAKEOFF_AGENT, never from a tool argument.
"""

from __future__ import annotations

import os

from mcp.server.mcpserver import MCPServer

from .github import GitHub, collect_contest
from .matrix import VERDICTS, render_text
from .pick import PickRefused, merge_pick as _merge_pick
from .state import Store

mcp = MCPServer("bakeoff")


def _safe(fn):
    """Return GitHub and input errors to the agent as one readable line instead of a stack trace."""
    import functools

    import httpx

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except httpx.HTTPStatusError as e:
            code = e.response.status_code
            what = {404: "not found (check owner/name and the number)", 401: "GitHub token rejected",
                    403: "GitHub refused (token scope or rate limit)"}.get(code, f"GitHub error {code}")
            return f"ERROR: {e.request.method} {e.request.url.path}: {what}."
        except (httpx.HTTPError, ValueError, KeyError) as e:
            return f"ERROR: {type(e).__name__}: {e}"
    return wrapper


MERGE = os.environ.get("BAKEOFF_ALLOW_MERGE") == "1"


def _reader_tool(fn):
    """Register a reading tool, except on the merge agent, which gets merge_pick alone."""
    return fn if MERGE else mcp.tool()(fn)


def _agent() -> str:
    return os.environ.get("BAKEOFF_AGENT", "unknown-agent")


def _readers() -> list[str] | None:
    raw = os.environ.get("BAKEOFF_READERS", "")
    return [a.strip() for a in raw.split(",") if a.strip()] or None


@_reader_tool
@_safe
def done_when(repo: str, issue: int) -> str:
    """The issue's Done-when checklist, numbered from 1, as code reads it from the issue body."""
    c = collect_contest(GitHub(repo), issue)
    if not c.items:
        return f"#{issue} has no Done-when or Acceptance checklist; read against the issue text instead.\n\n{c.title}"
    return f"#{issue} {c.title}\n" + "\n".join(f"{i}. {t}" for i, t in enumerate(c.items, 1))


@_reader_tool
@_safe
def contest_matrix(repo: str, issue: int) -> str:
    """The contest matrix: one column per open PR closing the issue. CI, files and scope come from GitHub;
    checklist cells come from the readers' recorded verdicts (yes / NO / SPLIT / 1/2 waiting / - unread)."""
    c = collect_contest(GitHub(repo), issue)
    if not c.prs:
        return f"No open pull requests close #{issue} in {repo}."
    m = c.matrix(Store().readings(repo, issue), _readers())
    lines = [render_text(m), "", "PRs:"]
    lines += [f"#{p.number} {p.title} by @{p.author} ({p.agent or 'agent not stated'}) {p.url}" for p in c.prs]
    return "\n".join(lines)


@_reader_tool
@_safe
def pr_diff(repo: str, pr: int) -> str:
    """The unified diff of one PR (truncated for very large PRs)."""
    return GitHub(repo).diff(pr)


@_reader_tool
@_safe
def record_readings(repo: str, issue: int, pr: int, readings: list[dict]) -> str:
    """Record your verdict on each Done-when item for one PR.
    readings: [{"item": 1, "verdict": "met" | "unmet" | "unclear", "evidence": "file.py:41 returns None on an empty body"}]
    Items are numbered from 1 as done_when lists them. Cite file:line from the diff as evidence."""
    c = collect_contest(GitHub(repo), issue)
    head = next((p.head_sha for p in c.prs if p.number == pr), None)
    if head is None:
        return f"Nothing recorded: #{pr} is not an open PR closing #{issue} (" + \
            ", ".join(f"#{p.number}" for p in c.prs) + ")."
    rows = []
    for r in readings:
        verdict = str(r.get("verdict", "")).lower().strip()
        try:
            item = int(r.get("item"))
        except (TypeError, ValueError):
            return f"Nothing recorded: every reading needs an item number from 1 to {len(c.items)}."
        if verdict not in VERDICTS:
            return f"Nothing recorded: verdict must be one of {VERDICTS}, got {verdict!r}."
        if not 1 <= item <= max(len(c.items), 1):
            return f"Nothing recorded: item {item} is out of range (the checklist has {len(c.items)} items)."
        rows.append((item - 1, verdict, str(r.get("evidence", ""))))
    store, agent = Store(), _agent()
    for item, verdict, evidence in rows:
        store.add_reading(repo, issue, agent, pr, item, verdict, evidence, sha=head)
    return f"Recorded {len(rows)} verdicts from {agent} for #{pr} on #{issue} (commit {head[:7]})."


if MERGE:
    @mcp.tool()
    @_safe
    def merge_pick(repo: str, issue: int, pr: int, decided_by: str) -> str:
        """Merge the PR a maintainer picked and post a reasoned note on every other PR in the contest.
        Call only when a maintainer has named the PR in the room; decided_by is that maintainer's name.
        Refuses when the contest is already decided, the PR is not in it, or its CI has not passed."""
        gh = GitHub(repo)
        try:
            return _merge_pick(gh, Store(), collect_contest(gh, issue), pr, decided_by, _readers())
        except PickRefused as e:
            return f"REFUSED: {e}"


def run() -> None:
    mcp.run()


if __name__ == "__main__":
    run()
