# Setup: install the launcher and MCP config into a project

Goal: a JupyterLab server in collaboration mode that `jupyter-mcp-server` (run by
`uvx` from `.mcp.json`) can drive, with the project folder as the server root.

Primary platform is Windows/PowerShell. `scripts/start-jupyter-server.sh` is the
Git Bash / Linux / macOS equivalent (tested on Git Bash only).

## 1. Prerequisites

- `uv` on PATH (`uvx --version`). `.mcp.json` runs `uvx jupyter-mcp-server`, so the
  MCP server lives in uv's own cache, not in the project venv. First start downloads it.
- A Python venv with the server-side packages (`templates/requirements-jupyter.txt`):

  ```powershell
  uv venv <project>\.venv                      # or one shared venv for several projects
  uv pip install --python <venv>\Scripts\python.exe -r <skill>\templates\requirements-jupyter.txt
  ```

  Upstream (README of datalayer/jupyter-mcp-server, 2026-10-23) asks for
  `jupyterlab jupyter-collaboration jupyter-mcp-tools ipykernel`, unpinned. Verified
  set: jupyterlab 4.6.3, jupyter-collaboration 5.0.2, pycrdt 0.14.4, pycrdt-store 0.1.5,
  ipykernel 7.3.0, with jupyter-mcp-server 2.2.4. Older READMEs pinned
  `jupyterlab==4.4.1 jupyter-collaboration==4.0.2` and `datalayer_pycrdt`; that is obsolete.
  Add the project's own notebook deps (torch, pandas, ...) to the same venv, since the
  kernels run in it.

## 2. Copy the files

```
<project>/
  .mcp.json                          <- templates/mcp.json, edit token (and port)
  scripts/start-jupyter-server.ps1   <- scripts/ (keep .ps1 and ystore_prefix.py together)
  scripts/ystore_prefix.py
  scripts/start-jupyter-server.sh    <- optional
```

```powershell
$skill = "<path>\jupyter-mcp-workflow"
New-Item -ItemType Directory -Force <project>\scripts | Out-Null
Copy-Item $skill\scripts\start-jupyter-server.ps1, $skill\scripts\ystore_prefix.py <project>\scripts\
Copy-Item $skill\templates\mcp.json <project>\.mcp.json     # merge by hand if .mcp.json already exists
```

The launcher may also stay in the skill folder and be called with
`-ProjectRoot <project>`; it only needs `ystore_prefix.py` next to itself.

### Sharing one launcher across many projects

Keep one copy in a parent folder and give each project a two-line wrapper:

```powershell
# <project>\scripts\start-jupyter-server.ps1
$PodRoot = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
& "<parent>\scripts\start-jupyter-server.ps1" -ProjectRoot $PodRoot @args
```

With a shared venv, set `$env:JUPYTER_VENV = "<parent>\.venv"` (or pass `-VenvPath`).
Only one project's server can use a port at a time: stop one before starting the next,
or give each project its own `-Port` and matching `JUPYTER_URL`.

## 3. Configure `.mcp.json`

Template (`templates/mcp.json`):

| env | value | why |
|---|---|---|
| `JUPYTER_URL` | `http://127.0.0.1:8888` | literal IPv4. `localhost` can resolve to `::1` first; the server binds `0.0.0.0` (IPv4) only, and the MCP's kernel client then fails with `[WinError 10061]` even though `list_files` works |
| `JUPYTER_TOKEN` | same string as the launcher's `-Token` / `$env:JUPYTER_TOKEN` | mismatch = 403 on every call |
| `DOCUMENT_ID` | `""` | optional default notebook path relative to the server root; empty means pick with `use_notebook` |
| `ALLOW_IMG_OUTPUT` | `true` | image outputs are returned as images instead of text placeholders |
| `REQUEST_TIMEOUT` | `60` | read by `jupyter_nbmodel_client` (default 10 s). A slow room-open past the limit is swallowed silently and shows up as "Notebook has 0 cells". Not listed on the upstream configuration page; confirmed in the installed client's `constants.py` |
| `WEBSOCKETS_MAX_BODY_SIZE` | `67108864` (64 MiB) | read by `jupyter_nbmodel_client` (`client.py`, default 16 MiB) and passed as the websocket `max_size`. The first sync frame carries the whole notebook, so a notebook bigger than this on disk (embedded audio/images in outputs) is closed with 1009 "message too big" and reads as "0 cells". A frame is about the notebook's on-disk size, so raise it further (e.g. `134217728`) for larger notebooks. Also undocumented upstream; verified 2026-10-23 |

