#!/usr/bin/env python
"""Health check for a JupyterLab server driven through jupyter-mcp-server.

Stdlib only. Run with:  python -I jupyter_health.py [options]

It probes the HTTP API the MCP server uses, prints one line per check and a
final verdict (OK / WARN / FAIL) with a concrete fix for every failure.
Exit code: 0 = OK, 1 = WARN, 2 = FAIL.

Checks (in order):
  1. URL/token source      .mcp.json env block, CLI flags, or environment
  2. Name resolution       what the URL host resolves to, in order
  3. Reachability          127.0.0.1 vs ::1 vs the literal host, with and without token
  4. Token                 403 without token is normal; 403 with token = mismatch
  5. Port owner            which process listens on the port (Windows: netstat + PowerShell)
  6. Kernels               /api/kernels
  7. Server root           /api/contents, "looks like a script folder" heuristic,
                           and comparison with --project when given
  8. Collaboration         /api/collaboration/* endpoint present (RTC extension loaded)
  9. YStore                launcher flag on the process, temp folders, legacy .jupyter_ystore.db
 10. Notebooks (--check-notebooks PATH, repeatable, no server needed)
                           (a) notebooks at/above the MCP client's websocket frame limit
                               (WEBSOCKETS_MAX_BODY_SIZE, 16 MiB default): these read as "0 cells"
                           (b) invalid nbformat cell ids: a schema-validity problem only (server logs
                               "Notebook JSON is invalid", not trusted); cells still read. Optional
                               fix: fix_cell_ids.py
"""

from __future__ import annotations

import argparse
import json
import os
import socket
import subprocess
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from nbcheck import DEFAULT_WS_MAX_BODY, invalid_ids, iter_notebooks, load_notebook  # noqa: E402

TIMEOUT = 4.0
YSTORE_PREFIX = "claude_jupyter_ystore_"
SCRIPT_FOLDER_MARKERS = {"ystore_prefix.py", "start-jupyter-server.ps1", "start-jupyter-server.sh"}


class Report:
    def __init__(self) -> None:
        self.level = 0  # 0 ok, 1 warn, 2 fail
        self.fixes: list[str] = []

    def ok(self, msg: str) -> None:
        print(f"[OK]   {msg}")

    def info(self, msg: str) -> None:
        print(f"[INFO] {msg}")

    def warn(self, msg: str, fix: str | None = None) -> None:
        print(f"[WARN] {msg}")
        self.level = max(self.level, 1)
        if fix:
            self.fixes.append(f"WARN: {fix}")

    def fail(self, msg: str, fix: str) -> None:
        print(f"[FAIL] {msg}")
        self.level = 2
        self.fixes.append(f"FAIL: {fix}")


def http_get(url: str, token: str | None) -> tuple[int | str, bytes]:
    """Return (status_code or error label, body)."""
    if token:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}token={urllib.parse.quote(token)}"
    req = urllib.request.Request(url, headers={"User-Agent": "jupyter-health/1"})
    try:
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return resp.status, resp.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read() if e.fp else b""
    except urllib.error.URLError as e:
        reason = e.reason
        if isinstance(reason, (ConnectionRefusedError, OSError)) and getattr(reason, "errno", None) in (
            10061, 111, 61,
        ):
            return "refused", b""
        if isinstance(reason, socket.timeout) or "timed out" in str(reason):
            return "timeout", b""
        return f"error: {reason}", b""
    except (socket.timeout, TimeoutError):
        return "timeout", b""
    except OSError as e:
        return f"error: {e}", b""


def load_mcp_json(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        data = json.load(f)
    servers = data.get("mcpServers", {})
    for name, cfg in servers.items():
        args = " ".join(cfg.get("args", []))
        if "jupyter-mcp-server" in name or "jupyter-mcp-server" in args or "jupyter-mcp-server" in cfg.get("command", ""):
            return cfg.get("env", {})
    raise SystemExit(f"No jupyter-mcp-server entry found in {path}")


def listener_pid(port: int) -> int | None:
    if os.name != "nt":
        return None
    try:
        out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True, timeout=10).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    for line in out.splitlines():
        parts = line.split()
        if len(parts) >= 5 and parts[0] == "TCP" and parts[3] == "LISTENING" and parts[1].endswith(f":{port}"):
            try:
                return int(parts[4])
            except ValueError:
                return None
    return None


