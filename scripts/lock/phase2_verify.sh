#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DB="$ROOT/infra/api/test.db"

echo "[1/4] Reset DB"
rm -f "$DB"
sqlite3 "$DB" "PRAGMA user_version;" >/dev/null

echo "[2/4] Export DATABASE_URL"
export DATABASE_URL="sqlite+aiosqlite:///$DB"

echo "[3/4] Alembic upgrade"
alembic -c infra/api/alembic.ini -q upgrade head

echo "[4/4] Phase-2 tests"
pytest -q tests/phase2/test_execution_adapter_fail_closed.py

echo "DONE: Phase-2 verify OK (DB=$DB)"
