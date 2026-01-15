#!/usr/bin/env bash
set -euo pipefail

pytest -q tests/test_constitutional_guards.py
pytest -q tests/test_dpa_transitions.py

python - <<'PY'
import json
from pathlib import Path
from core.engine.run_engine import run_engine

p = Path("docs/demo/v0_3_childcare.json")
data = json.loads(p.read_text(encoding="utf-8"))

out = run_engine(data, strict=True)
print("[OK] run_engine(strict=True) demo passed")
print("org_id:", out.meta.org_id, "site_id:", out.meta.site_id, "channel:", out.meta.channel)
print("decision.mode:", out.decision.mode, "decision.severity:", out.decision.severity)
PY
