#!/usr/bin/env bash
set -euo pipefail

# -----------------------------------------
# Deterministic TMP_BASE (fixes inbox_path drift across runs)
# - If METAOS_CI_DETERMINISTIC_CONSUMER=1 -> stable /tmp/metaos_ci_local.DETERMINISTIC
# - Else: CI uses /tmp/metaos_ci_${GITHUB_RUN_ID} (stable within a run)
# - Else: local uses mktemp (unique per run)
# -----------------------------------------
TMP_BASE="${TMP_BASE:-}"
if [[ -z "${TMP_BASE}" ]]; then
  if [[ "${METAOS_CI_DETERMINISTIC_CONSUMER:-}" =~ ^(1|true|yes|y|on)$ ]]; then
    TMP_BASE="/tmp/metaos_ci_local.DETERMINISTIC"
    rm -rf "$TMP_BASE"
    mkdir -p "$TMP_BASE"
  elif [[ -n "${GITHUB_RUN_ID:-}" ]]; then
    TMP_BASE="/tmp/metaos_ci_${GITHUB_RUN_ID}"
    mkdir -p "$TMP_BASE"
  else
    TMP_BASE="$(mktemp -d "/tmp/metaos_ci_local.XXXXXX")"
    mkdir -p "$TMP_BASE"
  fi
fi
export TMP_BASE

# --- TMP_BASE + NORM_A/B (must be defined before any mode function runs) ---
NORM_A="${TMP_BASE}/norm_A.json"
NORM_B="${TMP_BASE}/norm_B.json"
# -------------------------------------------------------------------------

MODE="${1:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# -----------------------------------------
# CI: capture full transcript deterministically (no hang)
# -----------------------------------------
if [[ "${MODE:-}" == "ci" ]]; then
  : "${CI_LOCK_REPORT_PATH:=/tmp/ci_lock_report.txt}"
  rm -f "$CI_LOCK_REPORT_PATH"
  # capture stdout+stderr; do NOT block waiting for stdin
  exec > >(tee -a "$CI_LOCK_REPORT_PATH") 2>&1
fi

PY="${PYTHON_BIN:-$ROOT/.venv/bin/python}"
# CI runners usually do not have repo-local .venv; fall back to system python
if [[ ! -x "$PY" ]]; then
  PY="$(command -v python3 || command -v python)"
fi
[[ -n "${PY:-}" ]] || { echo "ERROR: python not found" >&2; exit 1; }
export PYTHONPATH="$ROOT"

POLICY_DEFAULT="$ROOT/policies/sentinel/gate_v1.yaml"

die(){ echo "ERROR: $*" >&2; exit 1; }
require_file(){ [[ -f "$1" ]] || die "missing file: $1"; }

gate_once(){
  local in_json="$1"
  local policy="$2"
  local out_json="$3"
  "$PY" "$ROOT/sdk/gate_cli.py" \
    --input "$in_json" \
    --policy "$policy" \
    --out "$out_json" \
    --include-policy-capsule
}

has_key(){
  local json_path="$1"
  local key="$2"
  "$PY" - <<PY
import json
j=json.load(open("$json_path"))
print(str("$key" in j))
PY
}

digest_section(){
  local gate_json="$1"
  local key="$2"
  "$PY" "$ROOT/tools/capsule_digest.py" --in "$gate_json" --path "$key"
}

