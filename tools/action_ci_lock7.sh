#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT"

# Determinism switches
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1
export METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1
export METAOS_CI_DETERMINISTIC_ORCH_DECISION=1

# Reuse LOCK6 to produce deterministic inbox payload
bash "$ROOT/tools/action_ci_lock6.sh" >/dev/null

INBOX="$(python - <<'PY'
import glob
paths=glob.glob("/tmp/orch_inbox_ci/*/*.json")
print(paths[0])
PY
)"

# Route twice from copies (avoid any accidental mutation)
cp "$INBOX" /tmp/inbox_1.json
cp "$INBOX" /tmp/inbox_2.json

DEC1="$($PY - <<PY
from core.orchestrator.write_decision import write_orch_decision
print(write_orch_decision("/tmp/inbox_1.json", out_base_dir="/tmp/orch_decisions_ci"))
PY
)"
DEC2="$($PY - <<PY
from core.orchestrator.write_decision import write_orch_decision
print(write_orch_decision("/tmp/inbox_2.json", out_base_dir="/tmp/orch_decisions_ci"))
PY
)"

# Compare decision artifact digests
$PY - <<PY
import hashlib
def digest(p):
    return hashlib.sha256(open(p,"rb").read()).hexdigest()
d1="$DEC1"; d2="$DEC2"
h1=digest(d1); h2=digest(d2)
print("dec1 =", d1)
print("dec2 =", d2)
print("digest1 =", h1)
print("digest2 =", h2)
if h1!=h2:
    raise SystemExit("FAIL-CLOSED: orch decision artifact not deterministic under METAOS_CI_DETERMINISTIC_ORCH_DECISION=1")
print("OK: orch decision deterministic")
PY

# AuditChain seal + verify
export AURALIS_AUDIT_PATH="/tmp/audit_ci_lock7.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

$PY tools/audit_append_orch_decision_chain.py --decision "$DEC1" --ts 0 --event-id "CI:ORCH_DECISION:SENTINEL:1" >/dev/null
$PY tools/audit/verify_chain.py --schema sdk/schemas/audit_event.v1.json --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK7 orch decision + audit verified"
