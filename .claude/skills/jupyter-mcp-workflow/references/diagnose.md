# Diagnose: health check and known failures

## Run the health check first

```powershell
python -I <skill>\scripts\jupyter_health.py --mcp-json <project>\.mcp.json --project <project>
# or explicitly
python -I <skill>\scripts\jupyter_health.py --url http://127.0.0.1:8888 --token <token>
```

Stdlib only; any Python 3.10+ works, it does not need the venv. It probes
`127.0.0.1`, `[::1]` and the configured host with and without the token, reads
`/api/status`, `/api/kernels`, `/api/contents` and `/api/collaboration/*`, finds the
process that owns the port (Windows), checks its command line for the token, the
`collaborative` flag and the ystore flag, and prints `VERDICT: OK|WARN|FAIL` with one fix
per finding. Exit code 0/1/2.

Reference run against a server launched from inside `script/` with a `localhost` URL
(2026-10-23) produced exactly the two expected failures:

```
[FAIL] JUPYTER_URL uses 'localhost', which resolves to ::1 first, but the server only listens on IPv4 ...
[FAIL] server root looks like the launcher's script folder, not a project (contains ['start-jupyter-server.ps1', 'ystore_prefix.py']) ...
```

The script cannot call MCP tools. After it says OK, finish from the client:
`list_kernels` must succeed and `use_notebook` on a known non-empty notebook must report
its real cell count.

## Failure catalogue

