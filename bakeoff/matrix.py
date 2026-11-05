"""The contest matrix: one column per competing PR, filled by code.

GitHub's own data decides CI, files and scope. The agents' readings are stored
as structured verdicts (item, PR, met/unmet/unclear, evidence), and code works
out where they agree, disagree or are still waiting. Nothing here calls a model.
"""

from __future__ import annotations

import fnmatch
import re
from dataclasses import dataclass, field

VERDICTS = ("met", "unmet", "unclear")

_CLAIM = re.compile(
    r"tests?\s+(?:are\s+|now\s+|all\s+)?(?:pass(?:es|ed|ing)?|green)\b|\bci\s+(?:is\s+)?green\b",
    re.IGNORECASE,
)
_NEGATION = re.compile(r"(?:\bnot\b|n't\b|\bnever\b)\s*\w*\s*$", re.IGNORECASE)
_UNCHECKED = re.compile(r"^\s*[-*+]\s+\[ \]")


@dataclass
class PR:
    number: int
    title: str
    author: str
    url: str
    ci: str  # success | failure | pending | none
    failing_checks: list[str] = field(default_factory=list)
    files: list[str] = field(default_factory=list)
    body: str = ""
    head_sha: str = ""
    mergeable: bool | None = None
    agent: str = ""  # which coding agent wrote it, when the PR says so


@dataclass
class Reading:
    agent: str
    pr: int
    item: int
    verdict: str
    evidence: str = ""
    sha: str = ""  # the PR head the reader read; a newer commit makes the reading stale


@dataclass
class Cell:
    status: str  # met | unmet | unclear | disagree | waiting | unread
    readings: dict[str, Reading] = field(default_factory=dict)


@dataclass
class Column:
    number: int
    title: str
    author: str
    url: str
    ci: str
    failing_checks: list[str]
    tests_touched: bool
    out_of_scope: list[str]
    flags: list[str]
    items: list[Cell]
    agent: str = ""

    @property
    def ready(self) -> bool:
        return self.ci == "success" and bool(self.items) and all(c.status == "met" for c in self.items)

    def reasons(self, item_texts: list[str]) -> list[str]:
        """Plain reasons this PR was not ready, for a decline note."""
        out: list[str] = []
        if self.ci == "failure":
            names = ", ".join(self.failing_checks) or "a check"
            out.append(f"CI failed ({names})")
        elif self.ci in ("pending", "none"):
            out.append("CI had not passed when the pick was made")
        out.extend(f"claim check: {f}" for f in self.flags if f.startswith("claims"))
        if self.out_of_scope:
            out.append("touches files outside the issue's scope: " + ", ".join(self.out_of_scope))
        for i, cell in enumerate(self.items):
            if cell.status in ("unmet", "disagree", "unclear"):
                ev = "; ".join(f"{a}: {r.evidence}" for a, r in cell.readings.items() if r.verdict != "met" and r.evidence)
                label = item_texts[i] if i < len(item_texts) else f"item {i + 1}"
                out.append(f'Done-when item {i + 1} "{label}" not met' + (f" ({ev})" if ev else ""))
        return out


@dataclass
class Matrix:
    issue: int
    items: list[str]
    columns: list[Column]
    agents: list[str]

    @property
    def disagreements(self) -> list[tuple[int, int]]:
        return [(c.number, i) for c in self.columns for i, cell in enumerate(c.items) if cell.status == "disagree"]

    def column(self, number: int) -> Column | None:
        return next((c for c in self.columns if c.number == number), None)


def claims_tests_pass(body: str | None) -> bool:
    """True when the PR body says its tests pass. An unchecked checklist box is not a claim."""
    if not body:
        return False
    for line in body.splitlines():
        if _UNCHECKED.match(line):
            continue
        for m in _CLAIM.finditer(line):
            if not _NEGATION.search(line[max(0, m.start() - 14): m.start()]):
                return True
    return False


def _is_test_file(path: str) -> bool:
    name = path.rsplit("/", 1)[-1]
    return path.startswith(("tests/", "test/")) or "/tests/" in path or name.startswith("test_") or name.endswith(
        ("_test.py", ".test.ts", ".test.js", ".spec.ts", ".spec.js"))


