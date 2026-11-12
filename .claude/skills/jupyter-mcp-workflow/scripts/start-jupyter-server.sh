#!/usr/bin/env bash
# POSIX/Git-Bash equivalent of start-jupyter-server.ps1. Same rules:
#   - run it from the project folder or pass --project <dir>; that folder is the server root
#   - venv: --venv <dir> / $JUPYTER_VENV, else <project>/.venv, else error
#   - token: --token / $JUPYTER_TOKEN / placeholder; must equal JUPYTER_TOKEN in .mcp.json
#   - <project>/.env is loaded into this process only (kernels inherit it); never export API keys globally
#   - PrefixTempFileYStore instead of the unbounded SQLiteYStore; its temp folders are removed on exit
# Tested on Git Bash (Windows); on Linux/macOS the venv layout is bin/ instead of Scripts/.
set -euo pipefail

PROJECT="$(pwd)"
VENV="${JUPYTER_VENV:-}"
TOKEN="${JUPYTER_TOKEN:-my_secure_token_123}"
PORT="${JUPYTER_PORT:-8888}"
DOTENV=""
while [ $# -gt 0 ]; do
  case "$1" in
    --project) PROJECT="$2"; shift 2 ;;
    --venv)    VENV="$2"; shift 2 ;;
    --token)   TOKEN="$2"; shift 2 ;;
    --port)    PORT="$2"; shift 2 ;;
    --dotenv)  DOTENV="$2"; shift 2 ;;
    *) echo "unknown option: $1" >&2; exit 2 ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$PROJECT" && pwd)"
case "$(basename "$PROJECT")" in
  script|scripts) [ -f "$PROJECT/ystore_prefix.py" ] && echo "WARNING: project root '$PROJECT' is a script folder; pass --project <project>" >&2 ;;
esac
cd "$PROJECT"
echo "Server root: $PROJECT"

activate=""
for cand in "$VENV" "$PROJECT/.venv"; do
  [ -n "$cand" ] || continue
  for a in "$cand/bin/activate" "$cand/Scripts/activate"; do
    if [ -f "$a" ]; then activate="$a"; break 2; fi
  done
done
if [ -z "$activate" ]; then
  echo "No virtual environment found. Tried: ${VENV:-<unset>} and $PROJECT/.venv. Pass --venv <dir> or set JUPYTER_VENV." >&2
  exit 1
fi
echo "Using venv: $(dirname "$(dirname "$activate")")"
# shellcheck disable=SC1090
source "$activate"
command -v jupyter >/dev/null || { echo "jupyter is not installed in that venv (see templates/requirements-jupyter.txt)" >&2; exit 1; }

# Port check: one server per port.
if python - "$PORT" <<'EOF'
import socket, sys
s = socket.socket(); s.settimeout(1)
sys.exit(0 if s.connect_ex(("127.0.0.1", int(sys.argv[1]))) == 0 else 1)
EOF
then
  echo "Port $PORT is already in use. Stop that server first or pass --port <other>." >&2
  exit 1
fi

export PYTHONPATH="$SCRIPT_DIR${PYTHONPATH:+:$PYTHONPATH}"

[ -n "$DOTENV" ] || DOTENV="$PROJECT/.env"
if [ -f "$DOTENV" ]; then
  while IFS= read -r line || [ -n "$line" ]; do
    if [[ "$line" =~ ^[[:space:]]*([A-Za-z_][A-Za-z0-9_]*)[[:space:]]*=[[:space:]]*(.*)$ ]]; then
      name="${BASH_REMATCH[1]}"; val="${BASH_REMATCH[2]}"
      val="${val%\"}"; val="${val#\"}"; val="${val%\'}"; val="${val#\'}"
      if [ -n "$val" ] && [ -z "${!name:-}" ]; then
        export "$name=$val"; echo "Loaded $name from .env"
      fi
    fi
  done < "$DOTENV"
fi

TMPROOT="$(python -c 'import tempfile; print(tempfile.gettempdir())')"
cleanup() {
  local n=0
  for d in "$TMPROOT"/claude_jupyter_ystore_*; do
    [ -d "$d" ] || continue
    rm -rf "$d" && n=$((n + 1))
  done
  [ "$n" -gt 0 ] && echo "Cleaned up $n YStore temp folder(s)."
  return 0
}
trap cleanup EXIT

echo "Starting JupyterLab on http://127.0.0.1:$PORT (token: $TOKEN)"
echo "Put JUPYTER_URL=http://127.0.0.1:$PORT in .mcp.json; 'localhost' may resolve to ::1, which this server does not bind."
jupyter lab --port "$PORT" \
  --IdentityProvider.token="$TOKEN" \
  --ServerApp.allow_origin='*' \
  --ServerApp.allow_remote_access=true \
  --ip=0.0.0.0 \
  --no-browser \
  --LabApp.collaborative=true \
  --YDocExtension.ystore_class=ystore_prefix.PrefixTempFileYStore
