"""Tests for summary_lines pure function."""

from bakeoff.matrix import PR, Reading, build_matrix
from bakeoff.summary import summary_lines

ITEMS = ["item 1", "item 2"]


def pr(n, ci="success", body="", author="author1"):
    return PR(number=n, title=f"PR {n}", author=author, url=f"https://x/pull/{n}", ci=ci,
              failing_checks=["tests"] if ci == "failure" else [], files=["test.py"], body=body)


def test_summary_lines_basic():
    """Test basic format of summary lines."""
    m = build_matrix(7, ITEMS, [pr(1)], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#1 pass 0/2 @author1"


def test_summary_lines_with_ci_failure():
    """Test CI failure status."""
    m = build_matrix(7, ITEMS, [pr(2, ci="failure")], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#2 FAIL 0/2 @author1"


def test_summary_lines_with_ci_pending():
    """Test CI pending/running status."""
    m = build_matrix(7, ITEMS, [pr(3, ci="pending")], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#3 running 0/2 @author1"


def test_summary_lines_with_ci_none():
    """Test CI none status."""
    m = build_matrix(7, ITEMS, [pr(4, ci="none")], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#4 none 0/2 @author1"


def test_summary_lines_with_claimed_pass_but_ci_failed():
    """Test FAIL (claimed pass) when PR claims tests pass but CI failed."""
    m = build_matrix(7, ITEMS, [pr(5, ci="failure", body="All tests pass.")], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#5 FAIL (claimed pass) 0/2 @author1"


def test_summary_lines_with_items_met():
    """Test counting items met."""
    readings = [
        Reading("checker", 1, 0, "met", "done"),
        Reading("checker", 1, 1, "met", "done"),
    ]
    m = build_matrix(7, ITEMS, [pr(1)], readings, scope=[], agents=["checker"])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#1 pass 2/2 @author1"


def test_summary_lines_with_partial_items_met():
    """Test partial items met."""
    readings = [
        Reading("checker", 1, 0, "met", "done"),
        Reading("checker", 1, 1, "unmet", "not done"),
    ]
    m = build_matrix(7, ITEMS, [pr(1)], readings, scope=[], agents=["checker"])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#1 pass 1/2 @author1"


def test_summary_lines_multiple_prs():
    """Test multiple PRs in order."""
    m = build_matrix(7, ITEMS, [pr(1, author="alice"), pr(2, ci="failure", author="bob"), pr(3, ci="pending", author="charlie")], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 3
    assert lines[0] == "#1 pass 0/2 @alice"
    assert lines[1] == "#2 FAIL 0/2 @bob"
    assert lines[2] == "#3 running 0/2 @charlie"


def test_summary_lines_multiple_prs_with_mixed_items():
    """Test multiple PRs with different item statuses."""
    readings = [
        Reading("checker", 1, 0, "met", "done"),
        Reading("checker", 1, 1, "met", "done"),
        Reading("checker", 2, 0, "unmet", "pending"),
        Reading("checker", 2, 1, "met", "done"),
    ]
    m = build_matrix(7, ITEMS, [pr(1, author="alice"), pr(2, ci="failure", author="bob")], readings, 
                     scope=[], agents=["checker"])
    lines = summary_lines(m)
    assert len(lines) == 2
    assert lines[0] == "#1 pass 2/2 @alice"
    assert lines[1] == "#2 FAIL 1/2 @bob"


def test_summary_lines_pr_number_order():
    """Test that PRs are shown in number order even if input is different."""
    m = build_matrix(7, ITEMS, [pr(3), pr(1), pr(2)], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 3
    assert lines[0].startswith("#1 ")
    assert lines[1].startswith("#2 ")
    assert lines[2].startswith("#3 ")
