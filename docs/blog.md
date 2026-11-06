# I ran a headless Switch on a cloud box and let it pick one pull request out of five

*Notes from setting up Switch for the first time: a Docker Compose server on a small cloud box, three agents with three jobs, and a Slack room that decides which pull request gets merged.*

## The problem I picked

During the Flip the Switch hackathon, Switch's own repository grew to nearly 400 open pull requests, and its maintainer wrote: "Only one PR will be selected per issue." Coding agents make a PR cheap. Reading five of them against one issue still costs a maintainer an evening, and the four people who lose usually hear nothing.

So I built Bakeoff. When two or more PRs say `Closes #N`, it opens a Switch room for issue N. GitHub's checks fill a matrix. Two agents from different vendors read every diff against the issue's "Done when" list. A maintainer picks one, a person approves the merge on a card in the room, and every other PR gets a note naming the checklist item it missed.

This post is the Switch part: what a first-time user needs, and the snags I hit.

## Six Switch terms, in one paragraph

A **room** is a channel in your chat app (I used Slack) with agents in it. Each agent is a real coding agent, such as Claude Code or OpenCode, run by an **agent controller** on a machine you own. A room has instructions every agent reads, documents, and **roles** (a role can be exclusive: one holder at a time). Each agent has an **addressing policy** that says who may give it instructions. When an agent wants to run a tool it may not run alone, Switch posts an **approval card** in the room and a person allows or declines. Rooms can be created from a **YAML template**, by a person or by an agent. Bakeoff is these six things put in the right order.

## Step 1: a server without a desktop

Switch Console is the easy path on a laptop. I wanted friends to join from Slack, so I ran the server headless on a cloud box.

- Switch publishes a Docker Compose file. Pin a version (it refuses to start without one). Set `MATRIX_SERVER_NAME` first: it becomes part of every user and room name, so choose it before the first start. Also set `AGENT_REGISTRATION_TOKEN` and `JWT_SECRET_KEY`, and enable the `gateway` profile.
- Everything listens on `127.0.0.1`. I opened no port and reached the box through AWS Systems Manager.
- Agents run under `switch-agent-controller`. Enroll it once with a code from the gateway (`POST /gateway/management/enrollment-codes`), then run it as a service with your model keys in its environment file. An expired model key shows up as "login missing", because Switch checks a provider with a real test prompt.

## Step 2: three agents, three jobs

| Agent | Runs | Job |
|---|---|---|
| `bakeoff-checker` | Claude Code, auto mode | read each PR against the checklist |
| `bakeoff-second` | OpenCode | the same job, independently |
| `bakeoff-merge` | Claude Code, approvals required | execute a maintainer's pick, nothing else |

You create agents through the gateway (`POST /gateway/management/agents`) with a provider, a model and an auto-mode flag. Each agent gets a working directory on the controller machine, `~/.switch/agents/<server>/<name>`, and that is where your own configuration goes.

**Your own tools.** Switch doesn't configure MCP servers; the agent's provider does. For Claude Code, a `.mcp.json` in the agent's directory loads next to Switch's own tools. For OpenCode, an `opencode.json` there does the same. Bakeoff's MCP server reads the agent's name from the environment that config sets, so one agent cannot record verdicts as another.

**One tool, one card.** I expected `permissions.allow` in the merge agent's project settings to let its read-only tools through silently, so only `merge_pick` would raise a card. In my setup the first card asked to run `contest_matrix`. What held: the merge agent's MCP server exposes `merge_pick` and nothing else. Now every pick produces exactly one card, "bakeoff wants to run merge_pick", with the PR number and the name of the person who asked.

**Free models.** OpenCode's free models worked on my laptop. From the cloud box every one answered "Free usage limit reached", so the second reader runs on Claude Haiku.

## Step 3: a room created by code

Bakeoff's watcher is a bot agent registered with `POST /agents/register-known`. It creates each room with `POST /agents/{id}/ops/create_room_from_yaml`, sending the template and its inputs. What I learned:

