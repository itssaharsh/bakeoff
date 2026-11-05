import importlib
import sys


def _load(monkeypatch, allow):
    if allow:
        monkeypatch.setenv("BAKEOFF_ALLOW_MERGE", "1")
    else:
        monkeypatch.delenv("BAKEOFF_ALLOW_MERGE", raising=False)
    sys.modules.pop("bakeoff.mcp_server", None)
    return importlib.import_module("bakeoff.mcp_server")


def _tool_names(mod):
    return set(mod.mcp._tool_manager._tools)


def test_readers_do_not_get_merge(monkeypatch):
    mod = _load(monkeypatch, allow=False)
    assert {"done_when", "contest_matrix", "pr_diff", "record_readings"} <= _tool_names(mod)
    assert "merge_pick" not in _tool_names(mod)


def test_merge_agent_gets_merge(monkeypatch):
    mod = _load(monkeypatch, allow=True)
    assert _tool_names(mod) == {"merge_pick"}


def test_record_readings_uses_agent_env_not_argument(monkeypatch, tmp_path):
    monkeypatch.setenv("BAKEOFF_STATE", str(tmp_path / "s.json"))
    monkeypatch.setenv("BAKEOFF_AGENT", "bakeoff-checker")
    mod = _load(monkeypatch, allow=False)
    out = mod.record_readings("o/r", 7, 11, [{"item": 1, "verdict": "met", "evidence": "a.py:1"},
                                             {"item": 2, "verdict": "unmet", "evidence": "no test"}])
    assert "2 verdicts from bakeoff-checker" in out
    from bakeoff.state import Store
    rs = Store(tmp_path / "s.json").readings("o/r", 7)
    assert [(r.agent, r.item, r.verdict) for r in rs] == [("bakeoff-checker", 0, "met"), ("bakeoff-checker", 1, "unmet")]
    bad = mod.record_readings("o/r", 7, 11, [{"item": 1, "verdict": "probably"}])
    assert bad.startswith("Nothing recorded")


def test_tool_errors_come_back_as_one_line(monkeypatch):
    import httpx
    mod = _load(monkeypatch, allow=False)

    def boom(*a, **k):
        req = httpx.Request("GET", "https://api.github.com/repos/o/r/issues/999")
        raise httpx.HTTPStatusError("x", request=req, response=httpx.Response(404, request=req))
    monkeypatch.setattr(mod, "collect_contest", boom)
    out = mod.done_when("o/r", 999)
    assert out.startswith("ERROR:") and "not found" in out
