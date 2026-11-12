---
name: jupyter-mcp-workflow
description: "Set up, health-check and work with Jupyter notebooks through the jupyter-mcp-server MCP (datalayer, run via uvx): a JupyterLab launcher in collaboration mode with token auth, venv resolution, .env-into-process, a bounded YStore (fixes the 'Notebook has 0 cells' bug) and temp cleanup; a .mcp.json template; a stdlib health check that probes 127.0.0.1 vs ::1 vs localhost, token, kernels, server root and port conflicts; and a tool-usage playbook (use_notebook / read / edit / execute loop, cell ids vs indexes, execute_code for scratch only, timeouts). Use when a project needs jupyter-mcp-server installed or configured, when MCP notebook tools fail (WinError 10061, 403, 0 cells, wrong root, port in use), or when editing or running notebooks via MCP tools."
argument-hint: "[setup <project> | diagnose | playbook]"
---

# jupyter-mcp-workflow

Drive Jupyter notebooks from Claude Code through `jupyter-mcp-server` without the
failure modes that cost whole sessions. Three entry points; pick the one that matches.

| Need | Go to |
|---|---|
| Install the launcher + `.mcp.json` into a project, venv packages, start/stop | [references/setup.md](references/setup.md) |
| Something fails (refused, 403, "0 cells", wrong files, port busy) | run `scripts/jupyter_health.py`, then [references/diagnose.md](references/diagnose.md) |
| Edit or run notebooks through the MCP tools | [references/playbook.md](references/playbook.md) |

## Files

```
scripts/start-jupyter-server.ps1   launcher (Windows, primary): collaborative JupyterLab, token, venv, .env, ystore, cleanup
scripts/start-jupyter-server.sh    same for Git Bash / Linux / macOS (tested on Git Bash)
scripts/ystore_prefix.py           PrefixTempFileYStore; must sit next to the launcher
scripts/jupyter_health.py          health check, stdlib only, VERDICT + a fix per failure; --check-notebooks for ids/size
scripts/fix_cell_ids.py            dry-run/--apply rewrite of invalid nbformat cell ids, only the id strings change
scripts/nbcheck.py                 shared notebook checks (id rule, walker, websocket size limit)
templates/mcp.json                 .mcp.json for the project root (uvx jupyter-mcp-server, 127.0.0.1)
templates/requirements-jupyter.txt venv packages for the server side, with verified versions
references/setup.md, diagnose.md, playbook.md
```

## Quick start

```powershell
# 1. venv with jupyterlab + jupyter-collaboration + ipykernel (+ the notebooks' own deps)
uv venv <project>\.venv
uv pip install --python <project>\.venv\Scripts\python.exe -r <skill>\templates\requirements-jupyter.txt

# 2. files into the project
Copy-Item <skill>\scripts\start-jupyter-server.ps1, <skill>\scripts\ystore_prefix.py <project>\scripts\
Copy-Item <skill>\templates\mcp.json <project>\.mcp.json      # set JUPYTER_TOKEN (and port)

# 3. start FROM THE PROJECT FOLDER, in its own terminal (blocks)
cd <project>; & .\scripts\start-jupyter-server.ps1            # -Port, -Token, -VenvPath, -ProjectRoot

# 4. verify, then (re)connect the MCP in Claude Code (/mcp) and call list_kernels
python -I <skill>\scripts\jupyter_health.py --mcp-json <project>\.mcp.json --project <project>
```

## Hard rules

1. **`JUPYTER_URL` is `http://127.0.0.1:<port>`, never `localhost`.** The server binds IPv4
   only; `localhost` may resolve to `::1` first and the MCP's kernel client then fails with
   `[WinError 10061]` while `list_files` still works. Restart the MCP after changing `.mcp.json`.
2. **Launch from the project folder (or `-ProjectRoot`).** The cwd is the server root and
   the only thing the MCP can see. Launching from `scripts/` exposes `scripts/`.
3. **Launch only with the launcher.** A hand-typed `jupyter lab` lacks the `PYTHONPATH`
   and ystore flag, so the "0 cells" bug returns, and skips `.env` and cleanup.
4. **Same token in the launcher and in `.mcp.json`; one server per port.** Stop one
   project's server before starting another's on the same port.
5. **Never write a `.ipynb` on disk while the server is up.** It is a live collaborative
   document; use the MCP tools (`use_notebook(mode="create")` for new files).
6. **API keys go in `<project>\.env`, loaded into the server process only.** Never
   system-wide: a global `ANTHROPIC_API_KEY` can make Claude Code bill that key.
7. **Verify through the real path.** After setup: health check OK, then `list_kernels`
   and `use_notebook` on a non-empty notebook reporting its real cell count.
8. **"0 cells" has three different causes; check the server log and the file size before
   touching the YStore.** A notebook over `WEBSOCKETS_MAX_BODY_SIZE` (16 MiB default; the
   template sets 64 MiB) is closed with 1009 and reads as empty. Invalid nbformat cell ids
   (over 64 chars, bad characters; common in downloaded notebooks) log "Notebook JSON is
   invalid" but do not empty the notebook; fix them with `scripts/fix_cell_ids.py` so
   validation and trust work. `jupyter_health.py --check-notebooks <dir>` finds both.

## Working loop (details in playbook.md)

`use_notebook` -> `read_notebook(brief)` -> `read_cell` (note the `cell_id`) ->
`edit_cell_source` by id -> `execute_cell` with a real `timeout` -> `read_cell` to confirm.
`execute_code` is scratch only; indexes shift after insert/delete/move, ids do not;
execution keeps running server-side after a timeout; `unuse_notebook` when done.

## Known-good versions (2026-10-23)

jupyter-mcp-server 2.2.4 via `uvx`; venv: jupyterlab 4.6.3, jupyter-collaboration 5.0.2,
pycrdt 0.14.4, pycrdt-store 0.1.5, ipykernel 7.3.0, Python 3.14, Windows 11. Upstream README
installs `jupyterlab jupyter-collaboration jupyter-mcp-tools ipykernel` unpinned; the old
`jupyterlab==4.4.1 jupyter-collaboration==4.0.2 datalayer_pycrdt` pins are obsolete.
`ystore_prefix.py` relies on `pycrdt.store.TempFileYStore(path, metadata_callback, log)` and
on jupyter-server-ydoc passing `config=`; re-check both after upgrading those packages.
