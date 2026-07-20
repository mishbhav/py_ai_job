#!/usr/bin/env bash
# Runs backend (port 8000) and frontend (port 5173) together.
# Ctrl+C stops both.
set -e

cleanup() {
  echo "Stopping servers..."
  kill "$BACKEND_PID" "$FRONTEND_PID" 2>/dev/null || true
}
trap cleanup EXIT

cd "$(dirname "$0")/.."

echo "==> Starting FastAPI backend on :8000"
(cd backend && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000) &
BACKEND_PID=$!

echo "==> Starting Vite frontend on :5173"
(cd frontend && npm run dev) &
FRONTEND_PID=$!

wait
