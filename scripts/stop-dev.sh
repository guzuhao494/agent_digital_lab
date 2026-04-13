#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/tmp/rockburst-agent-lab.pids"
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

stop_matching() {
  local name="$1"
  local pattern="$2"
  pgrep -f "$pattern" | while read -r pid; do
    if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "$pid" >/dev/null 2>&1 || true
      echo "Stopped stale $name ($pid)"
    fi
  done
}

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file found."
else
  while IFS=: read -r name pid; do
    if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
      kill "-$pid" >/dev/null 2>&1 || kill "$pid" >/dev/null 2>&1 || true
      echo "Stopped $name ($pid)"
    fi
  done < "$PID_FILE"

  rm -f "$PID_FILE"
fi

stop_matching "frontend" "$ROOT_DIR/frontend/node_modules/.bin/vite"
stop_matching "backend" "python -c from app import create_app"
