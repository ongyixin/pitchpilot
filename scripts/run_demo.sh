#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────────────────
# PitchPilot — one-command hackathon demo launcher
#
# Usage:
#   bash scripts/run_demo.sh          # normal demo (1.5s stage delay)
#   bash scripts/run_demo.sh --fast   # instant results (no stage animation)
#   bash scripts/run_demo.sh --stop   # kill running servers
#
# What it does:
#   1. Starts the demo backend (uvicorn backend.demo_server:app --port 8000)
#   2. Starts the frontend dev server (vite --port 5173)
#   3. Opens http://localhost:5173 in your browser
#   4. Prints the demo URL and session ID
# ─────────────────────────────────────────────────────────────────────────────

set -euo pipefail

BACKEND_PORT=8000
FRONTEND_PORT=5173
BACKEND_LOG="/tmp/pitchpilot_backend.log"
FRONTEND_LOG="/tmp/pitchpilot_frontend.log"
PID_FILE="/tmp/pitchpilot_pids"

FAST=false
STOP=false

for arg in "$@"; do
  case $arg in
    --fast) FAST=true ;;
    --stop) STOP=true ;;
  esac
done

# ─── Stop mode ────────────────────────────────────────────────────────────────
if $STOP; then
  echo "Stopping PitchPilot servers..."
  if [ -f "$PID_FILE" ]; then
    while read -r pid; do
      kill "$pid" 2>/dev/null && echo "  Killed PID $pid" || true
    done < "$PID_FILE"
    rm -f "$PID_FILE"
  fi
  # Also try port-based kill as fallback
  lsof -ti :$BACKEND_PORT  | xargs kill -9 2>/dev/null || true
  lsof -ti :$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
  echo "Done."
  exit 0
fi

# ─── Setup checks ─────────────────────────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

echo ""
echo "  ╔═══════════════════════════════════════╗"
echo "  ║        PitchPilot Demo Server         ║"
echo "  ╚═══════════════════════════════════════╝"
echo ""

# Check Python
if ! command -v python3 &>/dev/null; then
  echo "ERROR: python3 not found." >&2
  exit 1
fi

# Check uvicorn
if ! python3 -c "import uvicorn" 2>/dev/null; then
  echo "ERROR: uvicorn not installed. Run: pip install -r requirements.txt" >&2
  exit 1
fi

# Check node/npm
if ! command -v npm &>/dev/null; then
  echo "ERROR: npm not found. Install Node.js >= 18." >&2
  exit 1
fi

# ─── Kill any existing servers on these ports ──────────────────────────────────
lsof -ti :$BACKEND_PORT  | xargs kill -9 2>/dev/null || true
lsof -ti :$FRONTEND_PORT | xargs kill -9 2>/dev/null || true
sleep 0.5

# ─── Start backend ─────────────────────────────────────────────────────────────
echo "→ Starting demo backend on :$BACKEND_PORT ..."

if $FAST; then
  export PITCHPILOT_DEMO_DELAY=0
else
  export PITCHPILOT_DEMO_DELAY=1.5
fi

cd "$PROJECT_ROOT"

python3 -m uvicorn backend.demo_server:app \
  --host 0.0.0.0 \
  --port $BACKEND_PORT \
  --log-level warning \
  > "$BACKEND_LOG" 2>&1 &
BACKEND_PID=$!
echo "  Backend PID: $BACKEND_PID  (log: $BACKEND_LOG)"

# Wait for backend to become ready
echo -n "  Waiting for backend"
for i in $(seq 1 20); do
  sleep 0.5
  if curl -sf "http://localhost:$BACKEND_PORT/health" >/dev/null 2>&1; then
    echo " ✓"
    break
  fi
  echo -n "."
  if [ $i -eq 20 ]; then
    echo ""
    echo "ERROR: Backend did not start. Check $BACKEND_LOG" >&2
    cat "$BACKEND_LOG" >&2
    exit 1
  fi
done

# ─── Start frontend ────────────────────────────────────────────────────────────
echo "→ Starting frontend dev server on :$FRONTEND_PORT ..."

cd "$PROJECT_ROOT/frontend"

# Install deps if node_modules missing
if [ ! -d "node_modules" ]; then
  echo "  Installing npm dependencies..."
  npm install --silent
fi

npm run dev -- --port $FRONTEND_PORT --host > "$FRONTEND_LOG" 2>&1 &
FRONTEND_PID=$!
echo "  Frontend PID: $FRONTEND_PID  (log: $FRONTEND_LOG)"

# Wait for frontend
echo -n "  Waiting for frontend"
for i in $(seq 1 30); do
  sleep 0.5
  if curl -sf "http://localhost:$FRONTEND_PORT" >/dev/null 2>&1; then
    echo " ✓"
    break
  fi
  echo -n "."
  if [ $i -eq 30 ]; then
    echo ""
    echo "ERROR: Frontend did not start. Check $FRONTEND_LOG" >&2
    cat "$FRONTEND_LOG" >&2
    exit 1
  fi
done

# Save PIDs for stop command
echo -e "$BACKEND_PID\n$FRONTEND_PID" > "$PID_FILE"

# ─── Open browser ─────────────────────────────────────────────────────────────
DEMO_URL="http://localhost:$FRONTEND_PORT"
echo ""
echo "  ✓ PitchPilot is running!"
echo ""
echo "  Frontend  →  $DEMO_URL"
echo "  Backend   →  http://localhost:$BACKEND_PORT"
echo "  API docs  →  http://localhost:$BACKEND_PORT/docs"
echo ""
echo "  Demo hint: Click 'Load Demo Session' to skip video upload."
if $FAST; then
  echo "  Mode: FAST (instant results, no animation)"
else
  echo "  Mode: NORMAL (1.5s stage delays for realistic demo)"
fi
echo ""
echo "  To stop: bash scripts/run_demo.sh --stop"
echo ""

# Open browser (macOS / Linux)
if command -v open &>/dev/null; then
  open "$DEMO_URL"
elif command -v xdg-open &>/dev/null; then
  xdg-open "$DEMO_URL"
fi

# Seed a demo session in background and print the ID
cd "$PROJECT_ROOT"
sleep 1
python3 scripts/seed_demo.py --base-url "http://localhost:$BACKEND_PORT" --quiet \
  && echo "  Demo session ready. Refresh the browser if needed." || true

# Keep script running so servers stay alive when called from terminal
echo "  Press Ctrl+C to stop all servers."
wait
