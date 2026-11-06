# Delivery report — Bakeoff (hackathon, 2026-11-06)

## Built
- J1 Contest opens: the watcher finds two or more open PRs that close one issue and creates one Switch room (a Slack channel) from `templates/bakeoff.room.yaml` through the agent bridge, then posts the matrix from GitHub (CI, tests touched, files outside scope). Web-page contests also get light and dark pictures of each candidate.
- J2 Readings and questions: two readers (Claude Code, OpenCode) record per-item verdicts with file:line through the Bakeoff MCP tools; code marks agreement, SPLIT and waiting; anyone in the room can ask a reader.
- J3 Pick: the merge agent's only tool is `merge_pick`, so every pick stops at a Switch approval card; the merge is pinned to the commit that was read, a reasoned note is posted on every other PR, and a contest is decided once.
- Cut: verifying Switch's approval record inside `merge_pick` (S2), webhooks, pagination past 100 checks/files.

## Architecture
- One Python package (`bakeoff/`) used three ways: the watcher, the MCP server per agent, and a CLI. State is one locked JSON file on the Switch box; GitHub is the source of truth for facts. Switch runs headless on one EC2 box (Docker Compose + agent controller), bridged to Slack by Socket Mode.
- Decisions: ADR-0001 (readers get MCP tools only), F-0001 (merge agent cut to one tool so each pick raises one card), L-0001 (agent-run templates check the kickoff against addressing first).
- Not built on purpose: a web dashboard, auto-merge without a person, ranking other entrants' PRs on Switch's repository.

## Verification
- Unit suite after the review fixes: 50 passed [E0027]; after the merged winners (#2 summary command): 58 passed [E0042]
- Review regressions written RED first, then GREEN (RED: E0022; GREEN: E0023)
- End to end in Slack (rehearsal #7): room, readings, approval card answered by the maintainer from Slack, merge, decline note, second pick refused [E0026]
- Approval card raised for `merge_pick` only [E0021]
- Readers cannot read files (canary) [E0024]
- Recorded take: three runs in Slack, picks #2 and #10 merged, the teammate's pick ignored, the second pick refused [E0033]; recording saved [E0032]
- Fresh-eyes review: report in `.prod-build/reports/T11-review.md`, 8 blocking findings, 7 fixed and 1 partly [E0024]
- Browser pass of the live landing page at 390/1024/1440: not run; the page is a static file checked by `scripts/brief_check.py` in CI

## Deployment
- Landing page: https://itssaharsh.github.io/bakeoff/ deployed by GitHub Pages from the merge of #10 [E0034]; live smoke 200 [E0044]
- Switch server and agents on EC2: not deployed publicly (no inbound ports, by design); it ran the demo, shown in the video

## Bugs found and fixed
- Merge not pinned to the reviewed commit; a push after the readings could be merged unreviewed: fixed with `sha` on the merge and stale-reading detection (RED first: E0022; GREEN: E0023)
- A 200 response with `merged: false` was reported as a merge: now refused and the pick undone (RED first: E0022; GREEN: E0023)
- Readers could read the box's env file (prompt-injection risk): file, shell and web tools denied [E0024]
- Wrapped checklist lines ended the list; prose starting "Acceptance" was read as a heading: parser fixed (RED first: E0022; GREEN: E0023)
- An interrupted pick left the contest stuck: the same pick now resumes (RED first: E0022; GREEN: E0023)

## Known limitations
- The name on a pick is what the merge agent passes; the approval card shows it and Switch records who answered, but `merge_pick` does not read that record.
- Readers are models: they can disagree and are shown as SPLIT; only CI, scope and tests touched are code-decided.
- One role per agent across all rooms, so concurrent contests queue.
- Polling every 30 s; PRs with more than 100 checks or files are partly read.
- The second reader runs on Claude Haiku through OpenCode (the box's free OpenCode models were rate-limited and Bedrock's other models are off on this account).

## Cleanup
- Test rooms archived; rehearsal Slack channels renamed and archived; planning notes kept outside the repository (`hackathon-idea/`, git-ignored).

## Optimization
- n/a: the watcher and tools are I/O bound on GitHub's API; no measurement taken.

## Memory
- ADR-0001, F-0001, L-0001 in docs/memory.

## Next steps
- Final video edit and upload, README video link, blog on DEV, #HowISwitch post, submit the form; rotate the Slack, GitHub and Anthropic tokens after the hackathon (they were pasted in chat); stop the EC2 box after judging.
