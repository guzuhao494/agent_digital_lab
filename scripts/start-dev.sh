#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="/tmp/rockburst-agent-lab.pids"
BACKEND_LOG="/tmp/rockburst-agent-lab-backend.log"
FRONTEND_LOG="/tmp/rockburst-agent-lab-frontend.log"

cd "$ROOT_DIR"
export PATH="$HOME/.local/node/bin:$PATH"

if [ ! -d ".venv" ]; then
  python3 -m venv .venv
fi

source .venv/bin/activate
pip install -r backend/requirements.txt >/dev/null

is_up() {
  curl --noproxy '*' --connect-timeout 1 --max-time 2 -fsS "$1" >/dev/null 2>&1
}

: > "$PID_FILE"

if ! is_up "http://127.0.0.1:5000/api/health"; then
  PYTHONPATH=backend nohup setsid python -c 'from app import create_app; create_app().run(host="127.0.0.1", port=5000, debug=False, use_reloader=False)' >"$BACKEND_LOG" 2>&1 </dev/null &
  echo "backend:$!" >> "$PID_FILE"
fi

if ! is_up "http://127.0.0.1:5173"; then
  (
    cd frontend
    nohup setsid npm run dev -- --host 0.0.0.0 >"$FRONTEND_LOG" 2>&1 </dev/null &
    echo "frontend:$!" >> "$PID_FILE"
  )
fi

for _ in $(seq 1 40); do
  is_up "http://127.0.0.1:5000/api/health" && break
  sleep 1
done

for _ in $(seq 1 40); do
  is_up "http://127.0.0.1:5173" && break
  sleep 1
done

is_up "http://127.0.0.1:5000/api/health"
is_up "http://127.0.0.1:5173"

echo "rockburst-agent-lab is running at http://localhost:5173"
echo "Backend log: $BACKEND_LOG"
echo "Frontend log: $FRONTEND_LOG"