def process_cmdline(pid: int) -> str:
    if os.name != "nt":
        return ""
    ps = (
        "(Get-CimInstance Win32_Process -Filter 'ProcessId=%d').CommandLine" % pid
    )
    try:
        return subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=15,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return ""


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--mcp-json", help="path to a .mcp.json; its jupyter-mcp-server env block supplies URL/token")
    ap.add_argument("--url", help="Jupyter URL (default: .mcp.json, then $JUPYTER_URL, then http://127.0.0.1:8888)")
    ap.add_argument("--token", help="Jupyter token (default: .mcp.json, then $JUPYTER_TOKEN)")
    ap.add_argument("--project", help="project folder the server root is expected to be")
    ap.add_argument("--expect-ystore", action="store_true",
                    help="fail (not warn) when the PrefixTempFileYStore launcher flag is missing")
    ap.add_argument("--check-notebooks", action="append", metavar="PATH",
                    help="notebook file or folder to scan for invalid cell ids and oversize files (repeatable)")
    a = ap.parse_args()
    r = Report()

    # 1. Source of URL/token
    env = load_mcp_json(a.mcp_json) if a.mcp_json else {}
    url = a.url or env.get("JUPYTER_URL") or os.environ.get("JUPYTER_URL") or "http://127.0.0.1:8888"
    token = a.token or env.get("JUPYTER_TOKEN") or os.environ.get("JUPYTER_TOKEN") or None
    src = "--url/--token" if a.url else (".mcp.json" if a.mcp_json else "environment/defaults")
    r.info(f"URL {url}  token {'set' if token else 'NOT SET'}  (from {src})")
    if a.mcp_json:
        if "REQUEST_TIMEOUT" not in env:
            r.warn(".mcp.json has no REQUEST_TIMEOUT; jupyter_nbmodel_client defaults to 10 s and a slow "
                   "room-open then silently returns an empty notebook ('0 cells')",
                   'add "REQUEST_TIMEOUT": "60" to the jupyter-mcp-server env block')
        if env.get("ALLOW_IMG_OUTPUT", "true").lower() not in ("true", "1", "yes", "on"):
            r.info("ALLOW_IMG_OUTPUT is off: image outputs come back as text placeholders")
    try:
        ws_limit = int(env.get("WEBSOCKETS_MAX_BODY_SIZE") or os.environ.get("WEBSOCKETS_MAX_BODY_SIZE") or DEFAULT_WS_MAX_BODY)
    except ValueError:
        ws_limit = DEFAULT_WS_MAX_BODY
    r.info(f"MCP websocket frame limit {ws_limit / 2**20:.0f} MiB (WEBSOCKETS_MAX_BODY_SIZE); "
           "a notebook bigger than this on disk is read as '0 cells'")
    if a.check_notebooks:
        check_notebooks(r, a.check_notebooks, ws_limit)

    u = urllib.parse.urlsplit(url)
    host, port = u.hostname or "127.0.0.1", u.port or (443 if u.scheme == "https" else 80)
    base = f"{u.scheme}://{{h}}:{port}"

    # 2. Name resolution
    try:
        addrs = [ai[4][0] for ai in socket.getaddrinfo(host, port, type=socket.SOCK_STREAM)]
    except socket.gaierror as e:
        r.fail(f"{host} does not resolve: {e}", "use http://127.0.0.1:<port> in JUPYTER_URL")
        addrs = []
    seen: list[str] = []
    for x in addrs:
        if x not in seen:
            seen.append(x)
    r.info(f"{host} resolves to {seen} (Python tries them in this order)")

    # 3. Reachability on every candidate address
    probes = {}
    for h in ["127.0.0.1", "[::1]"] + ([host] if host not in ("127.0.0.1", "::1") else []):
        no_tok, _ = http_get(base.format(h=h) + "/api/status", None)
        with_tok, body = http_get(base.format(h=h) + "/api/status", token)
        probes[h] = (no_tok, with_tok, body)
        r.info(f"  {h:<12} /api/status  no-token={no_tok}  with-token={with_tok}")
    v4 = probes["127.0.0.1"][1]
    v6 = probes["[::1]"][1]
    lit = probes.get(host, probes["127.0.0.1"])[1]

    if v4 == "refused" and v6 == "refused":
        r.fail(f"nothing listens on port {port} (127.0.0.1 and ::1 both refused)",
               f"start the server from the project folder: scripts/start-jupyter-server.ps1 -ProjectRoot <project> "
               f"(port {port}); if the server was started on another port, change JUPYTER_URL")
    elif v6 == "refused" and v4 in (200, 403):
        if host == "localhost" and seen and seen[0] == "::1":
            r.fail("JUPYTER_URL uses 'localhost', which resolves to ::1 first, but the server only listens on IPv4 "
                   "(--ip=0.0.0.0). Some clients fall back to 127.0.0.1 (curl, browsers), the MCP's kernel/websocket "
                   "client did not ([WinError 10061] on list_kernels while list_files worked)",
                   f"set JUPYTER_URL=http://127.0.0.1:{port} in .mcp.json, then restart the MCP server "
                   "(Claude Code: /mcp -> reconnect, or restart the session)")
        elif host == "localhost":
            r.warn("'localhost' currently resolves to IPv4 first, but ::1 is refused; the order can change "
                   "between Python versions and OS settings",
                   f"prefer JUPYTER_URL=http://127.0.0.1:{port} to make it deterministic")
        else:
            r.ok("IPv4 reachable; ::1 refused is expected with --ip=0.0.0.0 and JUPYTER_URL uses a literal IPv4 address")
    elif v4 in (200, 403):
        r.ok("server reachable on 127.0.0.1")
    else:
        r.fail(f"unexpected result on 127.0.0.1: {v4}", "check the server log; is it still starting?")

    # 4. Token
    working_host = "127.0.0.1" if v4 in (200, 403) else host
    base_ok = base.format(h=working_host)
    no_tok = probes.get(working_host, probes["127.0.0.1"])[0]
    with_tok = probes.get(working_host, probes["127.0.0.1"])[1]
    if no_tok == 403:
        r.info("403 without a token is normal (the server requires auth); it is not an error")
    elif no_tok == 200:
        r.warn("the server accepts requests WITHOUT a token (no auth)", "start it with --IdentityProvider.token=<token>")
    if with_tok == 200:
        r.ok("token accepted")
        try:
            st = json.loads(probes[working_host][2] or b"{}")
            r.info(f"server started {st.get('started')}  kernels={st.get('kernels')}  connections={st.get('connections')}")
        except json.JSONDecodeError:
            pass
    elif with_tok == 403:
        r.fail("token rejected (403 with token): JUPYTER_TOKEN in .mcp.json does not match the running server",
               "use the same token in the launcher ($env:JUPYTER_TOKEN / -Token) and in .mcp.json, then restart the MCP; "
               "or the port is owned by ANOTHER project's server (see 'port owner' below): stop it first, "
               "only one server can use the port")
    elif not token and no_tok == 403:
        r.fail("no token configured but the server requires one", "set JUPYTER_TOKEN in .mcp.json")

    # 5. Port owner
    pid = listener_pid(port)
    cmd = process_cmdline(pid) if pid else ""
    if pid:
        r.info(f"port {port} owned by PID {pid}")
        if cmd:
            r.info(f"  cmdline: {cmd[:300]}")
            if "IdentityProvider.token=" in cmd and token:
                running = cmd.split("IdentityProvider.token=", 1)[1].split()[0].strip('"\'')
                if running != token:
                    r.fail("the listening process was started with a DIFFERENT token than the one configured",
                           "stop that server (another project?) or fix JUPYTER_TOKEN in .mcp.json")
            if "collaborative=true" not in cmd and "collaborative=True" not in cmd:
                r.fail("the listening process was not started with --LabApp.collaborative=true",
                       "start it with scripts/start-jupyter-server.ps1 (RTC is required by jupyter-mcp-server)")
    elif os.name == "nt" and with_tok in (200, 403):
        r.info("could not determine the owning PID (netstat parse)")

    if with_tok != 200:
        return finish(r)

    # 6. Kernels
    code, body = http_get(f"{base_ok}/api/kernels", token)
    if code == 200:
        kernels = json.loads(body or b"[]")
        states = ", ".join(f"{k.get('name')}:{k.get('execution_state')}" for k in kernels) or "none"
        r.ok(f"/api/kernels -> {len(kernels)} kernel(s): {states}")
    else:
        r.fail(f"/api/kernels failed: {code}", "see reachability/token results above")

    # 7. Server root
    code, body = http_get(f"{base_ok}/api/contents?content=1", token)
    if code == 200:
        root = json.loads(body)
        names = [e["name"] for e in root.get("content", [])]
        dirs = [e["name"] for e in root.get("content", []) if e["type"] == "directory"]
        nbs = [e["name"] for e in root.get("content", []) if e["type"] == "notebook"]
        r.info(f"server root has {len(names)} entries: {names[:12]}{' ...' if len(names) > 12 else ''}")
        if SCRIPT_FOLDER_MARKERS & set(names):
            r.fail("server root looks like the launcher's script folder, not a project "
                   f"(contains {sorted(SCRIPT_FOLDER_MARKERS & set(names))}); the MCP can only see files under it",
                   "stop this server and relaunch from the project folder: "
                   "cd <project>; & <skill>/scripts/start-jupyter-server.ps1   or pass -ProjectRoot <project>")
        elif not nbs and not dirs:
            r.warn("server root contains no notebooks and no folders", "is this the right folder? check -ProjectRoot")
        if a.project:
            local = set(os.listdir(a.project))
            remote = set(names)
            if remote and not remote <= local:
                r.fail(f"server root does not match --project {a.project} (server shows {sorted(remote - local)[:5]} "
                       "which are not in the project)",
                       "relaunch with -ProjectRoot pointing at the project")
            elif remote:
                r.ok(f"server root entries all exist in {a.project}")
    else:
        r.fail(f"/api/contents failed: {code}", "see above")

    # 8. Collaboration extension
    code, _ = http_get(f"{base_ok}/api/collaboration/session/__health_probe__.ipynb", token)
    if code == 404:
        r.fail("/api/collaboration/* is missing: jupyter-collaboration (jupyter-server-ydoc) is not installed or "
               "the server was started without --LabApp.collaborative=true",
               "pip install jupyter-collaboration into the venv and relaunch with the launcher")
    else:
        r.ok(f"collaboration endpoint present (GET /api/collaboration/session -> {code})")

    # 9. YStore
    if cmd:
        if "ystore_class=ystore_prefix.PrefixTempFileYStore" in cmd:
            r.ok("launcher flag present: --YDocExtension.ystore_class=ystore_prefix.PrefixTempFileYStore")
        else:
            msg = ("server runs the default SQLiteYStore: .jupyter_ystore.db grows without bound and heavy notebooks "
                   "can open as '0 cells' (jupyter-collaboration #430)")
            fix = "relaunch with scripts/start-jupyter-server.ps1 (sets PYTHONPATH + the ystore_class flag)"
            r.fail(msg, fix) if a.expect_ystore else r.warn(msg, fix)
    tmp = tempfile.gettempdir()
    try:
        ydirs = [d for d in os.listdir(tmp) if d.startswith(YSTORE_PREFIX)]
    except OSError:
        ydirs = []
    r.info(f"{len(ydirs)} {YSTORE_PREFIX}* folder(s) in {tmp} "
           "(one appears when a notebook room opens; proves the subclass instantiated; launcher removes them on exit)")
    for folder in filter(None, [a.project, os.getcwd()]):
        db = os.path.join(folder, ".jupyter_ystore.db")
        if os.path.isfile(db):
            mb = os.path.getsize(db) / 1e6
            (r.warn if mb > 50 else r.info)(
                f"legacy SQLite ystore {db} is {mb:.0f} MB",
                "safe to delete while the server is stopped; it is only used by the default SQLiteYStore")
    return finish(r)


