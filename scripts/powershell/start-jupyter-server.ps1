# Start JupyterLab for jupyter-mcp-server (run in its own terminal; it blocks).
#
# Thin wrapper around the validated launcher in the project skill
# .claude/skills/jupyter-mcp-workflow (collaboration mode, token auth, bounded
# YStore that fixes the "Notebook has 0 cells" bug, temp cleanup on exit).
#
# Server root = code/  (so both LibreVNA-dev/notebook and ena-dev/notebook are
# visible to the MCP; notebook paths are relative to code/). Venv = code/.venv.
# Token/port must match .mcp.json (my_secure_token_123, http://127.0.0.1:8888).
#
# Usage (from anywhere):
#   pwsh -File scripts\powershell\start-jupyter-server.ps1            # port 8888
#   pwsh -File scripts\powershell\start-jupyter-server.ps1 -Port 8899 # extra args pass through
# Stop: Ctrl+C. Then in Claude Code: /mcp -> reconnect jupyter-mcp-server.

$RepoRoot = Split-Path -Parent (Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path))
$Launcher = Join-Path $RepoRoot ".claude\skills\jupyter-mcp-workflow\scripts\start-jupyter-server.ps1"

if (-not (Test-Path $Launcher)) {
    Write-Error "Skill launcher not found: $Launcher (pull jupyter-mcp-workflow from my-skills into .claude/skills/)."
    exit 1
}

& $Launcher -ProjectRoot (Join-Path $RepoRoot "code") @args
