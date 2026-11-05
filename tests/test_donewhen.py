from bakeoff.donewhen import parse_done_when, parse_scope

ISSUE = """Some context about the bug.

## Done when
- [ ] `bakeoff matrix OWNER/REPO N` prints one column per open PR
- [ ] exits 1 with a message when the issue has no open PRs
  - the message names the issue
- [x] `--json` prints the same data as JSON
- [ ] tests in tests/test_cli.py

## Notes
- this list is not part of the checklist

Scope: `bakeoff/cli.py`, `tests/test_cli.py`
"""


def test_items_under_done_when_heading_in_order():
    items = parse_done_when(ISSUE)
    assert items == [
        "`bakeoff matrix OWNER/REPO N` prints one column per open PR",
        "exits 1 with a message when the issue has no open PRs; the message names the issue",
        "`--json` prints the same data as JSON",
        "tests in tests/test_cli.py",
    ]


def test_acceptance_heading_and_numbered_items():
    body = "**Acceptance criteria:**\n1. first thing\n2. second thing\n\nThanks!"
    assert parse_done_when(body) == ["first thing", "second thing"]


def test_plain_done_when_line_with_colon():
    body = "Done when:\n* a\n* b\n"
    assert parse_done_when(body) == ["a", "b"]


def test_falls_back_to_task_list_items_without_heading():
    body = "Please fix.\n- [ ] one\n- [ ] two\n- plain bullet is not a task\n"
    assert parse_done_when(body) == ["one", "two"]


def test_empty_when_nothing_found():
    assert parse_done_when("Just a sentence.") == []
    assert parse_done_when(None) == []


def test_scope_paths():
    assert parse_scope(ISSUE) == ["bakeoff/cli.py", "tests/test_cli.py"]
    assert parse_scope("Touches only: src/a.py, docs/*.md") == ["src/a.py", "docs/*.md"]
    assert parse_scope("no scope here") == []