def check_notebooks(r: Report, paths: list[str], ws_limit: int) -> None:
    bad_files: list[tuple[str, int, int]] = []   # path, invalid count, longest id
    big_files: list[tuple[str, int]] = []
    n = 0
    try:
        for p in iter_notebooks(paths):
            n += 1
            size = os.path.getsize(p)
            if size >= ws_limit:
                big_files.append((str(p), size))
            try:
                _, nb = load_notebook(p)
            except (OSError, ValueError) as e:
                r.warn(f"{p}: cannot parse ({e})")
                continue
            inv = invalid_ids(nb)
            if inv:
                bad_files.append((str(p), len(inv), max((len(i or "") for _, i, _ in inv), default=0)))
    except FileNotFoundError as e:
        r.fail(f"--check-notebooks path not found: {e}", "pass an existing notebook file or folder")
        return
    r.info(f"scanned {n} notebook(s) under {paths}")
    if bad_files:
        total = sum(c for _, c, _ in bad_files)
        r.fail(f"{len(bad_files)} notebook(s) with {total} invalid cell id(s) (nbformat 4.5: ^[a-zA-Z0-9-_]+$, "
               f"1-64 chars; longest seen {max(m for _, _, m in bad_files)}). First: "
               + "; ".join(f"{p} ({c})" for p, c, _ in bad_files[:3]),
               "python -I scripts/fix_cell_ids.py <path> (dry run), then --apply with the server stopped; "
               "the server logs 'Notebook JSON is invalid ... is too long' and marks them not trusted, and a "
               "fresh download from the same source brings the ids back")
    else:
        r.ok("no invalid cell ids")
    if big_files:
        r.fail(f"{len(big_files)} notebook(s) at or above the {ws_limit / 2**20:.0f} MiB websocket limit; the MCP "
               "client closes the sync with 1009 'message too big' and reports 0 cells: "
               + "; ".join(f"{p} ({s / 2**20:.1f} MiB)" for p, s in big_files[:3]),
               'set "WEBSOCKETS_MAX_BODY_SIZE": "67108864" (or larger) in the jupyter-mcp-server env block and '
               "reconnect the MCP, or clear the heavy outputs (e.g. embedded audio/images) from those notebooks")
    else:
        r.ok(f"no notebook at or above the {ws_limit / 2**20:.0f} MiB websocket limit")


def finish(r: Report) -> int:
    print()
    verdict = ["OK", "WARN", "FAIL"][r.level]
    print(f"VERDICT: {verdict}")
    for f in r.fixes:
        print(f"  - {f}")
    if r.level == 0:
        print("  MCP-level checks still to run from the client: list_kernels, use_notebook on a non-empty "
              "notebook must report a non-zero cell count.")
    return r.level


if __name__ == "__main__":
    sys.exit(main())
