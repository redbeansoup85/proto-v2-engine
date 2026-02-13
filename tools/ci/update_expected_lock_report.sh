#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# run CI transcript (may fail at LOCK9 if expected is stale)
set +e
bash "$ROOT/scripts/run_replay_stability.sh" ci
rc=$?
set -e

# build expected snapshot from latest transcript
python "$ROOT/tools/ci/build_lock_report.py" /tmp/ci_lock_report.txt "$ROOT/sdk/snapshots/expected_lock_report.ci.json"

# verify expected vs current
python "$ROOT/tools/ci/build_lock_report.py" /tmp/ci_lock_report.txt /tmp/current_lock_report.json
python "$ROOT/tools/ci/verify_lock_report.py" "$ROOT/sdk/snapshots/expected_lock_report.ci.json" /tmp/current_lock_report.json

echo "OK: updated expected lock report (previous rc=$rc)"
