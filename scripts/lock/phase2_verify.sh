#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

DB="$ROOT/infra/api/test.db"

echo "[1/4] Reset DB"
rm -f "$DB"
sqlite3 "$DB" "PRAGMA user_version;" >/dev/null

echo "[2/4] Migrate"
export DATABASE_URL="sqlite+aiosqlite:///$DB"
alembic -c infra/api/alembic.ini -q upgrade head

echo "[3/4] Phase-2 tests"
pytest -q tests/phase2

echo "DONE: Phase-2 verify OK (DB=$DB)"
echo "TIP: If you want to run additional pytest commands, run: export DATABASE_URL=\"sqlite+aiosqlite:///$DB\""
