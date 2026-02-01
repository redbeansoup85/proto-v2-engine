#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
cd "$ROOT"

echo "[1/2] Verify schema_registry hashes (fail-closed)"
python - <<'PY'
import json, hashlib, sys
from pathlib import Path
REG = Path("Judgment_Data/registry/schema_registry.jsonl")
if not REG.exists():
    print("[FAIL-CLOSED] missing schema_registry.jsonl", file=sys.stderr); raise SystemExit(1)
for i, line in enumerate(REG.read_text(encoding="utf-8").splitlines(), 1):
    if not line.strip():
        continue
    obj = json.loads(line)
    if obj.get("registry_kind") != "schema":
        continue
    sid = obj.get("schema_id")
    p = Path(obj.get("path",""))
    declared = obj.get("schema_hash","")
    if not sid or not p.exists() or not declared.startswith("sha256:"):
        print(f"[FAIL-CLOSED] bad registry line {i}: {obj}", file=sys.stderr); raise SystemExit(1)
    h = hashlib.sha256(p.read_bytes()).hexdigest()
    if "sha256:"+h != declared:
        print(f"[FAIL-CLOSED] schema_hash mismatch for {sid}", file=sys.stderr)
        print(f"  declared: {declared}", file=sys.stderr)
        print(f"  computed: sha256:{h}", file=sys.stderr)
        raise SystemExit(1)
print("OK: schema_registry hashes match")
PY

echo "[2/2] Run Phase-2 tests"
DB="$ROOT/infra/api/test.db"
rm -f "$DB"
sqlite3 "$DB" "PRAGMA user_version;" >/dev/null
export DATABASE_URL="sqlite+aiosqlite:///$DB"
alembic -c infra/api/alembic.ini -q upgrade head
pytest -q tests/phase2
echo "DONE: Phase-2.5 verify OK"
