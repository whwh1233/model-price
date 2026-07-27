#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NODE_BIN="/Users/wh/.nvm/versions/node/v22.22.2/bin"

cd "$ROOT_DIR/backend"
uv sync
uv run playwright install chromium
uv run python -m scripts.refresh_snapshot

cd "$ROOT_DIR/frontend"
PATH="$NODE_BIN:$PATH" npm install
PATH="$NODE_BIN:$PATH" npm run build:fallback
