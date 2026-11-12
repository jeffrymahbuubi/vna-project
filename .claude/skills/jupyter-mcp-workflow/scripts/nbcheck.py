"""Shared notebook checks for jupyter_health.py and fix_cell_ids.py (stdlib only).

Cell id rule: nbformat v4.5 schema (definitions.cell_id in nbformat/v4/nbformat.v4.5.schema.json,
checked against nbformat 5.11.1): type string, pattern ^[a-zA-Z0-9-_]+$, minLength 1, maxLength 64.
Ids are required from nbformat 4.5 on; a 4.0-4.4 notebook legitimately has none.
"""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Iterator

ID_RE = re.compile(r"^[a-zA-Z0-9\-_]{1,64}$")
MAX_ID_LEN = 64
SKIP_DIRS = {".ipynb_checkpoints", ".venv", "node_modules", ".git", "__pycache__"}
# jupyter_nbmodel_client/client.py: WEBSOCKETS_MAX_BODY_SIZE = int(os.environ.get(..., 16*1024*1024)).
# The Y-doc SYNC_STEP2 frame is about the notebook's on-disk size; above the limit the
# client's websocket is closed with 1009 and the MCP reports "Notebook has 0 cells".
DEFAULT_WS_MAX_BODY = 16 * 1024 * 1024


def iter_notebooks(paths: list[str] | list[Path]) -> Iterator[Path]:
    """Yield every *.ipynb under the given files/dirs, skipping SKIP_DIRS, sorted."""
    for p in paths:
        p = Path(p)
        if p.is_file():
            if p.suffix == ".ipynb":
                yield p
            continue
        if not p.is_dir():
            raise FileNotFoundError(p)
        for root, dirs, files in os.walk(p):
            dirs[:] = sorted(d for d in dirs if d not in SKIP_DIRS)
            for f in sorted(files):
                if f.endswith(".ipynb"):
                    yield Path(root) / f


def needs_ids(nb: dict) -> bool:
    try:
        return int(nb.get("nbformat", 0)) == 4 and int(nb.get("nbformat_minor", 0)) >= 5
    except (TypeError, ValueError):
        return False


def invalid_ids(nb: dict) -> list[tuple[int, str | None, str]]:
    """Return (cell_index, id, reason) for every cell whose id violates the schema."""
    out = []
    required = needs_ids(nb)
    for i, cell in enumerate(nb.get("cells", [])):
        cid = cell.get("id")
        if cid is None:
            if required:
                out.append((i, None, "missing (required since nbformat 4.5)"))
            continue
        if not isinstance(cid, str):
            out.append((i, str(cid), "not a string"))
        elif len(cid) == 0:
            out.append((i, cid, "empty"))
        elif len(cid) > MAX_ID_LEN:
            out.append((i, cid, f"too long ({len(cid)} > {MAX_ID_LEN})"))
        elif not ID_RE.match(cid):
            out.append((i, cid, "bad characters (allowed: a-z A-Z 0-9 - _)"))
    return out


def load_notebook(path: Path) -> tuple[bytes, dict]:
    data = path.read_bytes()
    return data, json.loads(data.decode("utf-8"))
