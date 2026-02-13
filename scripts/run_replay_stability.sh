#!/usr/bin/env bash
set -euo pipefail

MODE="${1:-}"
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PY="$ROOT/.venv/bin/python"
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
    --out "$out_json"
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
  local A_in="${A_IN:-/tmp/norm_A.json}"
  local B_in="${B_IN:-/tmp/norm_B.json}"
  local A_out="${A_OUT:-/tmp/gate_A.json}"
  local B_out="${B_OUT:-/tmp/gate_B.json}"

  require_file "$policy"
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
  local S_out1="${S_OUT1:-/tmp/gate_same_1.json}"
  local S_out2="${S_OUT2:-/tmp/gate_same_2.json}"

  require_file "$S_in"

  gate_once "$S_in" "$policy" "$S_out1"
  gate_once "$S_in" "$policy" "$S_out2"

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

  echo "[CI] OK: strict policy stability locked"
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
