# Implementation contract - bakeoff
mode: hackathon | channel: direct | created: 2026-11-05
Upstream read: the idea package written before the build (kept outside this repository), Switch repo docs and code (sandbox-quantum/switch @186e9a4)

## 1. Intent
- User and moment of use: a maintainer when two or more pull requests compete to close the same issue (this hackathon's own Track 03 issue list: five to ten claimants per issue, "Only one PR will be selected per issue"). Personal mode: a person who asked several agents for the same thing (a homepage redesign) and wants friends' views before shipping one.
- What they can do: open one Switch room per contest, read a matrix GitHub's own data fills, read two agents' independent checklist readings, ask contributors questions in the room, pick one PR by name, and have the merge and every decline note posted for them.
- What changes after (before -> after): before, the maintainer re-reads each PR against the issue, over days, and the losing contributors get silence or a one-line close. After, one sitting in one room: a pick made by a named maintainer, one merge, and every other contributor gets a note naming the unmet checklist item.

## 2. Scope
MUST (core, main workflow, judged or required):
- M1 Collector: issue -> Done-when checklist; open PRs that close it; per PR: CI conclusion, files changed, tests touched, files outside the issue's scope, claims in the body ("tests pass") vs CI, mergeability. GitHub is the source of truth.
- M2 Contest matrix: pure code over the collected facts; two agents' readings stored as structured verdicts (item, PR, met/unmet/unclear, file:line); disagreements computed by code.
- M3 Bakeoff MCP server (stdio) with tools: done_when, contest_matrix, pr_diff, record_reading, and merge_pick (single use per contest, refuses red CI, refuses PRs outside the contest, posts merge + winner comment + decline notes).
- M4 Intake watcher: detects a contest (2+ open PRs closing one issue) and creates the Switch room from the Bakeoff room template through the Switch agent bridge, posts the matrix, kickoff mentions the two checker agents.
- M5 Room template (YAML): roles checker / second-opinion / merger (exclusive), instructions, references (issue + PRs), maintainers and contributors as users, kickoff.
- M6 Switch setup: server + controller on EC2, Slack bridge, agents bakeoff-checker (Claude Code), bakeoff-second (OpenCode, non-Anthropic model), bakeoff-merge (Claude Code, approvals on, addressing limited to maintainers).
- M7 Demo world: a real issue on this repo with four PRs written by four coding agents (Claude Code, Kimi Code, Pi, OpenCode); CI on this repo.
- M8 README (one-sentence summary first, how Switch is used, run it yourself), video, submission form text, blog post.
SHOULD:
- S1 Personal mode coda: a homepage repo, brief with must-haves checked by a CI job, a screenshot of each candidate posted in the room, friends weigh in, owner picks, merge deploys to GitHub Pages.
- S2 merge_pick also reads Switch's own approval record (approval_requests.answered_by) and refuses unless a maintainer approved this exact call.
COULD: contest replay page; GitHub webhook instead of polling; Mattermost recording.
WON'T now: running PR code locally, ranking contributors, auto-merge without a person, multi-repo dashboards, ranking other entrants' PRs on the Switch repo.

## 3. Core journeys
J1 Contest opens: a second PR closing issue #N appears -> watcher creates room "bakeoff-N" from the template, posts the matrix -> checker and second-opinion each post a reading table (item x PR) with file:line -> code posts agreements and disagreements.
J2 Questions: a maintainer or agent asks a contributor in the room -> contributor answers -> agents may re-read and record a new verdict.
J3 Pick: a maintainer writes "@bakeoff-merge pick #P" -> merge agent calls merge_pick -> Switch shows the approval card -> a maintainer allows once -> PR #P merged, winner comment, decline notes on the others with the unmet item -> room posts the result with links. A second pick on the same contest is refused with who decided and when.

## 4. Surfaces
Slack channel per contest (Switch room); GitHub PRs and comments; the bakeoff MCP tools; `bakeoff` CLI: `bakeoff watch`, `bakeoff matrix OWNER/REPO ISSUE`, `bakeoff mcp`.

## 5. States per journey
| Journey | initial | loading | success | error | empty | partial | retry | disabled | permission-denied | offline/degraded |
|---|---|---|---|---|---|---|---|---|---|---|
| J1 | issue with 0-1 PR: no room | watcher polling | room + matrix posted | GitHub API error: watcher logs and retries next poll, no room | issue without Done-when list: matrix says "no checklist found: agents read against the issue text" | some PR has no CI yet: cell "pending", re-read on next poll | next poll (30 s) | contest already has a room: no second room | GitHub token lacks scope: watcher exits with the missing scope named | Switch API down: watcher retries, nothing posted twice (idempotent by issue) |
| J2 | room open | agent turn running (Switch progress) | reading recorded | agent tool error shown in thread | no readings yet: matrix shows "-" | one agent read, other not: matrix marks "waiting for second opinion" | maintainer asks again | n/a | a non-maintainer cannot instruct the merge agent (addressing policy) | model down: the matrix still stands on GitHub facts alone |
| J3 | contest open | approval card waiting | merged + notes posted | merge conflict / GitHub refuses: tool returns error, contest stays open | n/a: pick needs a PR number | merge done but a decline note failed: tool reports which, retry posts the rest | re-run merge_pick (idempotent per comment) | contest decided: second pick refused naming the decider | approval declined or from someone outside maintainers: nothing posted | GitHub down: nothing half-posted, contest stays open |

## 6. Data
| Entity | Key fields | Relationships | Owner | Persistence | Source of truth | PII/retention |
|---|---|---|---|---|---|---|
| Contest | repo, issue, pr list, room_id, status, decided_by, decided_at, winner | 1 issue : 1 contest | Bakeoff service | ~/.bakeoff/state.json on the box | this file (decision), GitHub (PR facts) | GitHub logins only |
| Reading | contest, agent, pr, item index, verdict, evidence | many per contest | the agent that recorded it | same file | this file | none |
| PR facts | ci conclusion, files, body claims | per PR | GitHub | not stored (fetched) | GitHub | public data |

## 7. Interfaces
| Interface | Purpose | Contract file | Failure mode | Fallback |
|---|---|---|---|---|
| GitHub REST/GraphQL | issue, PRs, checks, merge, comments | bakeoff/github.py | rate limit, 5xx, merge conflict | retry next poll; merge_pick returns error, contest stays open |
| Switch agent bridge API | create room from YAML, post messages | bakeoff/switch_api.py | 401/5xx | retry; idempotent by issue |
| MCP stdio | agent tools | bakeoff/mcp_server.py | tool exception | error text back to the agent, shown in thread |
| Agents (Claude Code, OpenCode) | readings and the pick | room template instructions | model refusal, timeout, bad table | readings are optional to the matrix; merge needs only a maintainer's pick + approval |

## 8. Constraints
- Judging criteria (https://www.devtoolsacademy.com/hackathons/flip-the-switch, read 2026-11-04): Use of Switch 30% "Is Switch central to the project, and would it stop working without it?"; Technical execution 25% "Does it run, and could someone clone the repo and reproduce it?"; Creativity and impact 25% "Is it a fresh idea that solves a problem a real team has?"; Presentation 20% "Do the demo video and README make clear how Switch is used?"
- Rules: in .prod-build/rules.json (7 rules). Switch central; public repo with setup README; built in the window; video under 3 min on YouTube/Loom; real chat with teammates.
- Security: GitHub token with repo scope only on this repo and the homepage repo, kept in SSM, never in the repo; Slack and Anthropic keys in SSM; merge only through merge_pick; no secrets in logs.
- Budget: Anthropic API credits; one m7i.xlarge (~$0.20/h) stopped after recording.
- Deadline: freeze 2026-11-07T06:58Z, end 2026-11-07T18:29Z.

## 9. Acceptance criteria
- AC-1: WHEN an issue has two or more open PRs that close it THE SYSTEM SHALL create exactly one Switch room for it and post the matrix. Verify: tests/test_watch.py + observed run. must
- AC-2: WHEN a PR body claims tests pass and its CI conclusion is failure THE SYSTEM SHALL mark the cell red with "claims pass, CI failed". Verify: tests/test_matrix.py (RED first). must
- AC-3: WHEN the issue body has a "Done when" (or "Acceptance") checklist THE SYSTEM SHALL extract each item in order. Verify: tests/test_donewhen.py (RED first). must
- AC-4: WHEN two agents record different verdicts for the same item and PR THE SYSTEM SHALL list it as a disagreement for the maintainer. Verify: tests/test_matrix.py. must
- AC-5: IF merge_pick is called for a contest already decided THEN THE SYSTEM SHALL refuse and name who decided and when, posting nothing. Verify: tests/test_pick.py (RED first). must
- AC-6: IF merge_pick is called for a PR with failing CI or outside the contest THEN THE SYSTEM SHALL refuse with the reason. Verify: tests/test_pick.py. must
- AC-7: WHEN merge_pick succeeds THE SYSTEM SHALL merge the PR, comment on it naming the decider, and comment on and close every other contest PR with its unmet items. Verify: tests/test_pick.py (fake GitHub) + observed on GitHub. must
- AC-8: WHEN a non-maintainer addresses the merge agent THE SYSTEM SHALL not act (Switch addressing policy). Verify: observed in Slack. must
- AC-9: WHEN the merge agent calls merge_pick THE SYSTEM SHALL show an approval card in the room before the tool runs. Verify: observed in Slack. must
- AC-10: WHEN someone clones the repo THE SYSTEM SHALL be reproducible from the README steps (template, MCP config, seed script). Verify: clean-clone run on the box. must

## 10. Assumptions
- A-1 [reversible]: polling every 30 s is enough (no webhook): no public address on the box.
- A-2 [reversible]: the decider's name passed to merge_pick is the maintainer who asked; the approval card shows it and only maintainers can approve (addressing policy). S2 upgrades this to a check of Switch's approval record.
- A-3 [safe]: PRs written by four coding agents and pushed from branches of this repo count as real competing PRs; each PR says which agent wrote it.
- A-4 [blocking, asked 2026-11-05]: Slack bot token and workspace id from the builder; until then, test on Switch's bundled Mattermost.
- A-5 [reversible]: second-opinion model = a non-Anthropic model via OpenCode (infra check picks it).

## 11. Demo script (under 3:00)
- 0:00-0:20 Problem: Switch's own repo during this hackathon, issue with several PRs, "Only one PR will be selected per issue." Bakeoff's own issue #N got four PRs from four coding agents.
- 0:20-1:50 Flow: watcher opens #bakeoff-N in Slack; matrix from GitHub; checker (Claude Code) and second opinion (OpenCode/other model) post readings; code flags the disagreement; maintainer asks a contributor; wow: PR says "all tests pass", CI red, cell stays red; friend #2 (non-maintainer) tells the merge agent to merge their PR: nothing happens; maintainer picks; approval card; Allow once; merge + decline notes land on GitHub.
- 1:50-2:20 Architecture: Switch room template, roles, addressing policy, approval card, MCP tools, GitHub facts.
- 2:20-2:45 Failure: second maintainer picks again: refused with name and time.
- 2:45-3:00 Personal coda: homepage candidates, friends' picks, live deploy (if S1 ships).

## 12. Event and judged path
(This file is public with the repository. It quotes the event's own public pages, with the date each was read.)
- Window: start 2026-11-03T18:31:00Z (Wed 4 Nov 00:01 IST), freeze 2026-11-07T06:58Z (Sat 7 Nov 12:28 IST), end 2026-11-07T18:29:00Z (Sat 7 Nov 23:59 IST), from https://wemakedevs-server.onrender.com/hackathons/switch (event data, read 2026-11-04). Rule on earlier work (FAQ, https://www.wemakedevs.org/hackathons/switch): "Existing agents, libraries and templates are fine. The Switch setup and the workflow your agents run need to be built during the hackathon."
- How an entry is judged: form description, then the demo video ("Keep it under 3 minutes"), then the repository README; live demo optional. Minutes per project and whether anyone runs the build: not published. Process: "Every submission is reviewed, and a shortlist is put together", then "Finalists are judged by a joint panel from DevTools Academy, Switch, and WeMakeDevs."
- Criteria: see §8 (weights from the DevTools Academy event page, read 2026-11-04; the WeMakeDevs page shows the same four questions).
- Criteria coverage: Use of Switch - room from a template by code, roles, addressing policy refusing a non-maintainer, approval card releasing the merge (met when M4-M6 are observed). Technical execution - seed script + room template + MCP config rebuild the run from a clean clone (met when AC-10 passes). Creativity and impact - several PRs competing for one slot, every contributor answered with a reason, run on real PRs written by four agents (partial until the run is on camera). Presentation - the one-sentence summary heads the README and the video's first 20 s (met when M8 ships).
- Capability coverage: Code with Wispr - prompts, room instructions and README dictated (builder's usage card on the form). Best Blog - a first-time Switch user's guide to this setup.
- Main result: on GitHub, one PR merged with a comment naming the maintainer who picked it in Switch, and every other PR closed with a note naming its unmet item; material: four PRs written by four coding agents on a real issue of this repo. Staged failure: a second pick on a decided contest is refused, naming who decided.
- Live feature: n/a: no hosted web app; the public repo, the demo PRs and their comments, the landing page and the video are what anyone can open. The Switch server runs on a private EC2 box and is shown in the video.
- Promise coverage: "Bakeoff" -> several candidates compete for one slot (the matrix's columns, one per PR); "two agents" -> two columns of readings by two vendors; "a maintainer picks the winner by name" -> the approval card and the winner comment.
- Before the clock: planning (idea package, judging notes) was done on 4 Nov after the window opened; T03 pull requests to Switch core were separate work. README: "Built during the Flip the Switch hackathon ... Planning notes and the build plan were written first, inside the window."