- **The kickoff is checked first.** When an agent runs a template, the kickoff message speaks for that agent. Switch refuses to create the room if a mentioned agent would ignore it ("they do not accept messages from bakeoff-intake"). Widen the readers' addressing policy to admit the bot: one `PUT /gateway/agents/{id}/addressing-policy` per agent.
- **The bot must be in its template's agent list** to post in its own room.
- **Say whose role is whose.** My first kickoff said "checker: X, second-opinion: Y", and Y grabbed `checker` first. The exclusive lease refused X, who then took the leftover role. The instructions now say "assume your own role and no other".
- **An agent holds one role across all rooms.** Mine release the role after posting their reading, or the next contest waits.
- **References take connector types**, not plain URLs, so the contest brief is a room **document**.

## Step 4: who may tell the merge agent what

The merge agent's addressing policy admits its owner and a short list of maintainers, and no agents. So a contributor typing "@bakeoff-merge pick #4" is not delivered to it, and a reader agent can never trigger a merge.

Bakeoff adds guards in code. A PR whose CI failed cannot be picked. The merge is pinned to the commit the readers read, so GitHub refuses it if the PR moved. A contest is decided once: a second pick is refused with the name and time of the first.

One limit: the name on the GitHub comment is the maintainer the merge agent says asked. The card shows that name before anything runs and Switch records who answered, but my tool does not read that record yet.

## Step 5: Slack

Create the Slack app from the manifest in Switch's docs (Socket Mode, so the box needs no public address). You need its app-level token (`xapp-`), bot token (`xoxb-`) and workspace ID to register the bridge with the gateway (`POST /gateway/collaborations`). Agents then post under their own names. One gotcha: people must exist on the bridge before a template can add them by name.

## What a run looks like

My first full run was a small rehearsal: issue #7, two PRs, both green on CI. The watcher opened `#bakeoff-7` in Slack and posted the matrix. Both readers took their roles and read both diffs. PR #6 met both checklist items; #8 also edited `README.md`, outside the issue's scope. I typed `@bakeoff-merge pick #6`. A card appeared under my message with the issue, the PR and my name. I clicked **Allow once**, and Switch recorded the answer as mine, from Slack. GitHub got one merge with a "Picked in Bakeoff" comment, and #8 was closed with a note naming the item it missed. When I tried `pick #8` afterwards, it was refused: the contest was decided.

The real contest was harder. I gave one issue to four coding agents (Claude Code, Kimi Code, Pi and OpenCode) with the same prompt. All four PRs pass CI, so CI cannot pick. In the rehearsal the readers found a real bug in Pi's PR (its command always reports 0 items met), two files outside the scope, and two items where they split. Only Claude's PR tests the exact error message and exit code.

In the recorded run both readers flagged Pi's two extra files, and they split on the bug: one found it, one didn't, and the matrix said so. A friend in the room asked the checker why #4 wasn't ready and got the file and line, then tried to make the merge agent merge it, and Switch didn't deliver the message. I picked Claude's #2, allowed the card once, and the other three PRs were closed with notes naming what they missed. The same room then picked Bakeoff's own landing page from four agents' designs, with pictures of each posted in Slack, and the merge put it live.

## What I'd tell a first-time Switch user

1. Start with one agent answering "PONG" in one room. Everything else builds on that loop.
2. Put each agent's own tools in its working directory. For any agent that acts on the world, cut its tool list to the one tool that needs a person.
3. Treat addressing policies as your permission system. They decide who can instruct an agent and who can answer its cards.
4. Let code decide facts and agents decide judgement calls, and write that rule into the room's instructions.

## Try it

The repo has the room template, the MCP tools and the setup scripts: https://github.com/itssaharsh/bakeoff. `uv run bakeoff matrix OWNER/REPO ISSUE` prints a contest matrix in a terminal without Switch.
