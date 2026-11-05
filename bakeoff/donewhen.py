"""Read the checklist an issue says it is done against.

Code, not a model, decides what the checklist is: the items under a "Done when",
"Acceptance" or "Definition of done" heading, or, with no such heading, the
task-list items (`- [ ]`) anywhere in the body.
"""

from __future__ import annotations

import re

_HEADING = re.compile(
    r"^\s*(?:#{1,6}\s*)?(?:\*\*|__)?\s*(done when|acceptance criteria|acceptance|definition of done)"
    r"\s*:?\s*(?:\*\*|__)?\s*:?\s*$",
    re.IGNORECASE,
)
_COMMENT = re.compile(r"<!--.*?-->", re.DOTALL)
_ITEM = re.compile(r"^(?P<indent>\s*)(?:[-*+]|\d+[.)])\s+(?:\[[ xX]\]\s+)?(?P<text>\S.*)$")
_TASK = re.compile(r"^\s*[-*+]\s+\[[ xX]\]\s+(?P<text>\S.*)$")
_ANY_HEADING = re.compile(r"^\s*(#{1,6}\s|\*\*[^*]+\*\*\s*:?\s*$)")
_SCOPE = re.compile(r"^\s*(?:\*\*)?(scope|touches only|files)(?:\*\*)?\s*:\s*(?P<rest>.+)$", re.IGNORECASE)


def parse_done_when(body: str | None) -> list[str]:
    """Return the checklist items, in order; nested items join their parent with '; '."""
    if not body:
        return []
    lines = _COMMENT.sub("", body).replace("\r\n", "\n").split("\n")
    start = next((i for i, line in enumerate(lines) if _HEADING.match(line)), None)
    if start is None:
        return [m.group("text").strip() for line in lines if (m := _TASK.match(line))]

    items: list[str] = []
    base_indent: int | None = None
    blank_since_item = False
    for line in lines[start + 1:]:
        if not line.strip():
            blank_since_item = bool(items)
            continue
        m = _ITEM.match(line)
        if m:
            indent = len(m.group("indent").expandtabs(4))
            text = m.group("text").strip()
            if base_indent is None:
                base_indent = indent
            if indent > base_indent and items:
                items[-1] = f"{items[-1]}; {text}"
            else:
                items.append(text)
            blank_since_item = False
            continue
        if items and not blank_since_item and line[:1].isspace():
            items[-1] = f"{items[-1]} {line.strip()}"  # a wrapped line continues the item
            continue
        if items or _ANY_HEADING.match(line):
            break
    return items


def parse_scope(body: str | None) -> list[str]:
    """Paths or globs an issue says a fix may touch ("Scope: `a.py`, `tests/*`")."""
    if not body:
        return []
    for line in body.split("\n"):
        m = _SCOPE.match(line)
        if m:
            rest = m.group("rest")
            ticked = re.findall(r"`([^`]+)`", rest)
            parts = ticked or [p.strip() for p in rest.split(",")]
            return [p for p in (x.strip().rstrip(".") for x in parts) if p]
    return []
