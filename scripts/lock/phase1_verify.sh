#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
DB="$ROOT/infra/api/test.db"

cd "$ROOT"

echo "[1/7] Reset DB"
rm -f "$DB"
sqlite3 "$DB" "PRAGMA user_version;" >/dev/null

export DATABASE_URL="sqlite+aiosqlite:///$DB"

echo "[2/7] Compile alembic env.py"
python -m py_compile infra/api/alembic/env.py

echo "[3/7] Alembic upgrade"
alembic -c infra/api/alembic.ini -q upgrade head

echo "[4/7] Tables"
sqlite3 "$DB" ".tables"

echo "[5/7] Alembic version"
sqlite3 "$DB" "select version_num from alembic_version;"

echo "[6/7] Alembic current / heads"
alembic -c infra/api/alembic.ini current -v
alembic -c infra/api/alembic.ini heads

echo "[7/7] Pytest"
pytest -q

echo "DONE: Phase-1 LOCK verify OK (DB=$DB)"
