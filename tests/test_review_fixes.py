"""Regression tests for the fresh-eyes review (T11)."""
from bakeoff.donewhen import parse_done_when
from bakeoff.github import Contest, ci_conclusion, closes_issue
from bakeoff.matrix import PR, Reading, build_matrix, claims_tests_pass
from bakeoff.pick import PickRefused, merge_pick
from bakeoff.state import Store


def test_wrapped_item_lines_continue_the_item():
    body = "## Done when\n- first item that wraps\n  onto a second line\n- second\n- third\n"
    assert parse_done_when(body) == ["first item that wraps onto a second line", "second", "third"]


def test_prose_starting_with_acceptance_is_not_a_heading():
    body = "Acceptance of this was discussed.\n\nSome list:\n- unrelated\n- [ ] real task\n"
    assert parse_done_when(body) == ["real task"]


def test_closes_issue_ignores_other_repos_comments_and_takes_urls():
    assert not closes_issue("Closes other/repo#5", 5, repo="o/r")
    assert closes_issue("Closes o/r#5", 5, repo="o/r")
    assert not closes_issue("<!-- Closes #5 -->", 5)
    assert closes_issue("Closes https://github.com/o/r/issues/5", 5, repo="o/r")


def test_latest_check_run_per_name_wins_and_skipped_only_is_none():
    runs = [{"id": 1, "name": "t", "status": "completed", "conclusion": "failure"},
            {"id": 2, "name": "t", "status": "completed", "conclusion": "success"}]
    assert ci_conclusion(runs, []) == ("success", [])
    assert ci_conclusion([{"id": 3, "name": "s", "status": "completed", "conclusion": "skipped"}], []) == ("none", [])


def test_claims():
    assert not claims_tests_pass("- [ ] tests pass")
    assert claims_tests_pass("No regressions, all tests pass.")
    assert claims_tests_pass("The failing tests now pass")
    assert claims_tests_pass("tests passed locally")


def test_readings_on_an_older_commit_are_dropped():
    p = PR(1, "t", "a", "u", "success", head_sha="new")
    m = build_matrix(1, ["x"], [p], [Reading("c", 1, 0, "met", "", sha="old")], [], agents=["c"])
    assert m.columns[0].items[0].status == "unread"
    assert any("newer commit" in f for f in m.columns[0].flags)


def test_readings_from_unlisted_agents_do_not_count():
    p = PR(1, "t", "a", "u", "success", head_sha="s")
    m = build_matrix(1, ["x"], [p], [Reading("stranger", 1, 0, "met", "", sha="s")], [], agents=["c", "d"])
    assert m.columns[0].items[0].status == "unread"


class GH:
    repo = "o/r"

    def __init__(self, merged=True):
        self.merged_ok, self.calls, self.comments, self.closed = merged, [], [], []

    def merge(self, n, title, message, sha=None):
        self.calls.append((n, sha))
        return {"merged": self.merged_ok}

    def comment(self, n, body):
        self.comments.append((n, body))

    def close_pull(self, n):
        self.closed.append(n)


def contest():
    return Contest("o/r", 7, "t", "u", ["x"], [], [PR(11, "a", "x", "u", "success", head_sha="h11"),
                                                PR(12, "b", "y", "u", "success", head_sha="h12")])


def opened(tmp_path):
    s = Store(tmp_path / "s.json")
    s.open_contest("o/r", 7, room_id="!r", prs=[11, 12])
    return s


def test_merge_is_pinned_to_the_head_that_was_read(tmp_path):
    gh = GH()
    merge_pick(gh, opened(tmp_path), contest(), 11, decided_by="m")
    assert gh.calls == [(11, "h11")]


def test_merged_false_is_not_a_merge(tmp_path):
    gh, s = GH(merged=False), opened(tmp_path)
    try:
        merge_pick(gh, s, contest(), 11, decided_by="m")
        raise AssertionError("expected refusal")
    except PickRefused as e:
        assert "did not merge" in str(e)
    assert gh.comments == [] and gh.closed == []
    assert s.contest("o/r", 7).get("winner") is None


def test_no_room_no_pick(tmp_path):
    try:
        merge_pick(GH(), Store(tmp_path / "s.json"), contest(), 11, decided_by="m")
        raise AssertionError("expected refusal")
    except PickRefused as e:
        assert "room" in str(e)


def test_interrupted_pick_resumes_for_the_same_pr(tmp_path):
    s = opened(tmp_path)
    s.decide("o/r", 7, 11, "m")                      # crashed right after recording the pick
    gh = GH()
    out = merge_pick(gh, s, contest(), 11, decided_by="m")
    assert gh.calls == [(11, "h11")] and gh.closed == [12] and "merged" in out
    try:
        merge_pick(GH(), s, contest(), 12, decided_by="other")
        raise AssertionError("expected refusal")
    except PickRefused as e:
        assert "already decided by m" in str(e)


def test_missing_decline_notes_are_posted_on_retry(tmp_path):
    s = opened(tmp_path)
    s.decide("o/r", 7, 11, "m")
    s.note("o/r", 7, merged=True, declined=[])
    gh = GH()
    out = merge_pick(gh, s, contest(), 11, decided_by="m")
    assert gh.calls == [] and gh.closed == [12] and "Posted the missing" in out


def test_decline_note_without_readings_says_so_and_strips_mentions(tmp_path):
    s = opened(tmp_path)
    s.add_reading("o/r", 7, "c", 12, 0, "unmet", "see @someone at a.py:1", sha="h12")
    gh = GH()
    merge_pick(gh, s, contest(), 11, decided_by="m", agents=["c"])
    note = dict(gh.comments)[12]
    assert "@someone" not in note and "someone" in note
