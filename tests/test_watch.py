from bakeoff.github import Contest
from bakeoff.matrix import PR
from bakeoff import watch
from bakeoff.state import Store


class FakeSwitch:
    def __init__(self):
        self.rooms, self.posts = [], []

    def create_room_from_template(self, inputs, yaml_text=None):
        self.rooms.append(inputs)
        return f"!room{len(self.rooms)}"

    def post(self, room, content):
        self.posts.append((room, content))
        return "e1"


class FakeGH:
    repo = "o/r"


def make(prs):
    return Contest("o/r", 7, "Add matrix", "u", ["a", "b"], [], prs)


def test_one_room_per_contest_and_no_duplicate_posts(tmp_path, monkeypatch):
    prs = [PR(11, "[claude] x", "u1", "url11", "pending", head_sha="a", agent="claude"), PR(12, "[kimi] y", "u2", "url12", "success", head_sha="b")]
    state = {"c": make(prs)}
    monkeypatch.setattr(watch, "contested_issues", lambda gh: {7: [11, 12]})
    monkeypatch.setattr(watch, "collect_contest", lambda gh, n: state["c"])
    sw, store = FakeSwitch(), Store(tmp_path / "s.json")

    assert watch.tick(FakeGH(), sw, store, "saharsh") == ["opened room !room1 for #7"]
    assert sw.rooms[0]["issue"] == 7 and sw.rooms[0]["maintainer"] == "saharsh"
    assert "#11 [claude] x by @u1 (written by claude)" in sw.rooms[0]["candidates"]
    assert len(sw.posts) == 1 and "2 open PRs" in sw.posts[0][1]

    assert watch.tick(FakeGH(), sw, store, "saharsh") == []          # same facts: silent
    assert len(sw.rooms) == 1 and len(sw.posts) == 1

    prs[0].ci, prs[0].failing_checks = "failure", ["tests"]          # CI finished: one update
    assert watch.tick(FakeGH(), sw, store, "saharsh") == ["updated #7"]
    assert "Updated matrix" in sw.posts[-1][1] and sw.posts[-1][0] == "!room1"

    state["c"] = make(prs + [PR(13, "[pi] z", "u3", "url13", "success", head_sha="c")])
    watch.tick(FakeGH(), sw, store, "saharsh")
    assert "New candidate(s): #13" in sw.posts[-1][1]


def test_decided_contest_is_left_alone(tmp_path, monkeypatch):
    monkeypatch.setattr(watch, "contested_issues", lambda gh: {7: [11, 12]})
    monkeypatch.setattr(watch, "collect_contest", lambda gh, n: (_ for _ in ()).throw(AssertionError("fetched")))
    store = Store(tmp_path / "s.json")
    store.open_contest("o/r", 7, "!r", [11, 12])
    store.decide("o/r", 7, 11, "saharsh")
    assert watch.tick(FakeGH(), FakeSwitch(), store, "saharsh") == []


def test_switch_client_finds_room_id():
    from bakeoff.switch_api import _find_room_id
    assert _find_room_id({"result": {"rooms": [{"room": {"id": "!x"}}]}}) == "!x"
    assert _find_room_id({"room_id": "!y"}) == "!y"
    assert _find_room_id({"nothing": 1}) == ""