| Symptom | Cause | Fix |
|---|---|---|
| `list_files` works, `list_kernels` / `use_notebook` fail with `[WinError 10061] ... refused` | `JUPYTER_URL=http://localhost:8888`; `localhost` resolves to `::1` first on this machine, the server binds `0.0.0.0` only. The contents API path happens to fall back to IPv4, the kernel/websocket client does not | `JUPYTER_URL=http://127.0.0.1:8888` in `.mcp.json`, then restart the MCP (`/mcp` reconnect or new session). The launcher prints this reminder at start |
| MCP lists only `start-jupyter-server.ps1`, `ystore_prefix.py`; notebooks "not found" | Server launched from inside `scripts/`; the cwd became the server root | Stop it; `cd <project>` first or pass `-ProjectRoot <project>`. Health check: "root looks like a script folder" |
| Every MCP call returns 403 / "forbidden" | Token in `.mcp.json` differs from the launcher's `-Token` / `$env:JUPYTER_TOKEN`; or another project's server owns the port with its own token | Make both equal and restart the MCP; or stop the other server. Health check compares the listener's command line with the configured token |
| `curl http://127.0.0.1:8888/api/status` returns 403 | No token in the request. This is normal, not a failure | `curl "http://127.0.0.1:8888/api/status?token=<token>"` must return 200 |
| Launcher exits with "Port 8888 is already in use by PID ..." | A server from another project (or an orphan) is listening | Stop that one (`taskkill /F /T /PID <pid>`) or use `-Port` + matching `JUPYTER_URL`. One server per port |
| `use_notebook` / `read_notebook`: "Notebook has 0 cells" on a non-empty notebook, YStore fix active | **Notebook bigger than the MCP client's websocket frame limit.** `jupyter_nbmodel_client` passes `WEBSOCKETS_MAX_BODY_SIZE` (default 16 MiB) as `max_size`; the SYNC_STEP2 frame is the whole Y doc (about the on-disk size), the `websockets` library closes with 1009 "message too big", `start()` waits `REQUEST_TIMEOUT`, logs only "Document ... not yet synced." and returns an empty doc. Tell-tale: server log shows "Content in room ... loaded from file" and "Cleaning room" ~2 s after the request, no traceback; `use_notebook` works on small notebooks on the same server; the file is > 16 MB (embedded audio/images in outputs) | `"WEBSOCKETS_MAX_BODY_SIZE": "67108864"` in `.mcp.json`, reconnect the MCP (verified: same 19.8 MB notebook went from 0 to 50 cells). Or clear the heavy outputs. `jupyter_health.py --check-notebooks <dir>` lists the files over the limit |
| Same symptom, server log has a traceback on room-open, or `.jupyter_ystore.db` is huge | (a) room-open crashed server-side: `TypeError: TempFileYStore.__init__() got an unexpected keyword argument 'config'` (ystore subclass without the `config=` override); (b) default SQLiteYStore with a huge `.jupyter_ystore.db` replaying the whole history (jupyter-collaboration #430); (c) a genuinely slow open past `REQUEST_TIMEOUT` (default 10 s). In all cases `jupyter_nbmodel_client` swallows the sync timeout and returns an empty doc | Use the bundled `ystore_prefix.py` (has the override) and launch only via the launcher (sets `PYTHONPATH` and the flag). Set `REQUEST_TIMEOUT=60`. Delete a stale `.jupyter_ystore.db` while the server is stopped. Then run the verification below |
| Server log: `[E] Notebook JSON is invalid: '<id>' is too long` (or `does not match '^[a-zA-Z0-9-_]+$'`) on open, plus "Notebook ... is not trusted" | Cell ids violate the nbformat 4.5 schema (1-64 chars of `a-z A-Z 0-9 - _`). Downloaded notebooks from some sources use long descriptive ids (93 chars seen). The server still loads the content and the MCP reads the cells fine (verified 2026-10-23: a 58 KB notebook with 11 ids of 65-91 chars synced and read all 46 cells, and the 19.8 MB notebook with 18 such ids read all 50 cells once the websocket limit was raised), so by itself this is NOT a "0 cells" cause, but anything that validates (nbformat, nbconvert, CI, trust) rejects the file, and it masks the real cause when it coincides with a >16 MB notebook | `python -I scripts/fix_cell_ids.py <dir>` (dry run), then `--apply` with the server stopped (`--force` only if the notebooks are not open anywhere). Deterministic mapping, only id strings change, `--backup-dir` / `--map-out` available. A re-download from the same source brings the long ids back, so re-run after harvesting |
| HTTP 500 in the server log at `jupyter_server_ydoc/handlers.py` on every open | Same TypeError as above, or `ystore_prefix` not importable (server started with a bare `jupyter lab` copy-paste, so no `PYTHONPATH`) | Relaunch via the launcher; never a hand-typed `jupyter lab ...` |
| Health check: "/api/collaboration/* is missing" | `jupyter-collaboration` not installed in the venv, or started without `--LabApp.collaborative=true` | Install `templates/requirements-jupyter.txt`, relaunch via the launcher |
| MCP tools absent in Claude Code / "server still connecting" forever | `uvx` not on PATH, first download in progress, or `.mcp.json` not at the project root Claude was started in | `uvx --version`; `uvx jupyter-mcp-server --help` once by hand; `/mcp` to see the error |
| Edits made by Claude disappear, or Claude's edits overwrite the user's | Someone wrote the `.ipynb` on disk while the server held the live document (NotebookEdit, `nbformat`, editors) | Never write the file while the server is up; edit only through MCP tools. If a file write is unavoidable: `unuse_notebook`, close the tab in JupyterLab, write, reopen |
| `execute_cell` returns a timeout but the cell keeps running | Expected: execution is server-side; the tool only stopped waiting | Pass a larger `timeout`, raise `JUPYTER_MCP_EXECUTION_TIMEOUT`, or poll with `read_cell` / `execute_code` (`%whos`) |
| Image outputs come back as `[image]` text | `ALLOW_IMG_OUTPUT=false` | Set it to `true` in `.mcp.json`, restart the MCP |
| Kernel env lacks `ANTHROPIC_API_KEY` etc. | `.env` missing in the project root, or the variable was already set (the launcher does not override existing process vars) | Put it in `<project>\.env`; the launcher prints `Loaded <NAME> from .env` |
| `%TEMP%` fills with `claude_jupyter_ystore_*` folders | Server killed in a way that skipped the `finally` block (e.g. `taskkill` from elsewhere) | Safe to delete them while no server is running |

## Telling the "0 cells" causes apart

| Observation | Websocket limit | YStore / TypeError | Invalid ids only |
|---|---|---|---|
| Server log on open | "loaded from file", no traceback | traceback at `jupyter_server_ydoc/handlers.py` (HTTP 500) | `[E] Notebook JSON is invalid ... is too long`, then "loaded from file" |
| `%TEMP%\claude_jupyter_ystore_*` appears | yes | no (or server not launched via the launcher) | yes |
| Small notebook on the same server | reads fine | also 0 cells | reads fine |
| File size | > `WEBSOCKETS_MAX_BODY_SIZE` (16 MiB default) | any | any; cells still read |
| Direct probe (`jupyter_nbmodel_client`, see below) | `ConnectionClosedError: 1009 message too big` | timeout, no SYNC_STEP2 | synced, real cell count |

Direct probe without the MCP (from the uvx env, read-only; replace URL/token/path):
```python
# REQUEST_TIMEOUT=60 uvx --from jupyter-mcp-server python probe.py
import asyncio, logging
from jupyter_nbmodel_client import NbModelClient, get_jupyter_notebook_websocket_url
logging.basicConfig(level=logging.WARNING)
async def main():
    ws = get_jupyter_notebook_websocket_url(server_url="http://127.0.0.1:8888", path="<nb.ipynb>", token="<token>", timeout=60)
    c = NbModelClient(ws, path="<nb.ipynb>", timeout=60)          # add ws_max_body_size=64*2**20 to test the size fix
    await c.start(); await asyncio.sleep(1); print("synced", c.synced, "cells", len(c)); await c.stop()
asyncio.run(main())
```

## The YStore "0 cells" bug, verified end-to-end

History: an earlier subclass only set `prefix_dir`. `jupyter_server_ydoc.app.YDocExtension`
builds the store with `partial(self.ystore_class, config=self.config)` (line 152 in
jupyter-server-ydoc 3.0.2); `pycrdt.store.TempFileYStore.__init__(path, metadata_callback=None,
log=None)` has no `config`, so every room-open raised a TypeError (HTTP 500). Client-side,
`jupyter_nbmodel_client` waited `REQUEST_TIMEOUT` (10 s) for SYNC_STEP2, swallowed the
timeout and returned an empty document, hence "0 cells" with no visible error. The
override in `scripts/ystore_prefix.py` absorbs the kwarg. Fixed and verified 2026-09-02.

Verify through the real code path, not a proxy (an `import_item()` check once passed while
the bug was still live):

1. Watch the server's stdout while connecting: no traceback on room-open.
2. `use_notebook` + `read_notebook` on a known non-empty notebook returns the real count
   (reference: "Notebook has 50 cells" with real content).
3. A fresh `%TEMP%\claude_jupyter_ystore_<random>` folder appears at the moment of
   connecting. That proves `PrefixTempFileYStore` actually instantiated.

## Finding and stopping the right server

```powershell
Get-NetTCPConnection -LocalPort 8888 -State Listen | Select-Object OwningProcess
Get-CimInstance Win32_Process -Filter "ProcessId=<pid>" | Select-Object ParentProcessId, CommandLine
taskkill /F /T /PID <pid>
```

The command line shows the venv path and token, which tells you which project started it.
Killing it ends the kernels (in-memory variables are lost; `.ipynb` files stay). Relaunch
only with the launcher. Cells that depended on kernel state need re-running.

## Restarting the MCP after a `.mcp.json` change

The MCP process inherits its env at start. In Claude Code: `/mcp`, pick
`jupyter-mcp-server`, reconnect; or start a new session. `connect_to_jupyter` can switch
URL/token at runtime without a restart, but it does not persist and it checks
`/api/status` with the token first, so it fails loudly on a bad URL.
