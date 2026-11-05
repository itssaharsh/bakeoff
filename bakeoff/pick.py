"""The pick: one merge per contest, made for a named person, and a reasoned note on every other PR."""

from __future__ import annotations

from .github import Contest
from .state import Store


class PickRefused(Exception):
    pass


def merge_pick(gh, store: Store, contest: Contest, pr: int, decided_by: str,
               agents: list[str] | None = None) -> str:
    repo, issue = contest.repo, contest.issue
    c = store.contest(repo, issue) or {}
    if c.get("winner"):
        raise PickRefused(f"Contest for #{issue} was already decided by {c['decided_by']} at {c['decided_at']}: "
                          f"#{c['winner']} was picked. Nothing was posted.")
    numbers = [p.number for p in contest.prs]
    if pr not in numbers:
        raise PickRefused(f"PR #{pr} is not in this contest (open PRs closing #{issue}: "
                          + ", ".join(f"#{n}" for n in numbers) + ").")
    m = contest.matrix(store.readings(repo, issue), agents)
    col = m.column(pr)
    if col.ci != "success":
        detail = f" ({', '.join(col.failing_checks)})" if col.failing_checks else ""
        raise PickRefused(f"CI on #{pr} is {col.ci}{detail}. GitHub's checks must pass before a pick; "
                          "the matrix cannot be overruled from chat.")
    if not decided_by.strip():
        raise PickRefused("A pick needs the name of the person who made it.")
    if not store.decide(repo, issue, pr, decided_by):
        c = store.contest(repo, issue) or {}
        raise PickRefused(f"Contest for #{issue} was just decided by {c.get('decided_by')}: #{c.get('winner')}.")

    try:
        gh.merge(pr, f"{col.title} (#{pr})",
                 f"Picked by {decided_by} in the Bakeoff room for #{issue} (Switch), from {len(numbers)} competing PRs.")
    except Exception as e:  # GitHub refused (conflict, protection): the contest stays open
        store.undecide(repo, issue)
        raise PickRefused(f"GitHub refused to merge #{pr}: {e}. The contest is still open.") from e

    readers = ", ".join(m.agents) if m.agents else "the room's agents"
    others = [p for p in contest.prs if p.number != pr]
    met = sum(1 for cell in col.items if cell.status == "met")
    failures: list[str] = []
    try:
        gh.comment(pr, (f"**Picked in Bakeoff.** {decided_by} chose this PR for #{issue} in the team's Switch room, "
                        f"from {len(numbers)} competing pull requests.\n\n"
                        f"- GitHub checks: passed\n- Done-when items met (both readers agree): {met} of {len(m.items)}\n"
                        f"- Readers: {readers}\n"))
    except Exception as e:
        failures.append(f"winner comment on #{pr} failed: {e}")

    declined = []
    for p in others:
        reasons = m.column(p.number).reasons(m.items) or ["another PR met the checklist first"]
        body = (f"Thank you for this pull request. #{issue} had {len(numbers)} competing PRs and only one could be "
                f"merged: {decided_by} picked #{pr} in the team's Switch room.\n\n"
                "What this PR was missing when the pick was made:\n" + "\n".join(f"- {r}" for r in reasons) +
                f"\n\n_Facts come from GitHub's checks; the checklist readings are by {readers}. "
                "Reply here if any of this is wrong._")
        try:
            gh.comment(p.number, body)
            gh.close_pull(p.number)
            declined.append(f"#{p.number}")
        except Exception as e:
            failures.append(f"note on #{p.number} failed: {e}")

    store.note(repo, issue, declined=declined, failures=failures)
    out = f"#{pr} merged, picked by {decided_by}. Declined with a note: {', '.join(declined) or 'none'}."
    if failures:
        out += " Problems: " + "; ".join(failures) + " The pick is recorded; post the missing note by hand."
    return out
