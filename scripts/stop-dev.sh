#!/usr/bin/env bash
set -euo pipefail

PID_FILE="/tmp/rockburst-agent-lab.pids"

if [ ! -f "$PID_FILE" ]; then
  echo "No PID file found."
  exit 0
fi

while IFS=: read -r name pid; do
  if [ -n "${pid:-}" ] && kill -0 "$pid" >/dev/null 2>&1; then
    kill "-$pid" >/dev/null 2>&1 || kill "$pid" >/dev/null 2>&1 || true
    echo "Stopped $name ($pid)"
  fi
done < "$PID_FILE"

rm -f "$PID_FILE"
