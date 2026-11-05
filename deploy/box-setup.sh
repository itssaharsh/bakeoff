#!/bin/bash
# Install or update Bakeoff on the Switch box (Ubuntu, user with uv, Switch agents run by the
# agent controller in ~/.switch/agents/<server>/<agent>). Idempotent. Secrets come from
# AWS SSM Parameter Store and are written only to ~/bakeoff.env (mode 600).
#   usage: deploy/box-setup.sh  (env: AGENTS_DIR, BAKEOFF_MAINTAINER, BAKEOFF_REPOS, INTAKE_AGENT_ID)
set -euo pipefail
AGENTS_DIR=${AGENTS_DIR:-$HOME/.switch/agents/127.0.0.1-8000}
SSM="aws ssm get-parameter --region ${AWS_REGION:-us-east-1} --with-decryption --query Parameter.Value --output text --name"
export PATH=$HOME/.local/bin:/snap/bin:$PATH

if [ -d "$HOME/bakeoff/.git" ]; then git -C "$HOME/bakeoff" pull -q --ff-only; else git clone -q https://github.com/itssaharsh/bakeoff "$HOME/bakeoff"; fi
(cd "$HOME/bakeoff" && uv sync -q --group screens && uv run playwright install --with-deps chromium >/dev/null 2>&1 || uv run playwright install chromium >/dev/null)

umask 077
cat > "$HOME/bakeoff.env" <<ENV
GITHUB_TOKEN=$($SSM /switch-demo/github-token)
BAKEOFF_STATE=$HOME/.bakeoff/state.json
BAKEOFF_READERS=bakeoff-checker,bakeoff-second
SWITCH_API_URL=http://127.0.0.1:8000
BAKEOFF_INTAKE_AGENT_ID=${INTAKE_AGENT_ID:?set INTAKE_AGENT_ID}
BAKEOFF_INTAKE_API_KEY=$($SSM /switch-demo/bakeoff-intake-api-key)
BAKEOFF_MAINTAINER=${BAKEOFF_MAINTAINER:?set BAKEOFF_MAINTAINER}
BAKEOFF_REPOS=${BAKEOFF_REPOS:-itssaharsh/bakeoff}
ENV
umask 022
mkdir -p "$HOME/.bakeoff"
MCP="$HOME/bakeoff/deploy/bakeoff-mcp.sh"

claude_agent() {  # name, allow-merge (0/1), allowed tools (json list), denied tools (json list)
  d="$AGENTS_DIR/$1"; mkdir -p "$d/.claude"
  cat > "$d/.mcp.json" <<J
{"mcpServers": {"bakeoff": {"command": "$MCP", "args": [], "env": {"BAKEOFF_AGENT": "$1", "BAKEOFF_ALLOW_MERGE": "$2"}}}}
J
  cat > "$d/.claude/settings.json" <<J
{"enableAllProjectMcpServers": true, "permissions": {"allow": $3, "deny": $4}}
J
}
claude_agent bakeoff-checker 0 \
  '["mcp__bakeoff__done_when","mcp__bakeoff__contest_matrix","mcp__bakeoff__pr_diff","mcp__bakeoff__record_readings"]' \
  '["Bash","Edit","Write","WebFetch","WebSearch"]'
# The merge agent's MCP server exposes merge_pick only, and it is deliberately NOT allowed here,
# so every pick stops at a Switch approval card for a person.
claude_agent bakeoff-merge 1 '[]' '["Bash","Edit","Write","WebFetch","WebSearch","Read","Glob","Grep"]'

d="$AGENTS_DIR/bakeoff-second"; mkdir -p "$d"
cat > "$d/opencode.json" <<J
{"\$schema": "https://opencode.ai/config.json",
 "mcp": {"bakeoff": {"type": "local", "command": ["$MCP"], "enabled": true, "environment": {"BAKEOFF_AGENT": "bakeoff-second", "BAKEOFF_ALLOW_MERGE": "0"}}},
 "permission": {"bash": "deny", "edit": "deny", "webfetch": "deny"}}
J

mkdir -p "$HOME/.config/systemd/user"
cp "$HOME/bakeoff/deploy/bakeoff-watch.service" "$HOME/.config/systemd/user/"
export XDG_RUNTIME_DIR=/run/user/$(id -u)
systemctl --user daemon-reload
echo "bakeoff installed; start the watcher with: systemctl --user enable --now bakeoff-watch"
