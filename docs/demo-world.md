# The demo contest

Issue [#1](https://github.com/itssaharsh/bakeoff/issues/1) asks for a `bakeoff summary` command, with a
five-item Done-when list and a Scope line. On 5 Nov 2026 four coding agents got the same prompt (the issue
text, "read the code first, run the tests, write PR_BODY.md") and file-editing tools only, each in its own
worktree. Their work became four real pull requests:

| PR | Agent | Model |
|---|---|---|
| [#2](https://github.com/itssaharsh/bakeoff/pull/2) | Claude Code | claude-opus-5-5 |
| [#3](https://github.com/itssaharsh/bakeoff/pull/3) | Kimi Code 2.5 | claude-haiku-4-5 |
| [#4](https://github.com/itssaharsh/bakeoff/pull/4) | Pi coding agent 1.5 | claude-haiku-4-5 |
| [#5](https://github.com/itssaharsh/bakeoff/pull/5) | OpenCode 1.18 | deepseek-v4.1-flash-free |

All four pass CI. They differ on the checklist and the scope, which is what the room has to read for.
`scripts/race.sh` rebuilds the race on a fork.