def _in_scope(path: str, scope: list[str]) -> bool:
    return any(path == s or fnmatch.fnmatch(path, s) or path.startswith(s.rstrip("/") + "/") for s in scope)


def _cell(readings: dict[str, Reading], agents: list[str]) -> Cell:
    if not readings:
        return Cell("unread")
    verdicts = {r.verdict for r in readings.values()}
    missing = [a for a in agents if a not in readings]
    if len(verdicts) > 1:
        return Cell("disagree", readings)
    if missing:
        return Cell("waiting", readings)
    return Cell(verdicts.pop(), readings)


def build_matrix(issue: int, items: list[str], prs: list[PR], readings: list[Reading],
                 scope: list[str], agents: list[str] | None = None) -> Matrix:
    agents = list(agents) if agents else sorted({r.agent for r in readings})
    heads = {p.number: p.head_sha for p in prs}
    latest: dict[tuple[int, int, str], Reading] = {}
    stale: set[int] = set()
    for r in readings:  # later readings replace earlier ones from the same agent
        if r.agent not in agents:
            continue
        if r.sha and heads.get(r.pr) and r.sha != heads[r.pr]:
            stale.add(r.pr)
            continue
        latest[(r.pr, r.item, r.agent)] = r
    columns = []
    for p in sorted(prs, key=lambda p: p.number):
        flags = []
        if claims_tests_pass(p.body) and p.ci == "failure":
            flags.append("claims pass, CI failed")
        if p.mergeable is False:
            flags.append("merge conflict")
        if p.number in stale:
            flags.append("newer commit since a reading: re-read needed")
        cells = []
        for i in range(len(items)):
            rs = {a: r for (pn, it, a), r in latest.items() if pn == p.number and it == i}
            cells.append(_cell(rs, agents))
        columns.append(Column(
            number=p.number, title=p.title, author=p.author, url=p.url, ci=p.ci,
            failing_checks=list(p.failing_checks),
            tests_touched=any(_is_test_file(f) for f in p.files),
            out_of_scope=[f for f in p.files if scope and not _in_scope(f, scope)],
            flags=flags, items=cells, agent=p.agent,
        ))
    return Matrix(issue=issue, items=list(items), columns=columns, agents=agents)


_SYM = {"met": "yes", "unmet": "NO", "unclear": "?", "disagree": "SPLIT", "waiting": "1/2", "unread": "-",
        "success": "pass", "failure": "FAIL", "pending": "running", "none": "none"}


def render_text(m: Matrix) -> str:
    """A fixed-width table for chat (Slack does not render Markdown tables)."""
    heads = [f"#{c.number}" + (f" {c.agent}" if c.agent else "") for c in m.columns]
    rows: list[tuple[str, list[str]]] = [
        ("CI (GitHub)", [_SYM.get(c.ci, c.ci) for c in m.columns]),
        ("tests touched", ["yes" if c.tests_touched else "NO" for c in m.columns]),
        ("outside scope", [str(len(c.out_of_scope)) if c.out_of_scope else "0" for c in m.columns]),
    ]
    for i, text in enumerate(m.items):
        label = f"{i + 1}. {text}"
        rows.append((label[:34] + ("…" if len(label) > 34 else ""), [_SYM[c.items[i].status] for c in m.columns]))
    rows.append(("ready to pick", ["YES" if c.ready else "no" for c in m.columns]))
    w0 = max(len(r[0]) for r in rows)
    widths = [max(len(h), *(len(r[1][j]) for r in rows)) for j, h in enumerate(heads)]
    lines = [" " * w0 + " | " + " | ".join(h.ljust(widths[j]) for j, h in enumerate(heads))]
    lines.append("-" * len(lines[0]))
    for label, vals in rows:
        lines.append(label.ljust(w0) + " | " + " | ".join(v.ljust(widths[j]) for j, v in enumerate(vals)))
    notes = [f"#{c.number}: {f}" for c in m.columns for f in c.flags]
    notes += [f"#{pr}: item {i + 1} split between readers" for pr, i in m.disagreements]
    body = "\n".join(lines)
    tail = ("\n" + "\n".join(notes)) if notes else ""
    return f"```\nIssue #{m.issue}: {len(m.columns)} PRs, {len(m.items)} Done-when items\n{body}{tail}\n```"
