#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi
export PYTHONPATH="$ROOT"

# TMP_BASE must be inherited from caller (run_replay_stability.sh)
: "${TMP_BASE:=/tmp/metaos_ci_local}"
mkdir -p "$TMP_BASE"

# Determinism switches
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1
export METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1
export METAOS_CI_DETERMINISTIC_ORCH_DECISION=1

# Reuse LOCK6 to produce deterministic inbox payload
bash "$ROOT/tools/action_ci_lock6.sh" >/dev/null

INBOX="$("$PY" - <<PY
import glob, sys
paths=sorted(glob.glob("$TMP_BASE/orch_inbox_ci/*/*.json"))
if not paths:
    sys.exit("FAIL-CLOSED: no orch inbox payload found under TMP_BASE")
print(paths[0])
PY
)"

# Route twice from copies (avoid any accidental mutation)
cp "$INBOX" "$TMP_BASE/inbox_1.json"
cp "$INBOX" "$TMP_BASE/inbox_2.json"

DEC_DIR="$TMP_BASE/orch_decisions_ci"

DEC1="$("$PY" - <<PY
from core.orchestrator.write_decision import write_orch_decision
print(write_orch_decision("$TMP_BASE/inbox_1.json", out_base_dir="$DEC_DIR"))
PY
)"
DEC2="$("$PY" - <<PY
from core.orchestrator.write_decision import write_orch_decision
print(write_orch_decision("$TMP_BASE/inbox_2.json", out_base_dir="$DEC_DIR"))
PY
)"

# Compare decision artifact digests
"$PY" - <<PY
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
export AURALIS_AUDIT_PATH="$TMP_BASE/audit_ci_lock7.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

"$PY" "$ROOT/tools/audit_append_orch_decision_chain.py" --decision "$DEC1" --ts 0 --event-id "CI:ORCH_DECISION:SENTINEL:1" >/dev/null
"$PY" "$ROOT/tools/audit/verify_chain.py" --schema "$ROOT/sdk/schemas/audit_event.v1.json" --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK7 orch decision + audit verified"
