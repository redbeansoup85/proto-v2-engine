#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="/.venv/bin/python"
if [[ ! -x "" ]]; then
  PY="20 20 12 61 79 80 81 701 33 98 100 204 250 395 398 399 400command -v python3 || command -v python)"
fi
export PYTHONPATH="$ROOT"

# deterministic (optional)
export METAOS_CI_DETERMINISTIC_PLAN=1
export METAOS_CI_DETERMINISTIC_CONSUMER=1
export METAOS_CI_DETERMINISTIC_ORCH_INBOX=1
export METAOS_CI_DETERMINISTIC_ORCH_DECISION=1
export METAOS_CI_DETERMINISTIC_ORCH_OUTBOX=1

export AURALIS_AUDIT_PATH="/tmp/audit_ci_lock9.jsonl"
rm -f "$AURALIS_AUDIT_PATH"

# 1) run lock8 to produce deterministic outbox item(s)
bash "$ROOT/tools/action_ci_lock8.sh" >/tmp/lock9_lock8_out.txt

# 2) parse outbox item path (item1 = ...)
OUTBOX_ITEM="$(python - <<'PY'
import re, pathlib
t = pathlib.Path("/tmp/lock9_lock8_out.txt").read_text(encoding="utf-8", errors="ignore")
m = re.search(r'^item1 = (.+)$', t, re.M)
print(m.group(1).strip() if m else "")
PY
)"

if [ -z "$OUTBOX_ITEM" ]; then
  echo "FAIL-CLOSED: could not parse outbox item path from action_ci_lock8 output"
  exit 1
fi

echo "OUTBOX_ITEM= $OUTBOX_ITEM"

# 3) append ALERT_EMITTED (fixed ts + fixed event-id for CI)
$PY "$ROOT/tools/audit_append_alert_emitted.py" \
  --outbox-item "$OUTBOX_ITEM" \
  --ts 0 \
  --event-id "CI:ALERT_EMITTED:SENTINEL:1" >/dev/null

# 4) verify chain
$PY "$ROOT/tools/audit/verify_chain.py" --schema "$ROOT/sdk/schemas/audit_event.v1.json" --chain "$AURALIS_AUDIT_PATH"

echo "OK: LOCK9 alert_emitted + audit verified"
