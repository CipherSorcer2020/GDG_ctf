#!/usr/bin/env bash
# One-shot launcher (Linux/macOS): starts the CTF server, then exposes it with a
# free Cloudflare Tunnel (HTTPS, no router setup).
#
# The ADMIN TOKEN is printed below, in this terminal only.
# Every launch WIPES scores + lobby (old scores are saved as a backup).
#
# Options:  PORT=8001  EVENT=my-event  KEEP_STATE=1 (no wipe)  HOST=0.0.0.0 (LAN play)
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"
KEEP=""; [ -n "${KEEP_STATE:-}" ] && KEEP="--keep"
if [ -z "${EVENT:-}" ]; then
    if [ -f "$ROOT/event.json" ]; then EVENT="$ROOT"; else EVENT="$ROOT/demo"; fi
fi
[ -f "$EVENT/event.json" ] || { echo "[!] No event.json in $EVENT (create one: ctf init my-event)"; exit 1; }

if [ -x "$ROOT/.venv/bin/python" ]; then PY="$ROOT/.venv/bin/python"; else PY="python3"; fi
export PYTHONPATH="$ROOT${PYTHONPATH:+:$PYTHONPATH}"

if (echo > "/dev/tcp/127.0.0.1/$PORT") 2>/dev/null; then
    echo "[!] Port $PORT is already in use - an old server is probably still running."
    echo "    Stop it, or use another port:  PORT=8001 ./run.sh"
    exit 1
fi

cd "$EVENT"
echo "Starting CTF server on port $PORT (event: $EVENT)..."
$PY -m ctf_runner serve --host "$HOST" --port "$PORT" $KEEP &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null || true' EXIT
sleep 3

if command -v cloudflared >/dev/null 2>&1; then
    echo "Exposing via Cloudflare Tunnel - send players the https://....trycloudflare.com link:"
    cloudflared tunnel --url "http://localhost:$PORT"
else
    echo "NOTE: cloudflared not installed - the server is local only: http://localhost:$PORT"
    echo "Install: https://developers.cloudflare.com/cloudflare-one/connections/connect-apps/install-and-setup/installation"
    wait $SERVER_PID
fi
