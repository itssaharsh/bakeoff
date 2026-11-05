#!/bin/bash
# Rebuild the demo contest: four coding agents fix the same issue, each in its own
# git worktree, with the same prompt and file-editing tools only. You then commit
# each worktree on its branch and open one PR per agent ("[agent] ..." titles,
# body starting "Closes #<issue>"). Used to create itssaharsh/bakeoff#2-#5.
#   usage: scripts/race.sh PROMPT_FILE  (run from the repo root)
set -euo pipefail
P="$(cat "$1")"
R=../race
for a in claude kimi pi opencode; do git worktree add -q "$R/$a" -b "race/$a" 2>/dev/null || true; done
(cd $R/claude && claude -p "$P" --allowedTools "Read,Edit,Write,Glob,Grep,Bash(uv run pytest:*),Bash(uv sync:*)" > ../claude.log 2>&1)
(cd $R/kimi && kimi -p "$P" > ../kimi.log 2>&1)                      # Kimi Code, default approval mode
(cd $R/pi && pi -p --model anthropic/claude-haiku-4-5 --tools read,edit,write,grep,find,ls "$P" > ../pi.log 2>&1)
(cd $R/opencode && echo '{"permission":{"bash":"deny","webfetch":"deny","edit":"allow"}}' > opencode.json \
   && opencode run -m opencode/deepseek-v4.1-flash-free "$P" > ../opencode.log 2>&1)
echo "done: review each worktree, commit, push race/<agent>, open the PRs"
