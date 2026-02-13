#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
export PYTHONPATH="$ROOT"

# Determinism switches (inherit prior locks)
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1
export METAOS_CI_DETERMINISTIC_ORCH_PAYLOAD=1
export METAOS_CI_DETERMINISTIC_ORCH_DECISION=1
export METAOS_CI_DETERMINISTIC_ORCH_OUTBOX=1

# Ensure LOCK7 produces a deterministic decision + audit
bash "$ROOT/tools/action_ci_lock7.sh" >/dev/null

DEC="$($PY - <<'PY'
import glob
paths=glob.glob("/tmp/orch_decisions_ci/*/*.json")
print(paths[0])
PY
)"

# Split outbox twice from copies
cp "$DEC" /tmp/dec_1.json
cp "$DEC" /tmp/dec_2.json

rm -f /tmp/outbox_list_1.txt /tmp/outbox_list_2.txt

$PY - <<'PY'
from core.orchestrator.outbox import split_outbox_from_decision
paths = split_outbox_from_decision("/tmp/dec_1.json", outbox_base_dir="/tmp/orch_outbox_ci_1")
open("/tmp/outbox_list_1.txt","w",encoding="utf-8").write("\n".join(paths)+("\n" if paths else ""))
PY

$PY - <<'PY'
from core.orchestrator.outbox import split_outbox_from_decision
paths = split_outbox_from_decision("/tmp/dec_2.json", outbox_base_dir="/tmp/orch_outbox_ci_2")
open("/tmp/outbox_list_2.txt","w",encoding="utf-8").write("\n".join(paths)+("\n" if paths else ""))
PY

# Determinism check: compare per-index digest
$PY - <<'PY'
import hashlib, sys
from pathlib import Path

def read_list(path: str):
    p=Path(path)
    if not p.exists():
        return []
    return [line.strip() for line in p.read_text(encoding="utf-8").splitlines() if line.strip()]

def digest(path: str) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()

outs1 = read_list("/tmp/outbox_list_1.txt")
outs2 = read_list("/tmp/outbox_list_2.txt")

print("outbox.count.1 =", len(outs1))
print("outbox.count.2 =", len(outs2))
if len(outs1) != len(outs2):
    raise SystemExit("FAIL-CLOSED: outbox item count differs")

for a,b in zip(outs1, outs2):
    ha, hb = digest(a), digest(b)
    print("item1 =", a)
    print("item2 =", b)
    print("digest1 =", ha)
    print("digest2 =", hb)
    if ha != hb:
        raise SystemExit("FAIL-CLOSED: outbox item not deterministic")

print("OK: outbox items deterministic")
PY

# AuditChain seal: append all outbox items deterministically then verify
export AURALIS_AUDIT_PATH="/tmp/audit_ci_lock8.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

i=0
while IFS= read -r p; do
  p="$(echo "$p" | tr -d '\r')"
  [ -z "$p" ] && continue
  i=$((i+1))
  $PY "$ROOT/tools/audit_append_orch_outbox_chain.py" \
    --outbox "$p" --ts 0 --event-id "CI:ORCH_OUTBOX_ITEM:SENTINEL:$i" >/dev/null
done < /tmp/outbox_list_1.txt

$PY "$ROOT/tools/audit/verify_chain.py" --schema "$ROOT/sdk/schemas/audit_event.v1.json" --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK8 orch outbox + audit verified"
