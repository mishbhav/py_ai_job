#!/usr/bin/env bash
set -e

echo "==> Installing backend dependencies"
cd backend
python -m pip install --upgrade pip
pip install -r requirements.txt
# Playwright needs its browser binaries downloaded separately
python -m playwright install --with-deps chromium || true
cd ..

echo "==> Installing frontend dependencies"
cd frontend
npm install
cd ..

echo "==> Done. Run 'bash scripts/dev.sh' to start both servers."
