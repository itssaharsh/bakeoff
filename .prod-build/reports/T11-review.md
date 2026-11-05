# Bakeoff review (read-only). Tests: 35 pass. Repro scripts: scratchpad/review/r1.py, r2.py

## Blocking
B1 github.py:474-478 + pick.py:130 -- merge is not pinned to the reviewed SHA. CI is read at collect_contest time, readings are not tied to head_sha,
   and PUT /merge is sent without "sha". A contributor pushes after the readers/CI/approval card; GitHub merges the new head.
   Fix: pass sha=col head_sha (GitHub then returns 409), and drop readings when head_sha changes.
B2 Checker agent can read the secrets (box-setup.sh:44-48 + 52-56). deny list is Bash/Edit/Write/Web*; Read/Glob/Grep stay allowed, ~/bakeoff.env is 600 but owned by
   the same user, holds GITHUB_TOKEN (write) and the intake API key. A PR diff with an injected instruction can make the auto-mode checker Read it
   and post it in the (public) channel. OpenCode reader: read permission not denied either. Fix: deny Read of ~/bakeoff.env (or separate OS user / only pass token to the merge MCP),
   readers' MCP process should not receive GITHUB_TOKEN with write scope.
B3 donewhen.py:334 -- a wrapped (continuation) line ends the list. "## Done when\n- first item that wraps\n  onto a second line\n- second\n- third" -> ['first item that wraps'] (items 2,3 silently lost; matrix then
   says ready with 1 item). Also _HEADING (donewhen.py:294) matches any line starting "Acceptance..."/"Done when ..." in prose:
   "Acceptance of this was discussed.\n\nSome list:\n- unrelated\n- [ ] real" -> ['unrelated','real task'].
B4 pick.py:131-135 -- merge response never checked for merged:true. Fake GH returning {"merged": False} (200) -> "#1 merged, picked by bob", winner comment posted, other PRs commented and CLOSED
   (repro r2.py). Real GitHub normally uses 405/409 for refusals, but code relies on that. Fix: require resp.get("merged") is True else undecide.
B5 pick.py:126-130 -- crash/kill between decide() and merge leaves winner set, nothing merged; watcher skips decided contests and a second pick is refused: contest permanently stuck
   (needs hand-editing state.json). Same for crash after merge before declines (others never closed, no retry path; README/contract J3 says "retry posts the rest" but re-run is refused).
   Fix: record status "merging" then "merged"; allow resume/retry of same PR.
B6 "matrix cannot be overruled" is false (pick.py:122-123, template lines 529-531): only CI is enforced. merge_pick does not check Done-when cells (unmet / SPLIT / unread),
   scope, mergeable, or even that any reading exists; a contest of ONE PR (no watcher room, any repo/issue the token can reach: repo and issue are tool args) can be merged. decided_by is a free string typed by the LLM
   (mcp_server.py:303); it is not tied to the Switch approval's answered_by (contract S2), so "picked by <name>" on GitHub can be spoofed/wrong.
   Fix or soften wording; at minimum require state.room_id for (repo,issue) and len(contest.prs)>=2.
B7 deploy/bakeoff-watch.service:8 -- "${BAKEOFF_REPOS}" is passed to systemd as ONE argument; two repos "a/b c/d" -> one bogus repo. Use $BAKEOFF_REPOS (unbraced splits on whitespace).
B8 README "Run it yourself" (AC-10): box-setup.sh:5,12,18-25 hard-requires AWS CLI + SSM parameters /switch-demo/github-token and /switch-demo/bakeoff-intake-api-key; README never says so.
   An outsider cannot follow steps 2. Also `$SSM` failures inside heredoc $(...) do not trip set -e: an empty GITHUB_TOKEN= is written silently. mcp dep: pyproject says mcp>=1.2 but code imports
   mcp.server.mcpserver.MCPServer (mcp 2.x; lock has 2.3.0) -> a fresh resolve of an older mcp breaks; pin >=2.

## Should fix
M1 watch.py:226-262 -- one exception aborts the whole repo tick (try is around tick, watch.py:275-279). A poison contest (Switch rejects room, 4xx) sorted first blocks every later issue forever. Wrap per issue.
M2 watch.py:240-245 -- check-then-create with no lock/idempotency: a crash or store failure between create_room and open_contest, or the service plus a manual `watch --once` (README step 4), makes a duplicate room.
   Room name bakeoff-{issue} also collides across repos with the same issue number.
M3 watch.py:256-261 -- posts on every fingerprint change; CI pending->success per push and re-run flaps = 2-3 posts per push. PR closing (<2 left) is silent (watch.py:236) and room stays open forever. mergeable is null on first fetch
   (github.py:168) and is not in the fingerprint, so "merge conflict" is missed/stale.
M4 github.py:367, 532 -- closes_issue false positives: "Closes other/repo#5" counts for local #5 (repo prefix accepted, never compared); "does not close #5" and "<!-- Closes #5 -->" (PR template comments) count. False negative: "Closes https://github.com/o/r/issues/5". (r1.py)
M5 matrix.py:105-115 claims_tests_pass: "- [ ] tests pass" (unchecked PR template box) is a claim -> false "claims pass, CI failed"; "No regressions, all tests pass" and "failing tests now pass" are missed (negation within 25 chars); "tests passed" not matched. Flag only, but visible to contributors in decline note.
M6 github.py:384-403 ci_conclusion: handles runs by name only in the sense GitHub's default filter=latest dedups server side; the function itself would report failure for old-fail+new-success lists (r1.py) and neither check-runs
   nor statuses nor pull_files paginate beyond 100 (github.py:455,458-459) -> >100 checks/files silently ignored. Conclusions "skipped/neutral/stale" count as success; a PR whose only check is skipped is "success" and pickable.
