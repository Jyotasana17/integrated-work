#!/usr/bin/env bash
###############################################################################
# Full-stack dev launcher for TrustLayer API Shield.
#
# Starts the FastAPI backend (SQLite + in-process worker pool + FakeRedis) on
# port 8000 AND the Next.js frontend on port 3000. The frontend proxies
# /api/v1/* to the backend (see frontend/next.config.ts), so the UI shows live
# real-time data with a single command and no external Redis/Postgres needed.
###############################################################################
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$ROOT"

export DATABASE_URL="${DATABASE_URL:-sqlite+aiosqlite:///./test.db}"
export PYTHONUNBUFFERED=1

PY="$(command -v python3 || command -v python)"

echo "[fullstack] Ensuring SQLite schema exists..."
"$PY" - <<'PYEOF'
import asyncio
from executor.persistence.database import engine, Base
import executor.persistence.models  # noqa: F401  (register models)
async def init():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
asyncio.run(init())
print("[fullstack] DB ready")
PYEOF

echo "[fullstack] Starting FastAPI backend on http://127.0.0.1:8000 ..."
"$PY" -m uvicorn executor.api.main:app --host 127.0.0.1 --port 8000 &
BACKEND_PID=$!

cleanup() {
  echo "[fullstack] Shutting down backend (pid $BACKEND_PID)..."
  kill "$BACKEND_PID" 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# Wait for backend health before starting the UI so first paint has data.
for i in $(seq 1 30); do
  if curl -sf http://127.0.0.1:8000/health >/dev/null 2>&1; then
    echo "[fullstack] Backend is healthy."
    break
  fi
  sleep 1
done

echo "[fullstack] Starting Next.js frontend on http://localhost:3000 ..."
cd "$ROOT/frontend"
exec npm run dev
