---
id: F-0001
type: failure
title: Switch Claude agent: project permissions.allow did not cover MCP tools
status: active
scope: project
components: deploy/box-setup.sh, bakeoff/mcp_server.py
triggers: approval card, permissions.allow, mcp tool, auto_mode false
evidence: bakeoff/mcp_server.py#L1-40
verified_at: 2026-11-05@041d1d9
relates: 
supersedes: 
helpful: 0
harmful: 0
cite_hash: 4e35669bbeed8116
created: 2026-11-05
source: unknown
---

Attempted: allow mcp__bakeoff__contest_matrix in <agentdir>/.claude/settings.json so only merge_pick raised a card. Error: the merge agent's first card asked to run contest_matrix. Root cause (observed, not traced in Switch code): with auto_mode false every non-switch MCP tool reaches canUseTool regardless of project allow. Fix: the merge agent's MCP server exposes merge_pick only (BAKEOFF_ALLOW_MERGE=1). Lesson: when an agent must ask a person before acting, shrink its tool list to the one action instead of relying on allow lists. Cheapest early check: one mention, then GET /gateway/agent-sessions/approvals.