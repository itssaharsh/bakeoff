import json

import httpx

from bakeoff.github import GitHub, ci_conclusion, closes_issue, agent_of, collect_contest


def test_closes_issue_keywords():
    assert closes_issue("Closes #7", 7)
    assert closes_issue("this fixes #7.", 7)
    assert closes_issue("Resolves owner/repo#7", 7)
    assert not closes_issue("See #7", 7)
    assert not closes_issue("Closes #70", 7)
    assert not closes_issue(None, 7)


def test_ci_conclusion_rules():
    assert ci_conclusion([], []) == ("none", [])
    assert ci_conclusion([{"name": "t", "status": "completed", "conclusion": "success"}], []) == ("success", [])
    assert ci_conclusion([{"name": "t", "status": "in_progress", "conclusion": None}], []) == ("pending", [])
    assert ci_conclusion([{"name": "t", "status": "completed", "conclusion": "success"},
                          {"name": "lint", "status": "completed", "conclusion": "failure"}], []) == ("failure", ["lint"])
    assert ci_conclusion([], [{"context": "ci/x", "state": "failure"}]) == ("failure", ["ci/x"])
    assert ci_conclusion([{"name": "s", "status": "completed", "conclusion": "skipped"}], []) == ("none", [])


def test_agent_of():
    assert agent_of("[kimi] add flag", "") == "kimi"
    assert agent_of("add flag", "Written by: Pi coding agent\n") == "Pi coding agent"
    assert agent_of("add flag", "") == ""


def _fake():
    issue = {"number": 7, "title": "Add matrix command", "body": "## Done when\n- [ ] a\n- [ ] b\n\nScope: `bakeoff/cli.py`",
             "html_url": "https://github.com/o/r/issues/7", "state": "open"}
    pulls = [
        {"number": 11, "title": "[claude] matrix", "body": "Closes #7. All tests pass.", "user": {"login": "x"},
         "html_url": "https://github.com/o/r/pull/11", "head": {"sha": "s11"}, "draft": False},
        {"number": 12, "title": "[kimi] matrix", "body": "Fixes #7", "user": {"login": "y"},
         "html_url": "https://github.com/o/r/pull/12", "head": {"sha": "s12"}, "draft": False},
        {"number": 13, "title": "unrelated", "body": "Closes #8", "user": {"login": "z"},
         "html_url": "https://github.com/o/r/pull/13", "head": {"sha": "s13"}, "draft": False},
    ]
    runs = {"s11": [{"name": "tests", "status": "completed", "conclusion": "failure"}],
            "s12": [{"name": "tests", "status": "completed", "conclusion": "success"}]}

    def handler(req: httpx.Request):
        p = req.url.path
        if p == "/repos/o/r/issues/7":
            return httpx.Response(200, json=issue)
        if p == "/repos/o/r/pulls" and req.method == "GET":
            return httpx.Response(200, json=pulls)
        if p.startswith("/repos/o/r/commits/") and p.endswith("/check-runs"):
            sha = p.split("/")[5]
            return httpx.Response(200, json={"check_runs": runs.get(sha, [])})
        if p.startswith("/repos/o/r/commits/") and p.endswith("/status"):
            return httpx.Response(200, json={"statuses": []})
        if p.startswith("/repos/o/r/pulls/") and p.endswith("/files"):
            n = int(p.split("/")[5])
            files = {11: ["bakeoff/cli.py", "tests/test_cli.py"], 12: ["bakeoff/cli.py", "README.md"]}[n]
            return httpx.Response(200, json=[{"filename": f} for f in files])
        if p.startswith("/repos/o/r/pulls/"):
            n = int(p.split("/")[5])
            return httpx.Response(200, json={"number": n, "mergeable": True})
        return httpx.Response(404, json={"message": f"no route {p}"})

    return GitHub("o/r", token="t", transport=httpx.MockTransport(handler))


def test_collect_contest_finds_linked_prs_and_facts():
    gh = _fake()
    c = collect_contest(gh, 7)
    assert c.items == ["a", "b"]
    assert c.scope == ["bakeoff/cli.py"]
    assert [p.number for p in c.prs] == [11, 12]
    p11, p12 = c.prs
    assert p11.ci == "failure" and p11.failing_checks == ["tests"] and p11.agent == "claude"
    assert p12.ci == "success" and p12.files == ["bakeoff/cli.py", "README.md"]
    m = c.matrix([])
    assert "claims pass, CI failed" in m.column(11).flags
    assert m.column(12).out_of_scope == ["README.md"]
