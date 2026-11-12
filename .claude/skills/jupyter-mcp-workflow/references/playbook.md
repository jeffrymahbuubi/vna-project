# Playbook: working on notebooks through jupyter-mcp-server

Tool semantics below are from the tool schemas that jupyter-mcp-server 2.2.4 advertises
(captured live 2026-10-23) and the upstream Tools reference. The server also offers
sandbox tools (`launch_sandbox`, `use_sandbox`, ...) and, in JupyterLab mode,
`notebook_run-all-cells` / `notebook_get-selected-cell`; they are not covered here.

## Rules

1. **Never write the `.ipynb` on disk while the server is up.** The notebook is a live
   collaborative (Yjs) document; a direct file write is silently discarded or silently
   overwrites unsaved edits. No `NotebookEdit`, no `nbformat`, no editors. Create new
   notebooks with `use_notebook(mode="create")`. If a disk write is unavoidable:
   `unuse_notebook`, close it in JupyterLab, write, then `use_notebook` again.
2. **Loop: `use_notebook` -> `read_notebook` (brief) -> `read_cell` -> edit -> execute ->
   `read_cell`.** Always read before editing; never edit from memory of an earlier read.
3. **Re-read after any insert/delete/move; indexes shift.** Better: take the `cell_id`
   from any result and address cells by id afterwards (`cell_id`, `cell_ids_to_delete`,
   `source_cell_id` / `target_cell_id`). Ids survive insertions above, indexes do not.
4. **`execute_code` is for scratch and inspection only.** Magics, `%pip install`, `df.head()`,
   `print(x)`, `!git status`, profiling. Never use it for imports or assignments the notebook
   depends on; that state is invisible in the notebook and lost on restart. Put it in a cell.
5. **Long cells: execution continues server-side after the tool times out.** The timeout
   only bounds the wait. Pass `timeout=<seconds>` (up to `JUPYTER_MCP_MAX_EXECUTION_TIMEOUT`,
   3600 by default) and keep `stream=true` so progress keepalives arrive; for training runs,
   poll afterwards with `read_cell(include_outputs=true)` or `execute_code("print(step)")`.
   Default when `timeout=0`: `JUPYTER_MCP_EXECUTION_TIMEOUT` (120 s).
6. **Prefer `edit_cell_source` over `overwrite_cell_source`.** Literal find/replace with a
   diff back; `old_string` must match exactly once unless `replace_all=true`.
7. **Images:** with `ALLOW_IMG_OUTPUT=true` plots come back as images; `false` gives text
   placeholders. Clear large outputs with `clear_cell_output` before re-reading a notebook
   with many plots.
8. **One active notebook.** `use_notebook` activates one; the others stay connected. Pass
   `notebook_name` on cell tools when several clients share the server, to avoid racing
   the shared "current notebook" pointer.
9. **`restart_notebook` loses all kernel state.** Ask before restarting a kernel someone
   else may be using; re-run setup cells afterwards.
10. **Be a good co-editor.** The user may have the same notebook open in JupyterLab and
    sees every edit live. Make small, explained edits; do not reorder or delete cells
    without saying so.

## Tool reference

Cell addressing: every cell tool takes `cell_index` (0-based) or `cell_id`; given both, the
id wins. Results report the id that was acted on.

