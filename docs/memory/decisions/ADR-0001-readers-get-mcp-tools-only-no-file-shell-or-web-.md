---
id: ADR-0001
type: decision
title: Readers get MCP tools only; no file, shell or web tools
status: active
scope: project
components: deploy/box-setup.sh
triggers: prompt injection, secrets, bakeoff.env
evidence: deploy/box-setup.sh#L40-60
verified_at: 2026-11-05@041d1d9
relates: 
supersedes: 
helpful: 0
harmful: 0
cite_hash: 387bfafcabc21019
created: 2026-11-05
source: unknown
---

PR diffs are untrusted text and ~/bakeoff.env (GitHub write token, intake key) is readable by the agents' OS user. Readers' Read/Glob/Grep/LS/Bash/Edit/Write/Web/Task are denied (Claude) and all built-in tools disabled (OpenCode). Verified by a canary file the checker could not read (E0024).