mode_ci(){
  local policy="${POLICY:-$POLICY_DEFAULT}"

  # Use TMP_BASE for all CI artifacts to avoid /tmp drift in embedded paths
  local A_in="${A_IN:-$NORM_A}"
  local B_in="${B_IN:-$NORM_B}"
  local A_out="${A_OUT:-$TMP_BASE/gate_A.json}"
  local B_out="${B_OUT:-$TMP_BASE/gate_B.json}"

  require_file "$policy"

  # source normalized input fixture (repo-local)
  local NORM_SRC="$ROOT/tests/fixtures/sentinel/normalized_input.ci.json"
  require_file "$NORM_SRC"

  # create A/B inputs if missing (deterministic: identical content)
  if [[ ! -f "$A_in" ]]; then
    cp "$NORM_SRC" "$A_in"
  fi
  if [[ ! -f "$B_in" ]]; then
    cp "$NORM_SRC" "$B_in"
  fi

  require_file "$A_in"
  require_file "$B_in"

  echo "[CI] policy: $policy"

  gate_once "$A_in" "$policy" "$A_out"
  gate_once "$B_in" "$policy" "$B_out"

  echo "[CI] policy_sha256 check"
  "$PY" - <<PY
import json, sys
A=json.load(open("$A_out"))
B=json.load(open("$B_out"))
a=A.get("policy_sha256")
b=B.get("policy_sha256")
print("A.policy_sha256 =", a)
print("B.policy_sha256 =", b)
if a!=b:
    sys.exit("policy_sha256 mismatch")
print("OK: policy_sha256 identical")
PY

  # Optional: if policy_capsule exists, digest it too.
  if [[ "$(has_key "$A_out" policy_capsule)" == "True" ]]; then
    echo "[CI] policy_capsule digest check"
    da="$(digest_section "$A_out" policy_capsule)"
    db="$(digest_section "$B_out" policy_capsule)"
    echo "A.policy_capsule.digest = $da"
    echo "B.policy_capsule.digest = $db"
    [[ "$da" == "$db" ]] || die "policy_capsule digest mismatch"
  else
    echo "[CI] policy_capsule missing; strict locked on policy_sha256 (expected)"
  fi

  echo "[CI] determinism check (same input twice)"

  local S_in="${S_IN:-$B_in}"
  local S_out1="${S_OUT1:-$TMP_BASE/gate_same_1.json}"
  local S_out2="${S_OUT2:-$TMP_BASE/gate_same_2.json}"

  require_file "$S_in"

  gate_once "$S_in" "$policy" "$S_out1"
  gate_once "$S_in" "$policy" "$S_out2"

  # --- legacy alias for LOCK9 parser (expects /tmp/gate_same_*.json paths in log) ---
  local LEG_S1="/tmp/gate_same_1.json"
  local LEG_S2="/tmp/gate_same_2.json"
  cp "$S_out1" "$LEG_S1"
  cp "$S_out2" "$LEG_S2"
  echo "OK: wrote $LEG_S1"
  echo "OK: wrote $LEG_S2"
  # -------------------------------------------------------------------------------

  "$PY" - <<EOF
import json, hashlib, sys
def digest(p):
    j=json.load(open(p))
    b=json.dumps(j, sort_keys=True, separators=(",",":"), ensure_ascii=False).encode()
    return hashlib.sha256(b).hexdigest()
a=digest("$S_out1")
b=digest("$S_out2")
print("same1.digest =", a)
print("same2.digest =", b)
if a!=b:
    sys.exit("gate decision not deterministic for identical input")
print("OK: deterministic")
EOF

  echo "[CI] audit chain verify (append_audit + verify_chain)"

  export AURALIS_AUDIT_PATH="$TMP_BASE/audit_ci_chain.jsonl"
  rm -f "$AURALIS_AUDIT_PATH"

  # Use gate_B output as payload source (already generated above)
  "$PY" -m sdk.gate_cli --input "$B_in" --policy "$policy" --out "$B_out" --include-policy-capsule >/dev/null

  "$PY" tools/audit_append_gate_chain.py \
    --gate "$B_out" \
    --ts 0 \
    --event-id "CI:GATE_DECISION:BTCUSDT:POLICY_V1" >/dev/null

  "$PY" tools/audit/verify_chain.py \
    --schema sdk/schemas/audit_event.v1.json \
    --chain "$AURALIS_AUDIT_PATH"

  echo "[CI] OK: audit chain verified"

  echo "[CI] LOCK4 plan+queue determinism"
  bash "$ROOT/tools/action_ci_lock4.sh"
  echo "[CI] OK: LOCK4 plan+queue deterministic"

  echo "[CI] LOCK5 consumer+audit determinism"
  bash "$ROOT/tools/action_ci_lock5.sh"
  echo "[CI] OK: LOCK5 consumer+audit verified"

  echo "[CI] LOCK6 orch inbox+audit determinism"
  bash "$ROOT/tools/action_ci_lock6.sh"
  echo "[CI] OK: LOCK6 orch inbox+audit verified"

  echo "[CI] LOCK7 orch decision+audit determinism"
  bash "$ROOT/tools/action_ci_lock7.sh"
  echo "[CI] OK: LOCK7 orch decision+audit verified"

  echo "[CI] LOCK8 orch outbox+audit determinism"
  bash "$ROOT/tools/action_ci_lock8.sh"
  echo "[CI] OK: LOCK8 orch outbox+audit verified"

  echo "[CI] LOCK9 expected snapshot verify"
  # Build current lock report from this CI log and compare with expected snapshot
  python "$ROOT/tools/ci/build_lock_report.py" "$CI_LOCK_REPORT_PATH" "$TMP_BASE/current_lock_report.json"
  python "$ROOT/tools/ci/verify_lock_report.py" "$ROOT/sdk/snapshots/expected_lock_report.ci.json" "$TMP_BASE/current_lock_report.json"
  echo "[CI] OK: LOCK9 expected snapshot matches"

  echo "[CI] OK: strict policy stability locked"

  echo "[CI] CI lock report"
  python "$ROOT/tools/ci/lock_report.py" "$CI_LOCK_REPORT_PATH"
}

mode_local(){
  echo "[LOCAL] running strict gate stability only"
  bash "$0" ci
  echo "[LOCAL] OK"
}

case "$MODE" in
  ci) mode_ci ;;
  local) mode_local ;;
  *) die "usage: $0 {ci|local}" ;;
esac
