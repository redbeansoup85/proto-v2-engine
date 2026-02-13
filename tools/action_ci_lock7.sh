#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi
export PYTHONPATH="$ROOT"

# Shared TMP_BASE (must match scripts/run_replay_stability.sh behavior)
TMP_BASE="${TMP_BASE:-}"
if [[ -z "${TMP_BASE}" ]]; then
  if [[ -n "${GITHUB_RUN_ID:-}" ]]; then
    TMP_BASE="/tmp/metaos_ci_${GITHUB_RUN_ID}"
  else
    TMP_BASE="$(mktemp -d "/tmp/metaos_ci_local.XXXXXX")"
  fi
fi
mkdir -p "$TMP_BASE"
export TMP_BASE

# Determinism switches
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1
export METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1
export METAOS_CI_DETERMINISTIC_ORCH_DECISION=1

# Reuse LOCK6 to produce deterministic inbox payload
bash "$ROOT/tools/action_ci_lock6.sh" >/dev/null

INBOX="$("$PY" - <<PY
import glob, os, sys
tmp_base=os.environ.get("TMP_BASE","")
if not tmp_base:
    raise SystemExit("FAIL-CLOSED: TMP_BASE env missing")

pattern=os.path.join(tmp_base,"orch_inbox_ci","*","*.json")
paths=sorted(glob.glob(pattern))
if not paths:
    raise SystemExit(f"FAIL-CLOSED: no orch inbox json found: {pattern}")
print(paths[0])
PY
)"

cp "$INBOX" /tmp/inbox_1.json
cp "$INBOX" /tmp/inbox_2.json

DEC1="$($PY - <<PY
from core.orchestrator.write_decision import write_orch_decision
print(write_orch_decision("/tmp/inbox_1.json", out_base_dir=f"{__import__('os').environ['TMP_BASE']}/orch_decisions_ci"))
PY
)"

DEC2="$($PY - <<PY
from core.orchestrator.write_decision import write_orch_decision
print(write_orch_decision("/tmp/inbox_2.json", out_base_dir=f"{__import__('os').environ['TMP_BASE']}/orch_decisions_ci"))
PY
)"

$PY - <<PY
import hashlib, sys
def digest(p):
    return hashlib.sha256(open(p,"rb").read()).hexdigest()

d1="$DEC1"; d2="$DEC2"
h1=digest(d1); h2=digest(d2)
print("dec1 =", d1)
print("dec2 =", d2)
print("digest1 =", h1)
print("digest2 =", h2)
if h1!=h2:
    raise SystemExit("FAIL-CLOSED: orch decision artifact not deterministic")
print("OK: orch decision deterministic")
PY

export AURALIS_AUDIT_PATH="/tmp/audit_ci_lock7.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

$PY "$ROOT/tools/audit_append_orch_decision_chain.py" \
  --decision "$DEC1" --ts 0 --event-id "CI:ORCH_DECISION:SENTINEL:1" >/dev/null

$PY "$ROOT/tools/audit/verify_chain.py" \
  --schema "$ROOT/sdk/schemas/audit_event.v1.json" \
  --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK7 orch decision + audit verified"
