from bakeoff.state import Store


def test_readings_round_trip_and_validation(tmp_path):
    s = Store(tmp_path / "state.json")
    s.add_reading("o/r", 7, "checker", 11, 0, "met", "cli.py:10")
    s.add_reading("o/r", 7, "second", 11, 0, "unmet", "no test")
    rs = s.readings("o/r", 7)
    assert [(r.agent, r.verdict) for r in rs] == [("checker", "met"), ("second", "unmet")]
    assert Store(tmp_path / "state.json").readings("o/r", 7)[1].evidence == "no test"
    try:
        s.add_reading("o/r", 7, "checker", 11, 0, "maybe", "")
        raise AssertionError("bad verdict accepted")
    except ValueError:
        pass


def test_room_and_decision(tmp_path):
    s = Store(tmp_path / "state.json")
    assert s.contest("o/r", 7) is None
    s.open_contest("o/r", 7, room_id="!abc", prs=[11, 12])
    assert s.contest("o/r", 7)["room_id"] == "!abc"
    assert s.decide("o/r", 7, winner=11, decided_by="saharsh") is True
    assert s.decide("o/r", 7, winner=12, decided_by="friend") is False
    assert s.contest("o/r", 7)["decided_by"] == "saharsh"
