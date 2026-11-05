from bakeoff.github import Contest
from bakeoff.matrix import PR, Reading
from bakeoff.pick import PickRefused, merge_pick
from bakeoff.state import Store

ITEMS = ["prints one column per PR", "exits 1 without PRs"]


class FakeGH:
    repo = "o/r"

    def __init__(self, fail_comment_on=None):
        self.merged, self.comments, self.closed = [], [], []
        self.fail_comment_on = fail_comment_on

    def merge(self, n, title, message, sha=None):
        self.merged.append(n)
        return {"merged": True, "sha": "abc"}

    def comment(self, n, body):
        if n == self.fail_comment_on:
            raise RuntimeError("boom")
        self.comments.append((n, body))
        return {"html_url": f"https://x/{n}#c"}

    def close_pull(self, n):
        self.closed.append(n)
        return {}


def contest():
    prs = [PR(11, "[claude] matrix", "x", "https://x/11", "success", agent="claude"),
           PR(12, "[kimi] matrix", "y", "https://x/12", "failure", ["tests"], body="All tests pass", agent="kimi"),
           PR(13, "[pi] matrix", "z", "https://x/13", "success", agent="pi")]
    return Contest("o/r", 7, "Add matrix", "https://x/issues/7", ITEMS, [], prs)


def readings():
    rs = [Reading(a, 11, i, "met", "ok") for a in ("checker", "second") for i in (0, 1)]
    rs += [Reading("checker", 13, 1, "unmet", "returns 0 at cli.py:22"), Reading("second", 13, 1, "unmet", "exit 0")]
    return rs


def test_pick_merges_winner_and_answers_every_other_pr(tmp_path):
    gh, store = FakeGH(), Store(tmp_path / "s.json")
    store.open_contest("o/r", 7, room_id="!r", prs=[11, 12, 13])
    for r in readings():
        store.add_reading("o/r", 7, r.agent, r.pr, r.item, r.verdict, r.evidence)
    out = merge_pick(gh, store, contest(), 11, decided_by="saharsh", agents=["checker", "second"])
    assert gh.merged == [11]
    assert sorted(gh.closed) == [12, 13]
    winner = dict(gh.comments)[11]
    assert "saharsh" in winner and "Switch" in winner
    n12 = dict(gh.comments)[12]
    assert "CI failed (tests)" in n12 and "claims pass, CI failed" in n12
    n13 = dict(gh.comments)[13]
    assert "exits 1 without PRs" in n13 and "cli.py:22" in n13
    assert "#11 merged" in out
    assert store.contest("o/r", 7)["decided_by"] == "saharsh"


def test_second_pick_is_refused_naming_the_decider(tmp_path):
    gh, store = FakeGH(), Store(tmp_path / "s.json")
    store.open_contest("o/r", 7, room_id="!r", prs=[11, 12, 13])
    merge_pick(gh, store, contest(), 11, decided_by="saharsh")
    gh2 = FakeGH()
    try:
        merge_pick(gh2, store, contest(), 13, decided_by="friend")
        raise AssertionError("second pick allowed")
    except PickRefused as e:
        assert "saharsh" in str(e) and "#11" in str(e)
    assert gh2.merged == [] and gh2.comments == []


def test_red_ci_and_outsider_prs_are_refused(tmp_path):
    store = Store(tmp_path / "s.json")
    store.open_contest("o/r", 7, room_id="!r", prs=[11, 12, 13])
    for pr, why in ((12, "CI"), (99, "not in this contest")):
        gh = FakeGH()
        try:
            merge_pick(gh, store, contest(), pr, decided_by="saharsh")
            raise AssertionError("refusal expected")
        except PickRefused as e:
            assert why in str(e)
        assert gh.merged == []
    assert store.contest("o/r", 7).get("winner") is None


def test_partial_failure_reports_which_note_failed(tmp_path):
    gh, store = FakeGH(fail_comment_on=13), Store(tmp_path / "s.json")
    store.open_contest("o/r", 7, room_id="!r", prs=[11, 12, 13])
    out = merge_pick(gh, store, contest(), 11, decided_by="saharsh")
    assert gh.merged == [11]
    assert "#13" in out and "failed" in out
