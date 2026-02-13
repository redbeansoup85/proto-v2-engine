import json
import os
import sys
import subprocess
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
SNAP = ROOT / "var/local_llm/snapshot.json"
DRY  = ROOT / "var/local_llm/dry_run_validated.json"
GATE = ROOT / "var/local_llm/gate_decision.json"

def run(cmd, env=None):
    p = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
    if p.returncode != 0:
        raise SystemExit(p.stdout)
    return p.stdout

def main():
    if not SNAP.exists():
        raise SystemExit(f"missing {SNAP}")

    run_id = os.getenv("RUN_ID")
    if not run_id:
        run_id = f"run-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    # 1) DRY_RUN regenerate from snapshot
    out1 = run([sys.executable, "tools/local_llm/dry_run_loop.py", str(SNAP)])
    # 2) Gate decision regenerate
    run([sys.executable, "tools/local_llm/make_normalized_input.py"])
    out2 = run([sys.executable, "sdk/gate_cli.py", "--input", "var/local_llm/normalized_input.json", "--policy", "policies/sentinel/gate_v1.yaml", "--out", "var/local_llm/gate_decision.json"])

    # 3) Append to audit (sentinel-only file strongly recommended)
    env = dict(os.environ)
    env["RUN_ID"] = run_id
    out3 = run([sys.executable, "tools/local_llm/append_sentinel_to_audit.py"], env=env)

    d = json.loads(DRY.read_text(encoding="utf-8"))
    g = json.loads(GATE.read_text(encoding="utf-8"))

    print(out1.strip())
    print(out2.strip())
    print(out3.strip())

    print("REPLAY_RESULT:")
    print(json.dumps({"run_id": run_id, "dry_run": d, "gate": g}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
