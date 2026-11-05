---
id: L-0001
type: lesson
title: Agent-run room templates: the kickoff is checked against addressing first
status: active
scope: project
components: templates/bakeoff.room.yaml, deploy/switch_admin.py
triggers: kickoff_ignored, create_room_from_yaml, addressing policy
evidence: deploy/switch_admin.py#L1-60
verified_at: 2026-11-05@041d1d9
relates: 
supersedes: 
helpful: 0
harmful: 0
cite_hash: 0858ec2e6dbfa914
created: 2026-11-05
source: unknown
---

When a bot agent runs a template, Switch refuses to create the room if an agent mentioned in the kickoff would not accept messages from the bot (kickoff_ignored). Widen each reader's addressing policy to admit the bot (switch_admin.py policies) before the first contest, and put the bot in the template's agents list or its posts get 403 'not a member'.