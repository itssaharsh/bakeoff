from bakeoff.matrix import PR, Reading, build_matrix
from bakeoff.summary import summary_lines

ITEMS = ["first item", "second item"]


def pr(n, ci="success", body="", author="author1"):
    return PR(number=n, title=f"PR {n}", author=author, url=f"https://x/pull/{n}", ci=ci,
              failing_checks=["tests"] if ci == "failure" else [], files=["test.py"], body=body)


def test_summary_lines_basic_format():
    m = build_matrix(7, ITEMS, [pr(1)], [], scope=[])
    lines = summary_lines(m)
    assert len(lines) == 1
    assert lines[0] == "#1 pass 0/2 @author1"


def test_summary_lines_with_met_items():
    readings = [Reading("checker", 1, 0, "met", ""), Reading("checker", 1, 1, "met", "")]
    m = build_matrix(7, ITEMS, [pr(1)], readings, scope=[], agents=["checker"])
    lines = summary_lines(m)
    assert lines[0] == "#1 pass 2/2 @author1"


def test_summary_lines_partial_items():
    readings = [Reading("checker", 1, 0, "met", ""), Reading("checker", 1, 1, "unmet", "")]
    m = build_matrix(7, ITEMS, [pr(1)], readings, scope=[], agents=["checker"])
    lines = summary_lines(m)
    assert lines[0] == "#1 pass 1/2 @author1"


def test_summary_lines_multiple_prs():
    readings = [
        Reading("checker", 1, 0, "met", ""),
        Reading("checker", 2, 0, "unmet", ""),
    ]
    m = build_matrix(7, ITEMS, [pr(1), pr(2)], readings, scope=[], agents=["checker"])
    lines = summary_lines(m)
    assert len(lines) == 2
    assert lines[0] == "#1 pass 1/2 @author1"
    assert lines[1] == "#2 pass 0/2 @author1"


def test_summary_lines_ci_statuses():
    m = build_matrix(
        7, ITEMS,
        [pr(1, ci="success"), pr(2, ci="failure"), pr(3, ci="pending"), pr(4, ci="none")],
        [], scope=[]
    )
    lines = summary_lines(m)
    assert "pass" in lines[0]
    assert "FAIL" in lines[1]
    assert "running" in lines[2]
    assert "none" in lines[3]


def test_summary_lines_claimed_pass_but_ci_failed():
    m = build_matrix(7, ITEMS, [pr(1, ci="failure", body="All tests pass.")], [], scope=[])
    lines = summary_lines(m)
    assert "FAIL (claimed pass)" in lines[0]


def test_summary_lines_different_authors():
    m = build_matrix(
        7, ITEMS,
        [pr(1, author="alice"), pr(2, author="bob"), pr(3, author="charlie")],
        [], scope=[]
    )
    lines = summary_lines(m)
    assert "@alice" in lines[0]
    assert "@bob" in lines[1]
    assert "@charlie" in lines[2]
