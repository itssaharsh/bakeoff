"""The intake watcher: one Switch room per contested issue, opened by code.

Polls each repository for issues that two or more open PRs say they close. For a
new contest it creates the room from the Bakeoff template and posts the matrix.
For an open contest it posts again only when GitHub's facts change (a new PR,
CI finishing). It never posts twice for the same facts and never touches a
decided contest.
"""

from __future__ import annotations

import hashlib
import logging
import os
import time

from .github import Contest, GitHub, collect_contest, contested_issues
from .matrix import render_text
from .state import Store
from .switch_api import Switch

log = logging.getLogger("bakeoff.watch")


def candidates_text(c: Contest) -> str:
    return "\n".join(f"- #{p.number} {p.title} by @{p.author}" + (f" (written by {p.agent})" if p.agent else "")
                     + f": {p.url}" for p in c.prs)


def facts_fingerprint(c: Contest) -> str:
    raw = "|".join(f"{p.number}:{p.ci}:{','.join(p.failing_checks)}:{p.head_sha}" for p in c.prs)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def readers() -> list[str]:
    raw = os.environ.get("BAKEOFF_READERS", "bakeoff-checker,bakeoff-second")
    return [a.strip() for a in raw.split(",") if a.strip()]


def tick(gh: GitHub, switch: Switch, store: Store, maintainer: str, only: set[int] | None = None) -> list[str]:
    """One pass over one repository. Returns what it did, for the log."""
    did: list[str] = []
    for issue, prs in sorted(contested_issues(gh).items()):
        if only and issue not in only:
            continue
        state = store.contest(gh.repo, issue) or {}
        if state.get("winner"):
            continue
        c = collect_contest(gh, issue)
        if len(c.prs) < 2:
            continue
        fp = facts_fingerprint(c)
        m = c.matrix(store.readings(gh.repo, issue), readers())
        if not state.get("room_id"):
            room = switch.create_room_from_template({
                "repo": gh.repo, "issue": issue, "issue_title": c.title,
                "candidates": candidates_text(c), "maintainer": maintainer,
            })
            store.open_contest(gh.repo, issue, room_id=room, prs=[p.number for p in c.prs])
            state = store.contest(gh.repo, issue) or {}
            did.append(f"opened room {room} for #{issue}")
        if not state.get("fingerprint"):
            switch.post(state["room_id"], f"Contest opened by code: {len(c.prs)} open PRs close {gh.repo}#{issue}. "
                                          "Facts from GitHub below; readings fill in as the readers record them.\n"
                                          + render_text(m))
            store.note(gh.repo, issue, fingerprint=fp)
            if not did or not did[-1].startswith("opened"):
                did.append(f"posted the opening matrix for #{issue}")
        elif state.get("fingerprint") != fp:
            new = sorted(set(p.number for p in c.prs) - set(state.get("prs", [])))
            store.set_prs(gh.repo, issue, [p.number for p in c.prs])
            what = f"New candidate(s): {', '.join(f'#{n}' for n in new)}. " if new else "GitHub's facts changed. "
            switch.post(state["room_id"], what + "Updated matrix:\n" + render_text(m))
            store.note(gh.repo, issue, fingerprint=fp)
            did.append(f"updated #{issue}")
    return did


def run_watch(repos: list[str], interval: int = 30, once: bool = False, only: list[int] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    switch, store = Switch(), Store()
    maintainer = os.environ.get("BAKEOFF_MAINTAINER", "")
    if not maintainer:
        log.error("set BAKEOFF_MAINTAINER to the maintainer's username on the room's messaging app")
        return 2
    while True:
        for repo in repos:
            try:
                for line in tick(GitHub(repo), switch, store, maintainer, set(only or [])):
                    log.info("%s: %s", repo, line)
            except Exception as e:  # keep watching; the next pass retries
                log.warning("%s: %s", repo, e)
        if once:
            return 0
        time.sleep(interval)
