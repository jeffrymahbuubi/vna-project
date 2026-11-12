#!/usr/bin/env python
"""Report and (with --apply) rewrite invalid nbformat cell ids. Stdlib only.

    python -I fix_cell_ids.py <file-or-dir>...                 # dry run, per-file report
    python -I fix_cell_ids.py <paths> --apply [--backup-dir D] [--map-out map.json]

Rule (nbformat v4.5 schema): ^[a-zA-Z0-9-_]+$, 1-64 chars. Mapping is deterministic:
bad characters -> '-'; if still over 64 chars -> first 55 chars + '-' + first 8 hex of
sha1(original id); then made unique within the notebook (suffix -2, -3, ...).
A missing id (nbformat >= 4.5 cell without "id") gets cell-<12 hex of sha1(index:source)>,
inserted as a new line right after the cell's "cell_type" line.

Only the id strings change: the file is edited textually ("id": "<old>" -> "id": "<new>"
in document order, missing ids inserted after the k-th "cell_type" line), then re-parsed
and compared with the original minus ids. Indent, key order, escapes, line endings and
the trailing newline are untouched.

Safety: --apply refuses to run while a Jupyter server listens on --port (default 8888)
unless --force, because writing an .ipynb that the server may hold as a live
collaborative document loses edits. Stop the server, or at least make sure the notebook
is not open anywhere, before --force.

Exit codes: 0 nothing invalid (or all fixed), 1 invalid ids found (dry run), 2 error.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import socket
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbcheck import ID_RE, MAX_ID_LEN, invalid_ids, iter_notebooks, load_notebook  # noqa: E402

BAD_CHARS = re.compile(r"[^a-zA-Z0-9\-_]")


def new_id_for(old: str, taken: set[str]) -> str:
    base = BAD_CHARS.sub("-", old) or "cell"
    if len(base) > MAX_ID_LEN:
        base = base[:55] + "-" + hashlib.sha1(old.encode("utf-8")).hexdigest()[:8]
    cand, n = base, 1
    while cand in taken:
        n += 1
        suffix = f"-{n}"
        cand = base[: MAX_ID_LEN - len(suffix)] + suffix
    assert ID_RE.match(cand), cand
    return cand


def plan(nb: dict) -> tuple[dict[int, tuple[str, str]], dict[int, str], list[tuple[int, str]]]:
    """Return ({index: (old, new)} replacements, {index: new} insertions, [(index, reason)] skipped)."""
    cells = nb.get("cells", [])
    taken = {c["id"] for c in cells if isinstance(c.get("id"), str) and ID_RE.match(c["id"])}
    mapping: dict[int, tuple[str, str]] = {}
    missing: dict[int, str] = {}
    skipped: list[tuple[int, str]] = []
    for idx, cid, reason in invalid_ids(nb):
        if cid is None:
            src = cells[idx].get("source", "")
            src = "".join(src) if isinstance(src, list) else str(src)
            seed = f"{idx}:{src}".encode("utf-8")
            new = new_id_for("cell-" + hashlib.sha1(seed).hexdigest()[:12], taken)
            taken.add(new)
            missing[idx] = new
            continue
        if not isinstance(cid, str):
            skipped.append((idx, reason))
            continue
        new = new_id_for(cid, taken)
        taken.add(new)
        mapping[idx] = (cid, new)
    return mapping, missing, skipped


CELL_TYPE_LINE = re.compile(r'^([ \t]*)"cell_type"[ \t]*:[ \t]*"(?:code|markdown|raw)"[ \t]*,?[ \t]*(\r?\n)', re.M)


def insert_missing(text: str, missing: dict[int, str]) -> str:
    """Insert "id" after the k-th "cell_type" line for every cell index k in `missing`."""
    if not missing:
        return text
    out, pos, k = [], 0, 0
    for m in CELL_TYPE_LINE.finditer(text):
        if k in missing:
            line, indent, eol = m.group(0), m.group(1), m.group(2)
            body = line.rstrip("\r\n").rstrip()
            if body.endswith(","):                                  # more keys follow: id gets a comma too
                new = line + f'{indent}"id": {json.dumps(missing[k])},{eol}'
            else:                                                   # "cell_type" was the last key
                new = body + "," + eol + f'{indent}"id": {json.dumps(missing[k])}{eol}'
            out.append(text[pos:m.start()])
            out.append(new)
            pos = m.end()
        k += 1
    out.append(text[pos:])
    return "".join(out)


def rewrite_text(text: str, mapping: dict[int, tuple[str, str]]) -> str:
    """Replace the k-th textual occurrence of "id": <old> with the k-th planned new id."""
    queues: dict[str, list[str]] = {}
    for idx in sorted(mapping):
        old, new = mapping[idx]
        queues.setdefault(old, []).append(new)
    for old, news in queues.items():
        pat = re.compile(r'("id"\s*:\s*)' + re.escape(json.dumps(old, ensure_ascii=False)))
        pat_ascii = re.compile(r'("id"\s*:\s*)' + re.escape(json.dumps(old, ensure_ascii=True)))
        it = iter(news)

        def repl(m: re.Match) -> str:
            try:
                return m.group(1) + json.dumps(next(it), ensure_ascii=False)
            except StopIteration:
                return m.group(0)

        text, n = pat.subn(repl, text)
        if n < len(news):
            text, _ = pat_ascii.subn(repl, text)
    return text


def strip_ids(nb: dict) -> dict:
    nb = json.loads(json.dumps(nb))
    for c in nb.get("cells", []):
        c.pop("id", None)
    return nb


def port_open(port: int) -> bool:
    s = socket.socket()
    s.settimeout(1)
    try:
        return s.connect_ex(("127.0.0.1", port)) == 0
    finally:
        s.close()


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("paths", nargs="+", help="notebook files and/or directories (recursive)")
    ap.add_argument("--apply", action="store_true", help="rewrite the files (default: dry run)")
    ap.add_argument("--force", action="store_true", help="apply even if a Jupyter server listens on --port")
    ap.add_argument("--port", type=int, default=8888)
    ap.add_argument("--backup-dir", help="copy originals here (relative paths preserved) before writing")
    ap.add_argument("--map-out", help="write {file: {old: new}} JSON here")
    ap.add_argument("--quiet", action="store_true", help="only print files with problems and the summary")
    a = ap.parse_args()

    if a.apply and not a.force and port_open(a.port):
        print(f"ERROR: a server listens on 127.0.0.1:{a.port}; writing .ipynb files while Jupyter holds them "
              "as live documents loses edits. Stop it, or pass --force if the notebooks are not open anywhere.",
              file=sys.stderr)
        return 2

    try:
        files = list(iter_notebooks(a.paths))
    except FileNotFoundError as e:
        print(f"ERROR: no such path: {e}", file=sys.stderr)
        return 2

    roots = [Path(p) for p in a.paths]
    total_bad = total_fixed = total_skipped = errors = 0
    changed_files = 0
    full_map: dict[str, dict[str, str]] = {}

    for f in files:
        try:
            data, nb = load_notebook(f)
        except (OSError, ValueError) as e:
            print(f"[ERROR] {f}: {e}")
            errors += 1
            continue
        mapping, missing, skipped = plan(nb)
        if not mapping and not missing and not skipped:
            if not a.quiet:
                print(f"[ok]   {f}")
            continue
        total_bad += len(mapping) + len(missing) + len(skipped)
        total_skipped += len(skipped)
        worst = max((len(o) for o, _ in mapping.values()), default=0)
        print(f"[{'FIX' if a.apply else 'BAD'}]  {f}: {len(mapping)} invalid id(s)"
              f"{f', longest {worst} chars' if worst else ''}"
              f"{f', {len(missing)} missing' if missing else ''}"
              f"{f', {len(skipped)} unfixable (non-string id)' if skipped else ''}")
        if not a.quiet:
            for idx in sorted(mapping)[:3]:
                old, new = mapping[idx]
                print(f"         cell {idx}: {old[:60]}{'...' if len(old) > 60 else ''} -> {new}")
            for idx in sorted(missing)[:3]:
                print(f"         cell {idx}: (no id) -> {missing[idx]}")
        if not mapping and not missing:
            continue
        file_map = {o: n for o, n in mapping.values()} | {f"<missing cell {i}>": n for i, n in missing.items()}
        if not a.apply:
            full_map[str(f)] = file_map
            continue

        text = data.decode("utf-8")
        new_text = insert_missing(rewrite_text(text, mapping), missing)
        try:
            new_nb = json.loads(new_text)
        except ValueError as e:
            print(f"[ERROR] {f}: rewritten text is not valid JSON ({e}); file left unchanged")
            errors += 1
            continue
        got = {i: c.get("id") for i, c in enumerate(new_nb.get("cells", []))}
        want_ok = (all(got.get(i) == new for i, (_, new) in mapping.items())
                   and all(got.get(i) == new for i, new in missing.items()))
        if not want_ok or strip_ids(new_nb) != strip_ids(nb):
            print(f"[ERROR] {f}: post-check failed (ids or other content differ from plan); file left unchanged")
            errors += 1
            continue
        if a.backup_dir:
            rel = next((f.relative_to(r) for r in roots if r.is_dir() and r in f.parents), Path(f.name))
            dest = Path(a.backup_dir) / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(f, dest)
        with open(f, "w", encoding="utf-8", newline="") as fh:   # newline="" keeps the file's own line endings
            fh.write(new_text)
        full_map[str(f)] = file_map
        total_fixed += len(mapping) + len(missing)
        changed_files += 1

    if a.map_out:
        with open(a.map_out, "w", encoding="utf-8") as fh:
            json.dump(full_map, fh, indent=1, ensure_ascii=False)
        print(f"map written to {a.map_out}")

    print(f"\n{len(files)} notebook(s) scanned, {total_bad} invalid/missing id(s)"
          f"{f', {total_skipped} unfixable' if total_skipped else ''}"
          + (f", {total_fixed} rewritten in {changed_files} file(s)" if a.apply else ", dry run (use --apply)")
          + (f", {errors} error(s)" if errors else ""))
    if errors:
        return 2
    if a.apply:
        return 1 if total_skipped else 0
    return 1 if total_bad else 0


if __name__ == "__main__":
    sys.exit(main())