Other upstream env vars (configuration page, 2026-10-23): `JUPYTER_PASSWORD`,
`DOCUMENT_URL/TOKEN/PASSWORD`, `DOCUMENT_PROVIDER` (`jupyter`|`datalayer`),
`JUPYTER_MCP_EXECUTION_TIMEOUT` (default 120 s, used when a tool call passes no
`timeout`), `JUPYTER_MCP_MAX_EXECUTION_TIMEOUT` (3600), `RECONNECT_INTERVAL` (0 = off),
`ALLOWED_JUPYTER_MCP_TOOLS`, `OPEN_NOTEBOOK_IN_UI`, `SANDBOX_VARIANT`, `TRANSPORT`, `PORT`,
`MCP_TOKEN` (streamable-http only). Raise `JUPYTER_MCP_EXECUTION_TIMEOUT` for training
notebooks rather than passing a timeout on every call.

Claude Code reads `.mcp.json` at session start. After editing it, run `/mcp` and reconnect,
or restart the session; a running MCP process keeps the old env.

## 4. Start the server

```powershell
cd <project>
& .\scripts\start-jupyter-server.ps1                      # port 8888, <project>\.venv or $env:JUPYTER_VENV
& .\scripts\start-jupyter-server.ps1 -Port 8899 -VenvPath D:\shared\.venv -Token <t>
```

Launcher parameters: `-ProjectRoot` (default: current folder), `-VenvPath` /
`$env:JUPYTER_VENV`, `-Token` / `$env:JUPYTER_TOKEN`, `-Port` / `$env:JUPYTER_PORT`,
`-DotEnv` (default `<project>\.env`). It refuses to start if the port is taken and
prints the owning process.

What it does, and why each flag matters:

- `--LabApp.collaborative=true`: required; the MCP edits the live Yjs document, not the file.
- `--IdentityProvider.token=<token>`, `--ip=0.0.0.0`, `--no-browser`, `allow_origin='*'`,
  `allow_remote_access=true`: as in the upstream quick start.
- `--YDocExtension.ystore_class=ystore_prefix.PrefixTempFileYStore` with `PYTHONPATH`
  pointing at `scripts/`: replaces the unbounded SQLite store (see diagnose.md, "0 cells").
- `.env` into the process only: variables from `<project>\.env` (e.g. `ANTHROPIC_API_KEY`)
  are set for the server process, so kernels inherit them. It prints names, never
  values. Do not set API keys system-wide: a global `ANTHROPIC_API_KEY` makes Claude
  Code bill that key instead of the subscription, and every other program sees it.
- `finally`: deletes `%TEMP%\claude_jupyter_ystore_*` when the server exits (Ctrl+C included).

Run it in its own terminal or a psmux/tmux session; it blocks. Claude's own background
shells end with the session, which would kill the server and every kernel.

## 5. Verify

```powershell
python -I <skill>\scripts\jupyter_health.py --mcp-json <project>\.mcp.json --project <project>
```

Expect `VERDICT: OK`. Then from the MCP client: `list_kernels`, then `use_notebook` on a
notebook you know is not empty and confirm the reported cell count. Full checklist and
every known failure: [diagnose.md](diagnose.md).

## 6. Stop

Ctrl+C in the launcher terminal. If it was started elsewhere:

```powershell
Get-NetTCPConnection -LocalPort 8888 -State Listen | Select-Object OwningProcess
taskkill /F /T /PID <pid>       # kills the kernels too; .ipynb files on disk are unaffected
```

Unsaved kernel state is lost; the notebook contents are already on disk because RTC
autosaves.
