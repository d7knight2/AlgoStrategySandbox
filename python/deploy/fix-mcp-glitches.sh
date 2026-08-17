#!/usr/bin/env bash
set -euo pipefail
# Apply fleet MCP pathspec + timeout fixes and sync to live (no MCP self-restart).
PR=/home/d7knight/repos/d7knight2/pi-remote
python3 "$PR/scripts/26-patch-fleet-server-glitches.py"
python3 "$PR/scripts/23-sync-fleet-policy.py"
echo "Patched. Restart MCP outside of an MCP tool call:"
echo "  systemctl --user restart pi-mcp.service"
