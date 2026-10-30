#!/usr/bin/env bash
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

echo "=========================================================="
echo "  Shelf Check: In-Store AI Shelf Scanning Demo            "
echo "  Straive Innovation · Retail Operations Platform         "
echo "=========================================================="
echo ""

# Ensure data is generated
if [ ! -f "app/public/data/store.json" ]; then
    echo ">> Generating simulated store data..."
    ./.venv/bin/python3 pipeline/build_store.py
fi

if [ ! -d "app/public/data/scans" ] || [ -z "$(ls -A app/public/data/scans 2>/dev/null)" ]; then
    echo ">> Generating saved benchmark replies..."
    ./.venv/bin/python3 pipeline/run_replay_scans.py
fi

# Always include source and replay changes in the served app.
echo ">> Building web app bundle..."
(cd app && npm run build)

PORT="${PORT:-8000}"
HOST="${HOST:-127.0.0.1}"

echo ">> Starting Shelf Check local server at http://${HOST}:${PORT}"
echo ">> Saved benchmark replies available offline."
echo ">> Live mode uses your Straive LLM Foundry sign-in and paid model calls."
echo ">> Press Ctrl+C to stop."
echo ""

exec ./.venv/bin/uvicorn server.main:app --host "$HOST" --port "$PORT"
