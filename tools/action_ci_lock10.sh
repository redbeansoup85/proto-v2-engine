#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi
# Run namespace isolation (CI-safe) — shared base across LOCK5/6/10
RUN_ID="${GITHUB_RUN_ID:-local}"
TMP_BASE="/tmp/metaos_ci_${RUN_ID}"
rm -rf "$TMP_BASE"
mkdir -p "$TMP_BASE"
export TMP_BASE

# Inputs from LOCK8 output locations (we generate them fresh inside this script)
export METAOS_CI_DETERMINISTIC_ORCH_OUTBOX=1
export METAOS_CI_DETERMINISTIC_CONSOLE_SENDER=1

# 1) Make sure we have a deterministic outbox item to send
OUTBOX1="$TMP_BASE/orch_outbox_ci_sender_1"
OUTBOX2="$TMP_BASE/orch_outbox_ci_sender_2"
export OUTBOX1 OUTBOX2
rm -rf "$OUTBOX1" "$OUTBOX2"
mkdir -p "$OUTBOX1" "$OUTBOX2"

# decision path produced by LOCK7 script (generate fresh)
export AURALIS_AUDIT_PATH="$TMP_BASE/audit_ci_lock10.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

# Generate a decision (LOCK7) deterministically
DEC_DIR="$TMP_BASE/orch_decisions_ci_lock10"
rm -rf "$DEC_DIR"
mkdir -p "$DEC_DIR"

# We assume an inbox exists from LOCK6; generate it fresh using LOCK6 helper
INBOX_BASE="$TMP_BASE/orch_inbox_ci_lock10"
rm -rf "$INBOX_BASE"
mkdir -p "$INBOX_BASE"

# Generate processed artifact via LOCK5 helper (should write under $TMP_BASE/queues_ci after patch)
bash "$ROOT/tools/action_ci_lock5.sh" >/dev/null

# Locate the processed file path from LOCK5 output directory (pick newest for robustness)
PROCESSED="$(ls -1t "$TMP_BASE/queues_ci/SENTINEL/processed"/dp_*.json | head -n 1)"
test -f "$PROCESSED"
echo "PROCESSED=$PROCESSED"

# Derive DP_ID from processed filename (SSOT for this script)
DP_ID="$(basename "$PROCESSED" .json)"
echo "DP_ID=$DP_ID"

# Build inbox payload deterministically (LOCK6 logic) using the same builder as LOCK6
INBOX_DIR="$INBOX_BASE/SENTINEL"
mkdir -p "$INBOX_DIR"

INBOX_JSON="$($PY - <<PY
from core.C_action.orch_payload import write_inbox_payload
print(write_inbox_payload("$PROCESSED", inbox_base_dir="$INBOX_BASE"))
PY
)"
echo "INBOX_JSON=$INBOX_JSON"
test -f "$INBOX_JSON" || { echo "ERROR: missing inbox json: $INBOX_JSON"; ls -la "$INBOX_DIR" || true; exit 10; }

# Build decision deterministically (LOCK7 logic)
DEC="$($PY - <<PY
import os
from core.orchestrator.write_decision import write_orch_decision

os.environ["METAOS_CI_DETERMINISTIC_ORCH_OUTBOX"] = "1"
print(write_orch_decision("${INBOX_JSON}"))
PY
)"
echo "DECISION_PATH= $DEC"
export DECISION_PATH="$DEC"
test -f "$DEC"

# Split outbox twice into separate dirs (capture actual output path)
ITEM1="$($PY - <<'PY'
import os
from core.orchestrator.outbox import split_outbox_from_decision
paths = split_outbox_from_decision(os.environ["DECISION_PATH"], outbox_base_dir=os.environ["OUTBOX1"])
print(paths[0])
PY
)"
echo "ITEM1=$ITEM1"

ITEM2="$($PY - <<'PY'
import os
from core.orchestrator.outbox import split_outbox_from_decision
paths = split_outbox_from_decision(os.environ["DECISION_PATH"], outbox_base_dir=os.environ["OUTBOX2"])
print(paths[0])
PY
)"
echo "ITEM2=$ITEM2"

test -f "$ITEM1"
test -f "$ITEM2"

# 2) Render console message twice and compare digests
digest () {
  $PY - <<PY
import hashlib, pathlib
p = pathlib.Path("$1")
b = p.read_bytes()
print(hashlib.sha256(b).hexdigest())
PY
}

MSG1="$TMP_BASE/console_msg_1.json"
MSG2="$TMP_BASE/console_msg_2.json"

$PY - <<PY > "$MSG1"
from core.orchestrator.senders.console_sender import send_to_stdout
send_to_stdout("${ITEM1}")
PY

$PY - <<PY > "$MSG2"
from core.orchestrator.senders.console_sender import send_to_stdout
send_to_stdout("${ITEM2}")
PY

d1="$(digest "$MSG1")"
d2="$(digest "$MSG2")"
echo "console.digest1 = $d1"
echo "console.digest2 = $d2"
if [[ "$d1" != "$d2" ]]; then
  echo "FAIL-CLOSED: console render not deterministic"
  exit 1
fi
echo "OK: console render deterministic"

# 3) Append audit event for console delivery and verify chain
# NOTE: use unquoted heredoc so $TMP_BASE expands into the JSON payload.
$PY - <<PY
from auralis_v1.core.audit_chain import append_audit

evt = {
  "schema": "audit_event.v1",
  "kind": "ORCH_DELIVERY_RENDERED",
  "event_id": "CI:ORCH:CONSOLE_RENDERED:1",
  "ts": 0,
  "payload": {
    "sender": "console",
    "msg_path": "${TMP_BASE}/console_msg_1.json",
  }
}
append_audit(evt)
PY

PYTHONPATH="$ROOT" $PY "$ROOT/tools/audit/verify_chain.py" \
  --schema "$ROOT/sdk/schemas/audit_event.v1.json" \
  --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK10 console sender + audit verified"
