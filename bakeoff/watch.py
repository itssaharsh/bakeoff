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
    raw = "|".join(f"{p.number}:{p.ci}:{','.join(p.failing_checks)}:{p.head_sha}:{p.mergeable}" for p in c.prs)
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def readers() -> list[str]:
    raw = os.environ.get("BAKEOFF_READERS", "bakeoff-checker,bakeoff-second")
    return [a.strip() for a in raw.split(",") if a.strip()]


def post_pictures(gh, switch, room: str, c: Contest) -> None:
    """For a web-page contest, post each candidate as it renders (light and dark)."""
    from .screenshot import html_scope, render

    path = html_scope(c.scope)
    if not path:
        return
    for p in c.prs:
        try:
            html = gh.file_at(path, p.head_sha)
            shots = [(f"pr{p.number}-light.png", render(html), "image/png"),
                     (f"pr{p.number}-dark.png", render(html, dark=True), "image/png")]
            who = f" ({p.agent})" if p.agent else ""
            switch.post_files(room, shots, caption=f"#{p.number}{who}: {path} as it renders, light and dark")
        except Exception as e:  # pictures help; they never block the contest
            log.warning("picture for #%s failed: %s", p.number, e)


def tick(gh: GitHub, switch: Switch, store: Store, maintainer: str, only: set[int] | None = None) -> list[str]:
    """One pass over one repository. Returns what it did, for the log."""
    did: list[str] = []
    contested = contested_issues(gh)
    for issue in sorted(set(contested) | _open_rooms(store, gh.repo)):
        if only and issue not in only:
            continue
        try:
            did.extend(_tick_issue(gh, switch, store, maintainer, issue))
        except Exception as e:  # one bad contest never blocks the others
            log.warning("%s#%s: %s", gh.repo, issue, e)
    return did


def _open_rooms(store: Store, repo: str) -> set[int]:
    return {c["issue"] for c in store.all_contests().values()
            if c.get("repo") == repo and c.get("room_id") and not c.get("winner")}


def _tick_issue(gh, switch, store: Store, maintainer: str, issue: int) -> list[str]:
    did: list[str] = []
    state = store.contest(gh.repo, issue) or {}
    if state.get("winner"):
        return did
    c = collect_contest(gh, issue)
    if len(c.prs) < 2:
        if state.get("room_id") and not state.get("paused"):
            switch.post(state["room_id"], f"Only {len(c.prs)} open PR still closes #{issue}: the contest is paused "
                                          "until another one opens.")
            store.note(gh.repo, issue, paused=True)
            did.append(f"paused #{issue}")
        return did
    fp = facts_fingerprint(c)
    m = c.matrix(store.readings(gh.repo, issue), readers())
    if not state.get("room_id"):
        if state.get("creating_at"):  # a crash between creating the room and recording it: never make two
            log.warning("%s#%s: a room was being created at %s; check Switch, then clear it with "
                        "`bakeoff forget %s %s`", gh.repo, issue, state["creating_at"], gh.repo, issue)
            return did
        store.note(gh.repo, issue, creating_at=time.strftime("%Y-%m-%dT%H:%M:%SZ"))
        room = switch.create_room_from_template({
            "repo": gh.repo, "issue": issue, "issue_title": c.title,
            "candidates": candidates_text(c), "maintainer": maintainer,
        })
        store.open_contest(gh.repo, issue, room_id=room, prs=[p.number for p in c.prs])
        state = store.contest(gh.repo, issue) or {}
        did.append(f"opened room {room} for #{issue}")
    if state.get("paused"):
        store.note(gh.repo, issue, paused=False)
    if not state.get("fingerprint"):
        switch.post(state["room_id"], f"Contest opened by code: {len(c.prs)} open PRs close {gh.repo}#{issue}. "
                                      "Facts from GitHub below; readings fill in as the readers record them.\n"
                                      + render_text(m))
        store.note(gh.repo, issue, fingerprint=fp)
        post_pictures(gh, switch, state["room_id"], c)
        if not did:
            did.append(f"posted the opening matrix for #{issue}")
    elif state.get("fingerprint") != fp:
        new = sorted(set(p.number for p in c.prs) - set(state.get("prs", [])))
        store.set_prs(gh.repo, issue, [p.number for p in c.prs])
        if all(p.ci != "pending" for p in c.prs) or new:  # skip the noise while CI is still running
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
