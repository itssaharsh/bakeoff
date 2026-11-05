from bakeoff.matrix import PR, Reading, build_matrix, claims_tests_pass, render_text

ITEMS = ["prints one column per PR", "exits 1 without PRs"]


def pr(n, ci="success", body="", files=("bakeoff/cli.py", "tests/test_cli.py"), author="a"):
    return PR(number=n, title=f"PR {n}", author=author, url=f"https://x/pull/{n}", ci=ci,
              failing_checks=["tests"] if ci == "failure" else [], files=list(files), body=body)


def test_claim_detection():
    assert claims_tests_pass("All tests pass locally.")
    assert claims_tests_pass("CI is green")
    assert claims_tests_pass("tests passing ✅")
    assert not claims_tests_pass("tests don't pass yet")
    assert not claims_tests_pass("tests are not passing")
    assert not claims_tests_pass("Adds a test.")


def test_claims_pass_but_ci_failed_is_flagged_red():
    m = build_matrix(7, ITEMS, [pr(1, ci="failure", body="All tests pass.")], [], scope=[])
    col = m.columns[0]
    assert col.ci == "failure"
    assert "claims pass, CI failed" in col.flags


def test_tests_touched_and_out_of_scope():
    m = build_matrix(7, ITEMS, [pr(2, files=["bakeoff/cli.py", "README.md"])], [],
                     scope=["bakeoff/cli.py", "tests/*"])
    col = m.columns[0]
    assert col.tests_touched is False
    assert col.out_of_scope == ["README.md"]


def test_agreement_disagreement_and_waiting():
    readings = [
        Reading("checker", 1, 0, "met", "cli.py:10"),
        Reading("second", 1, 0, "met", "cli.py:10"),
        Reading("checker", 1, 1, "met", "cli.py:20"),
        Reading("second", 1, 1, "unmet", "returns 0 at cli.py:22"),
        Reading("checker", 2, 0, "unmet", "no columns"),
    ]
    m = build_matrix(7, ITEMS, [pr(1), pr(2)], readings, scope=[], agents=["checker", "second"])
    c1, c2 = m.columns
    assert c1.items[0].status == "met"
    assert c1.items[1].status == "disagree"
    assert c2.items[0].status == "waiting"
    assert c2.items[1].status == "unread"
    assert m.disagreements == [(1, 1)]


def test_latest_reading_per_agent_wins():
    readings = [Reading("checker", 1, 0, "unmet", "x"), Reading("checker", 1, 0, "met", "fixed")]
    m = build_matrix(7, ITEMS[:1], [pr(1)], readings, scope=[], agents=["checker"])
    assert m.columns[0].items[0].status == "met"


def test_ready_needs_green_ci_and_every_item_met():
    readings = [Reading(a, 1, i, "met", "") for a in ("checker", "second") for i in (0, 1)]
    readings += [Reading(a, 2, i, "met", "") for a in ("checker", "second") for i in (0, 1)]
    m = build_matrix(7, ITEMS, [pr(1), pr(2, ci="failure")], readings, scope=[], agents=["checker", "second"])
    assert [c.number for c in m.columns if c.ready] == [1]


def test_unmet_items_for_decline_note():
    readings = [Reading("checker", 2, 1, "unmet", "returns 0 at cli.py:22"),
                Reading("second", 2, 1, "unmet", "exit code 0")]
    m = build_matrix(7, ITEMS, [pr(2, ci="failure")], readings, scope=[], agents=["checker", "second"])
    reasons = m.columns[0].reasons(ITEMS)
    assert any("CI failed" in r for r in reasons)
    assert any("exits 1 without PRs" in r and "cli.py:22" in r for r in reasons)


def test_render_text_has_one_column_per_pr():
    m = build_matrix(7, ITEMS, [pr(1), pr(2, ci="failure", body="all tests pass")], [], scope=[])
    out = render_text(m)
    assert "#1" in out and "#2" in out
    assert "claims pass, CI failed" in out
    assert out.startswith("```") and out.rstrip().endswith("```")