| Tool | Does | Notes |
|---|---|---|
| `connect_to_jupyter(jupyter_url, jupyter_token?, document_provider="jupyter")` | Switch server at runtime | Validated against `/api/status` first; the previous connection stays if it fails. Not persisted; `.mcp.json` is the durable config. Unavailable when the MCP runs as a Jupyter extension |
| `list_files(path="", max_depth=1 (max 3), pattern="", limit=25, start_index=0)` | Recursive listing under the server root | The root is the launcher's cwd / `-ProjectRoot`. Nothing above it is visible |
| `list_kernels()` | Running kernels: id, name, state, connections | First MCP-level sanity check; fails on the IPv6/localhost problem while `list_files` works |
| `list_notebooks()` | Notebooks opened with `use_notebook` in this MCP session | Not the files on disk; use `list_files(pattern="*.ipynb")` for that |
| `use_notebook(notebook_name, notebook_path, mode="connect"\|"create", kernel_id?)` | Open (or create) and activate | `notebook_path` is relative to the server root. `notebook_name` is your own handle. Kernel: `kernel_id=<id>` binds an existing kernel; omitted, it reuses the notebook's live session (and says so) or attaches no kernel; `kernel_id="NEW"` starts an isolated kernel. Reply includes the cell count: a non-zero count on a non-empty notebook is the "0 cells" check |
| `unuse_notebook(notebook_name)` | Disconnect and release | Do it before any on-disk write and at the end of a task |
| `read_notebook(notebook_name, response_format="brief"\|"detailed", start_index=0, limit=20)` | Index, type, first line / full source, execution count | Brief with a big `limit` (0 = all) for the map, then `detailed` on a narrow range |
| `read_cell(cell_index\|cell_id, include_outputs=true, notebook_name?)` | One cell: metadata, source, formatted outputs | Use it to build an exact `old_string` for `edit_cell_source` and to poll a running cell |
| `insert_cell(cell_index, cell_type="code"\|"markdown"\|"raw", cell_source, notebook_name?)` | Insert at index (`-1` = append) | Shifts every index at and after it; re-read or use ids |
| `insert_execute_code_cell(cell_index, cell_source, timeout=0, stream=true, progress_interval=5)` | Insert a code cell and run it | Shortcut for insert + execute; `-1` appends |
| `edit_cell_source(cell_index\|cell_id, old_string, new_string, replace_all=false, notebook_name?)` | Literal find/replace in one cell, returns a diff | Multi-line ok; `old_string` must occur exactly once unless `replace_all` |
| `overwrite_cell_source(cell_source, cell_index\|cell_id, notebook_name?)` | Replace the whole source, returns a diff | For rewrites only |
| `delete_cell(cell_indices=[...] \| cell_ids_to_delete=[...], include_source=true, notebook_name?)` | Delete cells, return their source | Ids are validated before anything is deleted; indexes shift as earlier cells go, so prefer ids for multi-cell deletes |
| `move_cell(source_index\|source_cell_id, target_index\|target_cell_id, notebook_name?)` | Atomic move, keeps metadata/outputs | `[A,B,C,D]`, `move_cell(1,3)` -> `[A,C,D,B]` |
| `execute_cell(cell_index\|cell_id, timeout=0, stream=true, progress_interval=5)` | Run one cell, return outputs | Kernel keeps running past the timeout |
| `execute_code(code, kernel_id?, timeout=30, progress_interval=5)` | Run code in the kernel without saving it | Scratch only (rule 4). `kernel_id` targets any kernel, even one with no notebook |
| `clear_cell_output(cell_index\|cell_id, notebook_name?)` | Clear outputs and execution count of one code cell | |
| `restart_notebook(notebook_name)` | Restart that notebook's kernel | All variables lost |

## Patterns

**Orient**
```
list_files(pattern="*.ipynb", max_depth=3, limit=0)
use_notebook("nb", "Section-2/02_intro.ipynb")        -> "Notebook has N cells"
read_notebook("nb", response_format="brief", limit=0)
```

**Targeted fix**
```
read_cell(cell_index=12)                              -> note cell_id
edit_cell_source(cell_id=<id>, old_string="lr=1e-2", new_string="lr=1e-3")
execute_cell(cell_id=<id>, timeout=120)
read_cell(cell_id=<id>)                               -> confirm output
```

**Add a section at the end**
```
insert_cell(-1, "markdown", "## Evaluation")
insert_execute_code_cell(-1, "metrics = evaluate(model)\nmetrics", timeout=600)
```

**Training cell that outlives the timeout**
```
execute_cell(cell_index=20, timeout=1800, stream=true, progress_interval=30)
... later ...
execute_code("print(epoch, loss)")        # inspection only
read_cell(cell_index=20, include_outputs=true)
```

**Scaffold a new notebook**
```
use_notebook("new", "notes/experiment.ipynb", mode="create", kernel_id="NEW")
insert_cell(0, "markdown", "# Experiment")
insert_execute_code_cell(-1, "import numpy as np")
```

**Hand-off**
```
unuse_notebook("nb")        # release the room; the file is already saved by RTC
```

## Verification habits

- Before claiming "it runs": `read_cell` on every executed cell and check the output,
  not just the absence of an error from the tool.
- Before claiming "fixed": re-read the cell by id and show the diff the edit tool returned.
- When the notebook looks empty or shorter than expected: stop, run
  `scripts/jupyter_health.py`, and read [diagnose.md](diagnose.md) ("0 cells").
