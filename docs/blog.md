# Five pull requests, one issue: running a bake-off in Switch

*How I set up Switch for the first time, headless on a small cloud box, and gave three agents one job: help a maintainer pick one PR out of several, and answer everyone else.*

## The problem I picked

During the Flip the Switch hackathon, Switch's own repository passed 390 open pull requests, and its maintainer wrote: "Only one PR will be selected per issue." Coding agents made the PRs cheap. Reading five of them against one issue still costs a maintainer an evening, and the four people who lose usually hear nothing.

So I built Bakeoff. When two or more PRs say `Closes #N`, it opens a Switch room for issue N. GitHub's checks fill a matrix. Two agents read every diff against the issue's "Done when" list. A maintainer picks one, and Switch asks a person to approve before the merge agent acts. Then every other PR gets a note that names what it missed.

This post covers what a first-time Switch user needs to get that far, including the snags I hit.

## What Switch gives you, in one paragraph

A Switch **room** is a channel in your chat app (Slack, Mattermost, Teams, Discord, Telegram) with agents in it. Each agent is a real coding agent (Claude Code, Codex, OpenCode and others) run by an **agent controller** on some machine. Rooms have instructions every agent reads, documents, and **roles** that agents assume (a role can be exclusive: one holder at a time). Each agent has an **addressing policy** that decides who may give it instructions. When an agent wants to run a tool it isn't allowed to run alone, Switch posts an **approval card** in the room, and a person allows or declines it. Rooms can be created from **YAML templates**, by people or by agents.

Bakeoff is mostly those six features put in the right order.

## Step 1: a server without a desktop

Switch Console is the easy path on a laptop. I wanted the server on a cloud box so friends could join from Slack, so I ran it headless:

- The Switch repo publishes a Docker Compose file. Pin the version (the file refuses to start without one), set `MATRIX_SERVER_NAME` (it names every user and room forever, so choose before the first start), `AGENT_REGISTRATION_TOKEN` and `JWT_SECRET_KEY`, and turn on the `gateway` profile for the admin API. The `collab` profile adds a Mattermost, which is handy until your Slack app is ready.
- Everything binds to `127.0.0.1`. I never opened a port: I reached the box through AWS Systems Manager.
- Agents run under `switch-agent-controller`. You enroll it once with a code from the gateway (`POST /gateway/management/enrollment-codes`), then run it as a service. It needs your model keys in its environment file. One catch: Switch checks a provider with a real test prompt, so an expired key shows up as "login missing", not as a key error.

## Step 2: three agents with three jobs

| Agent | Runs | Job |
|---|---|---|
| `bakeoff-checker` | Claude Code, auto mode | read each PR against the checklist |
| `bakeoff-second` | OpenCode | the same job, independently |
| `bakeoff-merge` | Claude Code, approvals required | execute a maintainer's pick, nothing else |

Agents are created through the gateway (`POST /gateway/management/agents`) with a provider, a model and whether auto mode is on. Each one gets a working directory on the controller machine (`~/.switch/agents/<server>/<name>`), and that is where your own configuration goes.

**Giving agents your own tools.** Switch doesn't configure MCP servers for you; the provider does. For Claude Code, a `.mcp.json` in the agent's directory is picked up beside Switch's own `switch` tools. For OpenCode, an `opencode.json` there does the same. My Bakeoff MCP server reads its agent's name from the environment that config sets, so one agent can't record verdicts as another.

**One tool, one card.** I expected `permissions.allow` in the merge agent's project settings to let its read-only tools through silently, so that only `merge_pick` would raise a card. In my setup the first card asked to run `contest_matrix`. The fix that holds: the merge agent's MCP server exposes `merge_pick` and nothing else, so every pick produces exactly one card: "bakeoff wants to run merge_pick", with the PR number and the name of the person who asked.

**Free models.** OpenCode lists free models, and they worked on my laptop. From the cloud box every one answered "Free usage limit reached", so the second reader ended up on a paid model. Test the route from the machine that will run it.

## Step 3: a room created by code

Bakeoff's watcher is a small bot agent, registered with `POST /agents/register-known`. It creates each contest room with `POST /agents/{id}/ops/create_room_from_yaml`, sending the template and its inputs. Things I learnt the hard way:

- **The kickoff is checked before anything is created.** When an agent runs a template, the kickoff speaks for that agent, and Switch refuses to create the room if a mentioned agent would ignore it ("they do not accept messages from bakeoff-intake"). Widen the readers' addressing policy to admit the bot first. It's one `PUT /gateway/agents/{id}/addressing-policy` per agent.
- **The bot must be in its own room** to post there, so it's in the template's agent list.
- **Roles need a clear owner.** My first kickoff said "checker: X, second-opinion: Y", and Y grabbed `checker` first. The exclusive lease did its job and refused X, who then took the leftover role. Now the instructions say "assume your own role and no other".
- Room **references** take connector types (GitHub, Jira, Drive, Confluence), not plain URLs, so the contest brief is a room **document** instead.
- The task-delegation protocol mentioned in some docs pages is not in the current server. Roles, mentions and approvals did everything I needed.

## Step 4: who may tell the merge agent what

The merge agent's addressing policy admits its owner (the maintainer) and a list of other maintainers, and no agents at all. That has two effects you can see on camera:

- a contributor typing "@bakeoff-merge pick #4" is simply not delivered to it;
- a reader agent can never trigger a merge, even by mistake.

The same policy decides who may answer its approval cards. Bakeoff adds its own guard in code: a contest is decided once. A second pick is refused with the name and time of the first, and nothing is posted.

## Step 5: Slack

Create the Slack app from the manifest in Switch's docs (Socket Mode, so the box needs no public address). Generate the app-level token (`xapp-`), install the app to get the bot token (`xoxb-`), note the workspace ID, and register the bridge with the gateway (`POST /gateway/collaborations`). Agents then post under their own names. Two gotchas: people have to exist on the bridge before a template can add them by name, and the admin account has to be added to a room before it can read or post through the gateway.

## What a run looks like

The first full run was a small rehearsal contest: issue #7 with two PRs, both green on CI. The watcher opened `#bakeoff-7` in Slack and posted the matrix. Both readers took their roles, read both diffs, and agreed: #6 met both checklist items, #8 also edited `README.md`, which the issue's scope didn't allow. I typed `@bakeoff-merge pick #6`. A card appeared under my message, "bakeoff wants to run merge_pick", with the issue, the PR and my name. I clicked **Allow once**. Switch recorded the answer as mine, from Slack. GitHub then got one merge with a "Picked in Bakeoff" comment, and #8 was closed with a note quoting the item it missed and both readers' evidence. When I tried `pick #8` afterwards, it was refused: the contest had been decided.

The real contest is bigger. On my own repository I gave one issue to four coding agents (Claude Code, Kimi Code, Pi and OpenCode), same prompt, file-editing tools only. All four PRs pass CI, so CI alone can't pick: one PR added two files outside the issue's scope, and the rest differ on the checklist. That's the work the room is for.

## What I'd tell a first-time Switch user

1. Start with one agent replying "PONG" in one room. Everything else builds on that loop.
2. Put your agents' own tools in their working directories, and keep the tool list of any agent that acts on the world down to the one tool that needs a person.
3. Treat addressing policies as your permission system. They decide who can instruct an agent and who can approve its actions.
4. Let code decide facts and let agents decide judgement calls, and write that line into the room's instructions.

The code, the room template and the setup scripts are at https://github.com/itssaharsh/bakeoff.
