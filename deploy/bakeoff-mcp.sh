#!/bin/bash
# Start the Bakeoff MCP server for one Switch agent.
# The agent's MCP config runs this with BAKEOFF_AGENT (and, for the merge agent only,
# BAKEOFF_ALLOW_MERGE=1) in its environment. Shared settings come from ~/bakeoff.env.
set -a
. "${BAKEOFF_ENV:-$HOME/bakeoff.env}"
set +a
exec "$HOME/.local/bin/uv" run --quiet --project "${BAKEOFF_HOME:-$HOME/bakeoff}" bakeoff mcp
