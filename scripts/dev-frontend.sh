#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR/frontend"

export PATH="$HOME/.local/node/bin:$PATH"

if ! command -v node >/dev/null 2>&1; then
  echo "Node is not available. Install Node in WSL or place it at $HOME/.local/node/bin." >&2
  exit 1
fi

if [ ! -d "node_modules" ]; then
  npm install
fi

npm run dev
