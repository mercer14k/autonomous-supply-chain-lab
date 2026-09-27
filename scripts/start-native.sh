#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")/.."
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[dev]'
(cd apps/web && pnpm install --frozen-lockfile)
.venv/bin/uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 &
LAB_API_PID=$!
trap 'kill "$LAB_API_PID" 2>/dev/null || true' EXIT INT TERM
cd apps/web
pnpm dev
