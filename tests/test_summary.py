from bakeoff.matrix import PR, Reading, build_matrix
from bakeoff.summary import summary_lines

ITEMS = ["a", "b", "c"]


def pr(n, ci="success", body="", author="alice"):
    return PR(number=n, title=f"PR {n}", author=author, url=f"https://x/pull/{n}", ci=ci,
              failing_checks=["tests"] if ci == "failure" else [], body=body)


def test_one_line_per_pr_in_number_order():
    m = build_matrix(7, ITEMS, [pr(12, ci="pending", author="b"), pr(3, ci="success", author="a")],
                     [], scope=[])
    assert summary_lines(m) == [
        "#3 pass 0/3 @a",
        "#12 running 0/3 @b",
    ]


def test_items_met_counts_met_cells():
    readings = [Reading("checker", 3, 0, "met"), Reading("checker", 3, 1, "met"),
                Reading("checker", 3, 2, "unmet")]
    m = build_matrix(7, ITEMS, [pr(3)], readings, scope=[], agents=["checker"])
    assert summary_lines(m) == ["#3 pass 2/3 @alice"]


def test_ci_none_and_failure():
    m = build_matrix(7, ITEMS, [pr(1, ci="none"), pr(2, ci="failure")], [], scope=[])
    assert summary_lines(m) == ["#1 none 0/3 @alice", "#2 FAIL 0/3 @alice"]


def test_claimed_pass_with_failed_ci_is_called_out():
    m = build_matrix(7, ITEMS, [pr(1, ci="failure", body="All tests pass.")], [], scope=[])
    assert summary_lines(m) == ["#1 FAIL (claimed pass) 0/3 @alice"]


def test_empty_matrix_has_no_lines():
    m = build_matrix(7, ITEMS, [], [], scope=[])
    assert summary_lines(m) == []