M7 mcp_server.py:291-297 record_readings: item 0, negative or > len(items) is accepted and reported "Recorded n verdicts" but ignored by matrix (item-1 = -1); pr not validated against the contest; partial writes if a later row has a bad "item" (KeyError -> ERROR after some stored). Validate and reject.
M8 pick.py:151 -- decline note falls back to "another PR met the checklist first" even when the PR was simply unread/"waiting"/ready; the note says "What this PR was missing when the pick was made" while no reading exists. Agent-authored `evidence` (400 chars, derived from attacker-controlled diffs)
   is posted verbatim into public GitHub comments (can @mention / link). Escape or drop.
M9 Secrets/permissions: box-setup.sh:21 `cat > ~/bakeoff.env` keeps the mode of an existing file (umask only applies on create) -> add chmod 600. No secrets in repo or git history (grep clean; only pattern strings in .prod-build/pb.py).
M10 state.py:34 -- no fsync before os.replace; and a 0-byte/truncated file is read as empty (state.py:34) silently forgetting every winner (duplicate rooms, re-pick possible). Corrupt JSON raises on every call (watcher logs forever). Locking itself is correct:
   8 processes x 20 writes -> 160/160 readings; two concurrent merge_pick -> exactly one merge (r2.py). Readings list is append-only and unbounded (negligible at demo scale; matrix keeps latest per agent).
M11 Prompt injection surface: PR titles go into the room instructions/docs given to the merger and readers ({candidates}); contest_matrix prints titles. Approval card is the only gate for the merger. Whether Switch substitutes inputs after YAML parse
   (a title with `"`, `: `, `{merger}` or `#` in issue_title/description line, or multi-line {candidates} inside `|` blocks at template lines 518-526) cannot be verified here; add a test with hostile titles against a real create_room_from_yaml.
M12 Readings from agents not in BAKEOFF_READERS still count in a cell (matrix.py:130-137) and with `agents=None` (CLI `bakeoff matrix`, readers unset) one reader alone yields "met" while merge_pick's comment says "both readers agree" (pick.py:144).

## README / template claims the code does not do
- "Nobody can overrule GitHub / matrix cannot be overruled": true for CI only (B6). Template line 530: scope and tests-touched are called facts nobody overrules; they are not enforced.
- "a maintainer picks the winner by name": name is LLM-supplied text, not verified against the approval (B6).
- "A decline note fails to post ... the pick stays recorded": true, but no retry path exists (B5).
- "Every other PR gets a note listing what it missed": generic fallback text when nothing recorded (M8).
- "run it yourself" omits AWS SSM dependency (B8); "writes ~/bakeoff.env" also pulls secrets from SSM.
- "Switch's addressing policy doesn't deliver it", approval card, role leases, register-known: not verifiable in this repo (observed-run claims).
- "idempotent by issue" (contract) is only true absent crashes/two watchers (M2).

## Dead code / simplifications
- mcp_server.py:10 unused `import json`; pyyaml dependency unused; Store.contests() unused; donewhen.py:318-321 if/else both `continue` (and `seen_item` is only used after); matrix.py _CLAIM alternation `tests?\s+passing` duplicates the first branch;
  github.py closes regex duplicated in github.py:367 and 532 (reuse _CLOSES); Switch/GitHub constructed per MCP call (fine). bakeoff-mcp.sh runs `uv run` (sync) on every agent start: latency and network dependency; use a pre-synced venv.
- Readers' MCP server gets the full env file (write token + intake key) though it only needs a read token.

## Resolution (2026-11-05, commit "T11: review fixes")
- B1 fixed: readings carry the PR head sha; stale readings dropped and flagged; merge sent with `sha` (tests/test_review_fixes.py).
- B2 fixed: readers' Read/Glob/Grep/LS/Bash/Edit/Write/Web/Task denied; OpenCode tools off. Observed: checker answered "I can't read files" to a canary request on the box.
- B3 fixed: wrapped lines continue an item; heading must be a heading line; HTML comments stripped.
- B4 fixed: merge requires `merged: true`, otherwise the pick is undone.
- B5 fixed: an interrupted pick resumes for the same PR; missing decline notes are posted on a re-run.
- B6 partly fixed: pick needs an open Bakeoff room, 2+ PRs and a watched repo; README now says only CI is enforced from chat, and how the name on the pick is recorded (S2, checking Switch's approval record, is not built).
- B7 fixed: `$BAKEOFF_REPOS` unbraced in the unit.
- B8 fixed: README states the SSM dependency and how to skip it; box-setup fails on an empty secret; mcp>=2.3; pyyaml dropped.
- M1, M2, M3 (pause notice, mergeable in fingerprint, no posts while CI pending), M4, M5, M6 (newest run per name, skipped-only = none), M7, M8, M9, M10 (fsync), M12 fixed. Not fixed: pagination past 100 checks/files, M11 hostile-title test against Switch.
