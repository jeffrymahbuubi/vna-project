# Start JupyterLab for jupyter-mcp-server (collaboration mode, token auth).
#
# Usage: run it FROM THE PROJECT FOLDER, or pass -ProjectRoot. The folder it
# runs in becomes the server root: everything the MCP can list, read or edit
# lives under it. Launching from inside scripts/ makes scripts/ the root (a
# real mistake that cost a session; the health check flags it).
#
#   cd <project>; & <path-to-skill>\scripts\start-jupyter-server.ps1
#   & <path-to-skill>\scripts\start-jupyter-server.ps1 -ProjectRoot <project> -Port 8888
#
# Virtual environment (first match wins):
#   1. -VenvPath <dir>   or $env:JUPYTER_VENV   (a shared venv used by several projects)
#   2. <project>\.venv
#   3. error, with the paths it tried
# Venvs break when moved: recreate instead of copying.
#
# Token: -Token, else $env:JUPYTER_TOKEN, else the placeholder below. It must
# equal JUPYTER_TOKEN in the project's .mcp.json.
param(
    [string]$ProjectRoot = (Get-Location).Path,
    [string]$VenvPath = $env:JUPYTER_VENV,
    [string]$Token = $(if ($env:JUPYTER_TOKEN) { $env:JUPYTER_TOKEN } else { "my_secure_token_123" }),
    [int]$Port = $(if ($env:JUPYTER_PORT) { [int]$env:JUPYTER_PORT } else { 8888 }),
    [string]$DotEnv = ""   # default: <project>\.env
)

$ErrorActionPreference = "Stop"

# Directory of this script (holds ystore_prefix.py)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path

$ProjectRoot = (Resolve-Path $ProjectRoot).Path
if ((Split-Path -Leaf $ProjectRoot) -in @("script", "scripts") -and (Test-Path (Join-Path $ProjectRoot "ystore_prefix.py"))) {
    Write-Warning "ProjectRoot '$ProjectRoot' is a script folder. The MCP will only see files under it. Pass -ProjectRoot <project> or cd there first."
}
Set-Location $ProjectRoot
Write-Host "Server root: $ProjectRoot"

# Activate virtual environment
$Candidates = @($VenvPath, (Join-Path $ProjectRoot ".venv")) | Where-Object { $_ }
$Activate = $Candidates | ForEach-Object { Join-Path $_ "Scripts\Activate.ps1" } | Where-Object { Test-Path $_ } | Select-Object -First 1
if ($Activate) {
    Write-Host "Using venv: $(Split-Path -Parent (Split-Path -Parent $Activate))"
    & $Activate
} else {
    Write-Error ("No virtual environment found. Tried: $($Candidates -join ', '). " +
        "Pass -VenvPath <dir>, set `$env:JUPYTER_VENV, or create <project>\.venv (see references/setup.md).")
    exit 1
}
if (-not (Get-Command jupyter -ErrorAction SilentlyContinue)) {
    Write-Error "jupyter is not installed in that venv. Install templates/requirements-jupyter.txt into it."
    exit 1
}

# Port check: only one server per port. A leftover server from another project
# answers with the wrong root and (often) the wrong token.
$Listener = Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction SilentlyContinue | Select-Object -First 1
if ($Listener) {
    $Proc = Get-CimInstance Win32_Process -Filter "ProcessId=$($Listener.OwningProcess)" -ErrorAction SilentlyContinue
    Write-Error ("Port $Port is already in use by PID $($Listener.OwningProcess) ($($Proc.Name)): " +
        "$($Proc.CommandLine)`nStop that server first (taskkill /F /T /PID $($Listener.OwningProcess)) or pass -Port <other>.")
    exit 1
}

# --YDocExtension.ystore_class swaps the default SQLiteYStore (which persists
# every Yjs update forever, unbounded) for a prefixed TempFileYStore. Without
# it, .jupyter_ystore.db grows without limit under heavy editing/output cells
# (248 MB from one notebook's training outputs in the original project), RTC
# replays the whole history on every open, and jupyter-mcp-server's
# use_notebook/read_notebook report "Notebook has 0 cells".
# See https://github.com/jupyterlab/jupyter-collaboration/issues/430
#
# TempFileYStore writes into a tempfile.mkdtemp() folder that Windows never
# auto-cleans, so ystore_prefix.py gives it the prefix "claude_jupyter_ystore_"
# and the finally block below removes exactly those folders, never a generic
# tmp* folder that could belong to another program.
$env:PYTHONPATH = if ($env:PYTHONPATH) { "$ScriptDir;$env:PYTHONPATH" } else { $ScriptDir }

# Secrets for the notebooks (e.g. ANTHROPIC_API_KEY) come from <project>\.env and
# are set for THIS PROCESS ONLY, so the kernels inherit them. Never set API keys
# system-wide: a global ANTHROPIC_API_KEY can make Claude Code bill that key
# instead of the subscription, and every other program sees it too.
if (-not $DotEnv) { $DotEnv = Join-Path $ProjectRoot ".env" }
if (Test-Path $DotEnv) {
    foreach ($line in Get-Content $DotEnv) {
        if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.+?)\s*$') {
            $val = $Matches[2].Trim('"', "'")
            if ($val -and -not [Environment]::GetEnvironmentVariable($Matches[1], "Process")) {
                [Environment]::SetEnvironmentVariable($Matches[1], $val, "Process")
                Write-Host "Loaded $($Matches[1]) from .env"   # name only, never the value
            }
        }
    }
}

Write-Host "Starting JupyterLab on http://127.0.0.1:$Port (token: $Token)"
Write-Host "Put JUPYTER_URL=http://127.0.0.1:$Port in .mcp.json; 'localhost' may resolve to ::1, which this server does not bind."
try {
    jupyter lab --port $Port `
        --IdentityProvider.token=$Token `
        --ServerApp.allow_origin='*' `
        --ServerApp.allow_remote_access=true `
        --ip=0.0.0.0 `
        --no-browser `
        --LabApp.collaborative=true `
        --YDocExtension.ystore_class=ystore_prefix.PrefixTempFileYStore
} finally {
    $ystoreDirs = Get-ChildItem -Path $env:TEMP -Directory -Filter "claude_jupyter_ystore_*" -ErrorAction SilentlyContinue
    if ($ystoreDirs) {
        Write-Host "Cleaning up $($ystoreDirs.Count) YStore temp folder(s) from this session..."
        $ystoreDirs | Remove-Item -Recurse -Force -ErrorAction SilentlyContinue
    }
}
