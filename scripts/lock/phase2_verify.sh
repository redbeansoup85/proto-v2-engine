#!/usr/bin/env bash
set -euo pipefail

echo "[1/5] Reset DB"
DB="$(pwd)/infra/api/test.db"
rm -f "$DB"
sqlite3 "$DB" "PRAGMA user_version;" >/dev/null

echo "[2/5] Export DATABASE_URL (FAIL-CLOSED)"
export DATABASE_URL="sqlite+aiosqlite:///$DB"

echo "[3/5] Alembic upgrade"
alembic -c infra/api/alembic.ini -q upgrade head

echo "[4/5] Phase-2 Pytest"
pytest -q tests/phase2

echo "DONE: Phase-2 verify OK (DB=$DB)"
