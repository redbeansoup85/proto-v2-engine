#!/usr/bin/env bash
set -euo pipefail
rm -f test.db
export DATABASE_URL="sqlite+aiosqlite:///test.db"
pytest -q
