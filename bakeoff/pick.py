"""The pick: one merge per contest, made for a named person, and a reasoned note on every other PR.

What code enforces here, whatever anyone types in chat:
- the pick happens in a contest Bakeoff opened (a room exists, two or more PRs), in a watched repo;
- the PR is one of the contest's PRs and GitHub's checks on it passed;
- the merge is pinned to the commit that was read (GitHub refuses it if the PR moved);
- a contest is decided once. An interrupted pick resumes for the same PR; another PR is refused.
"""

from __future__ import annotations

import os
import re

from .github import Contest
from .state import Store


class PickRefused(Exception):
    pass


def _watched(repo: str) -> bool:
    raw = os.environ.get("BAKEOFF_REPOS", "")
    repos = {r.strip().lower() for r in raw.replace(",", " ").split() if r.strip()}
    return not repos or repo.lower() in repos


def _clean(text: str) -> str:
    """Agent-written evidence goes onto public GitHub: no @mentions, short."""
    return re.sub(r"@(?=\w)", "", text)[:200]


def merge_pick(gh, store: Store, contest: Contest, pr: int, decided_by: str,
               agents: list[str] | None = None) -> str:
    repo, issue = contest.repo, contest.issue
    c = store.contest(repo, issue) or {}
    if not _watched(repo):
        raise PickRefused(f"{repo} is not a repository Bakeoff watches.")
    if not c.get("room_id"):
        raise PickRefused(f"No Bakeoff room is open for {repo}#{issue}; picks happen in the contest room.")
    numbers = [p.number for p in contest.prs]
    winner = c.get("winner")
    if winner and winner != pr:
        raise PickRefused(f"Contest for #{issue} was already decided by {c['decided_by']} at {c['decided_at']}: "
                          f"#{winner} was picked. Nothing was posted.")
    if winner == pr and c.get("merged"):
        return _post_notes(gh, store, contest, pr, c["decided_by"], agents, retry=True)
    if not winner and len(numbers) < 2:
        raise PickRefused(f"#{issue} has {len(numbers)} open PR; a bake-off needs two or more.")
    if pr not in numbers:
        raise PickRefused(f"PR #{pr} is not in this contest (open PRs closing #{issue}: "
                          + ", ".join(f"#{n}" for n in numbers) + ").")
    m = contest.matrix(store.readings(repo, issue), agents)
    col = m.column(pr)
    if col.ci != "success":
        detail = f" ({', '.join(col.failing_checks)})" if col.failing_checks else ""
        raise PickRefused(f"CI on #{pr} is {col.ci}{detail}. GitHub's checks must pass before a pick; "
                          "chat cannot overrule them.")
    if not decided_by.strip():
        raise PickRefused("A pick needs the name of the person who made it.")
    if not winner and not store.decide(repo, issue, pr, decided_by):
        c = store.contest(repo, issue) or {}
        raise PickRefused(f"Contest for #{issue} was just decided by {c.get('decided_by')}: #{c.get('winner')}.")
    decided_by = (store.contest(repo, issue) or {}).get("decided_by", decided_by)

    head = next(p.head_sha for p in contest.prs if p.number == pr)
    try:
        resp = gh.merge(pr, f"{col.title} (#{pr})",
                        f"Picked by {decided_by} in the Bakeoff room for #{issue} (Switch), "
                        f"from {len(numbers)} competing PRs.", sha=head or None)
    except Exception as e:  # GitHub refused (conflict, protection, head moved): the contest stays open
        store.undecide(repo, issue)
        raise PickRefused(f"GitHub refused to merge #{pr}: {e}. The contest is still open.") from e
    if not (isinstance(resp, dict) and resp.get("merged") is True):
        store.undecide(repo, issue)
        raise PickRefused(f"GitHub did not merge #{pr} ({str(resp)[:120]}). The contest is still open.")
    store.note(repo, issue, merged=True, merge_sha=resp.get("sha", ""), declined=[])
    return _post_notes(gh, store, contest, pr, decided_by, agents, retry=False)


def _post_notes(gh, store: Store, contest: Contest, pr: int, decided_by: str,
                agents: list[str] | None, retry: bool) -> str:
    repo, issue = contest.repo, contest.issue
    c = store.contest(repo, issue) or {}
    m = contest.matrix(store.readings(repo, issue), agents)
    col = m.column(pr)
    numbers = [p.number for p in contest.prs]
    readers = ", ".join(m.agents) if m.agents else "the room's agents"
    done = set(c.get("declined", []))
    failures: list[str] = []

    if not retry:
        met = sum(1 for cell in col.items if cell.status == "met") if col else 0
        agree = "both readers agree" if len(m.agents) >= 2 else "readers"
        try:
            gh.comment(pr, (f"**Picked in Bakeoff.** {decided_by} chose this PR for #{issue} in the team's Switch "
                            f"room, from {len(numbers) + len(done)} competing pull requests.\n\n"
                            f"- GitHub checks: passed\n- Done-when items met ({agree}): {met} of {len(m.items)}\n"
                            f"- Readers: {readers}\n"))
        except Exception as e:
            failures.append(f"winner comment on #{pr} failed: {e}")

    posted = []
    for p in contest.prs:
        if p.number == pr or f"#{p.number}" in done:
            continue
        reasons = [_clean(r) for r in m.column(p.number).reasons(m.items)]
        if not reasons:
            reasons = ["no checklist item was recorded as missed: the maintainer preferred the picked PR"]
        body = (f"Thank you for this pull request. #{issue} had several competing PRs and only one could be "
                f"merged: {decided_by} picked #{pr} in the team's Switch room.\n\n"
                "What this PR was missing when the pick was made:\n" + "\n".join(f"- {r}" for r in reasons) +
                f"\n\n_Facts come from GitHub's checks; the checklist readings are by {readers}. "
                "Reply here if any of this is wrong._")
        try:
            gh.comment(p.number, body)
            gh.close_pull(p.number)
            posted.append(f"#{p.number}")
        except Exception as e:
            failures.append(f"note on #{p.number} failed: {e}")

    store.note(repo, issue, declined=sorted(done | set(posted)), failures=failures)
    if retry:
        out = f"Posted the missing decline notes: {', '.join(posted) or 'none were missing'}."
    else:
        out = f"#{pr} merged, picked by {decided_by}. Declined with a note: {', '.join(posted) or 'none'}."
    if failures:
        out += " Problems: " + "; ".join(failures) + ". Run the same pick again to post what is missing."
    return out
