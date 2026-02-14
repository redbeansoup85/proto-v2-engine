#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi
export PYTHONPATH="$ROOT"

# Run namespace isolation (CI-safe) — respect upstream TMP_BASE if provided
RUN_ID="${GITHUB_RUN_ID:-local}"
TMP_BASE="${TMP_BASE:-/tmp/metaos_ci_${RUN_ID}}"
mkdir -p "$TMP_BASE"
export TMP_BASE

# Determinism switches
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1
export METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1

# Reuse LOCK5 to produce a deterministic processed artifact (should write under $TMP_BASE/queues_ci after patch)
bash "$ROOT/tools/action_ci_lock5.sh" >/dev/null

# Find processed artifact (created by LOCK5 under $TMP_BASE/queues_ci) — pick newest by mtime
PROCESSED="$(ls -1t "${TMP_BASE}/queues_ci"/*/processed/*.json | head -n 1)"
test -f "$PROCESSED"
echo "PROCESSED=$PROCESSED"

# Create inbox payload twice from copies (avoid mutation differences)
cp "$PROCESSED" "$TMP_BASE/processed_1.json"
cp "$PROCESSED" "$TMP_BASE/processed_2.json"

INBOX1="$($PY - <<PY
from core.C_action.orch_payload import write_inbox_payload
print(write_inbox_payload("${TMP_BASE}/processed_1.json", inbox_base_dir="${TMP_BASE}/orch_inbox_ci"))
PY
)"
INBOX2="$($PY - <<PY
from core.C_action.orch_payload import write_inbox_payload
print(write_inbox_payload("${TMP_BASE}/processed_2.json", inbox_base_dir="${TMP_BASE}/orch_inbox_ci"))
PY
)"

# Compare inbox payload digests
$PY - <<PY
import hashlib
def digest(p):
    return hashlib.sha256(open(p,"rb").read()).hexdigest()
i1="${INBOX1}"; i2="${INBOX2}"
d1=digest(i1); d2=digest(i2)
print("inbox1 =", i1)
print("inbox2 =", i2)
print("digest1 =", d1)
print("digest2 =", d2)
if d1!=d2:
    raise SystemExit("FAIL-CLOSED: orch inbox payload not deterministic under METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1")
print("OK: orch inbox payload deterministic")
PY

# AuditChain seal + verify (keep inside TMP_BASE for parallel safety)
export AURALIS_AUDIT_PATH="$TMP_BASE/audit_ci_lock6.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

$PY tools/audit_append_orch_inbox_chain.py --inbox "$INBOX1" --ts 0 --event-id "CI:ORCH_INBOX_PAYLOAD:SENTINEL:1" >/dev/null
PYTHONPATH="$ROOT" $PY tools/audit/verify_chain.py --schema sdk/schemas/audit_event.v1.json --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK6 orch inbox + audit verified"
