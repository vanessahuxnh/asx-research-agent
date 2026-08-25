#!/bin/bash
# ASX Research Agent — one-step launcher.
#
# Double-click this file in Finder (or run ./start.command in a terminal).
# It checks the environment, starts the server, and opens the browser.
# Closing this window (or pressing Ctrl-C) stops the server.

cd "$(dirname "$0")" || exit 1

PORT="${ASX_PORT:-5001}"
URL="http://localhost:$PORT"
PY=".venv/bin/python"

echo ""
echo "  ASX Research Agent"
echo "  ─────────────────────────────────────────"

# ── Already running? Just open it. ───────────────────────────────────────────
if lsof -nP -iTCP:"$PORT" -sTCP:LISTEN >/dev/null 2>&1; then
    echo "  Server is already running on port $PORT."
    echo "  Opening $URL"
    open "$URL"
    echo ""
    read -r -p "  Press Return to close this window. "
    exit 0
fi

# ── Virtual environment ──────────────────────────────────────────────────────
if [ ! -x "$PY" ]; then
    echo "  Creating virtual environment..."
    python3 -m venv .venv || { echo "  ✗ Could not create .venv — is python3 installed?"; read -r; exit 1; }
fi

# ── Dependencies (only installs when something is actually missing) ──────────
if ! "$PY" -c "import flask, flask_cors, anthropic, yfinance, pandas, reportlab, bs4, dotenv" >/dev/null 2>&1; then
    echo "  Installing dependencies (first run only, may take a minute)..."
    "$PY" -m pip install -q --upgrade pip
    "$PY" -m pip install -q -r requirements.txt || { echo "  ✗ Dependency install failed."; read -r; exit 1; }
fi

# ── API key ──────────────────────────────────────────────────────────────────
if [ ! -f .env ] && [ -z "$ANTHROPIC_API_KEY" ]; then
    echo "  ✗ No .env file and no ANTHROPIC_API_KEY set."
    echo "    Create a .env file containing:  ANTHROPIC_API_KEY=sk-ant-..."
    read -r -p "  Press Return to close. "
    exit 1
fi

# ── Start the server ─────────────────────────────────────────────────────────
echo "  Starting server..."
"$PY" server.py &
SERVER_PID=$!
trap 'kill $SERVER_PID 2>/dev/null; wait $SERVER_PID 2>/dev/null' EXIT INT TERM HUP

# Wait for it to accept connections (up to ~15s)
for _ in $(seq 1 60); do
    if curl -fsS -o /dev/null "$URL/" 2>/dev/null; then
        READY=1
        break
    fi
    kill -0 $SERVER_PID 2>/dev/null || break   # server died during startup
    sleep 0.25
done

if [ -z "$READY" ]; then
    echo ""
    echo "  ✗ Server failed to start — see the errors above."
    read -r -p "  Press Return to close. "
    exit 1
fi

echo "  Ready. Opening $URL"
open "$URL"
echo ""
echo "  Leave this window open while you use the agent."
echo "  Press Ctrl-C (or close the window) to stop."
echo ""

wait $SERVER_PID
