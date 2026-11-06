from bakeoff.cli import main
from bakeoff.github import Contest
from bakeoff.matrix import PR, Matrix, Reading, build_matrix
from bakeoff.summary import summary_lines

ITEMS = ["prints one line per PR", "exits 1 without PRs", "pure function"]
AGENTS = ["checker", "second"]


def pr(n, ci="success", body="Closes #7", author="a"):
    return PR(number=n, title=f"PR {n}", author=author, url=f"https://x/pull/{n}", ci=ci,
              failing_checks=["tests"] if ci == "failure" else [], files=["bakeoff/cli.py"], body=body)


def both(pr_number, item, verdict="met"):
    return [Reading(a, pr_number, item, verdict, "") for a in AGENTS]


def test_one_line_per_pr_with_ci_items_and_author():
    readings = both(3, 0) + both(3, 1) + both(5, 0)
    m = build_matrix(7, ITEMS, [pr(5, author="kimi-bot"), pr(3, author="claude-bot")], readings,
                     scope=[], agents=AGENTS)
    assert summary_lines(m) == ["#3 pass 2/3 @claude-bot", "#5 pass 1/3 @kimi-bot"]


def test_lines_are_in_pr_number_order_even_if_columns_are_not():
    m = build_matrix(7, ITEMS, [pr(2), pr(10), pr(4)], [], scope=[])
    m.columns.reverse()
    assert [line.split()[0] for line in summary_lines(m)] == ["#2", "#4", "#10"]


def test_ci_words_follow_github():
    prs = [pr(1, ci="success"), pr(2, ci="failure"), pr(3, ci="pending"), pr(4, ci="none")]
    m = build_matrix(7, ITEMS, prs, [], scope=[])
    assert [line.split()[1] for line in summary_lines(m)] == ["pass", "FAIL", "running", "none"]


def test_claimed_pass_with_failed_ci_is_called_out():
    prs = [pr(1, ci="failure", body="Closes #7. All tests pass."),
           pr(2, ci="failure", body="Closes #7. Tests are not passing yet."),
           pr(3, ci="success", body="Closes #7. All tests pass.")]
    m = build_matrix(7, ITEMS, prs, [], scope=[])
    assert summary_lines(m) == [
        "#1 FAIL (claimed pass) 0/3 @a",
        "#2 FAIL 0/3 @a",
        "#3 pass 0/3 @a",
    ]


def test_only_agreed_met_items_count():
    readings = (both(1, 0, "met")                                             # met
                + [Reading("checker", 1, 1, "met"), Reading("second", 1, 1, "unmet")]  # disagree
                + [Reading("checker", 1, 2, "met")])                          # waiting on second reader
    m = build_matrix(7, ITEMS, [pr(1)], readings, scope=[], agents=AGENTS)
    assert summary_lines(m) == ["#1 pass 1/3 @a"]


def test_no_columns_gives_no_lines():
    assert summary_lines(Matrix(issue=7, items=ITEMS, columns=[], agents=[])) == []


def _stub_github(monkeypatch, tmp_path, prs):
    monkeypatch.setenv("BAKEOFF_STATE", str(tmp_path / "state.json"))
    monkeypatch.setattr("bakeoff.github.GitHub", lambda repo: object())
    contest = Contest(repo="o/r", issue=7, title="t", url="u", items=ITEMS, scope=[], prs=prs)
    monkeypatch.setattr("bakeoff.github.collect_contest", lambda gh, issue: contest)


def test_cli_prints_summary(monkeypatch, tmp_path, capsys):
    _stub_github(monkeypatch, tmp_path, [pr(12, author="y"), pr(11, ci="failure", body="Closes #7. All tests pass.",
                                                               author="x")])
    assert main(["summary", "o/r", "7"]) == 0
    out = capsys.readouterr()
    assert out.out == "#11 FAIL (claimed pass) 0/3 @x\n#12 pass 0/3 @y\n"
    assert out.err == ""


def test_cli_without_competing_prs_exits_1(monkeypatch, tmp_path, capsys):
    _stub_github(monkeypatch, tmp_path, [])
    assert main(["summary", "o/r", "7"]) == 1
    out = capsys.readouterr()
    assert out.out == ""
    assert out.err == "no competing pull requests for #7\n"
