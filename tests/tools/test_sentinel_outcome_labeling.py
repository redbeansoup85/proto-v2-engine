import json
import subprocess
import sys
from pathlib import Path

GEN = Path("tools/local/llm_generate_intent.py")
GATE = Path("tools/gates/sentinel_trade_intent_schema_gate.py")
CONSUMER = Path("tools/sentinel/consume_trade_intent.py")
VERIFY = Path("tools/audits/verify_judgment_event_chain.py")
RECORD = Path("tools/sentinel/record_outcome.py")

def test_outcome_ref_and_record_outcome(tmp_path):
    audit_path = tmp_path / "chain.jsonl"
    snap_dir = tmp_path / "snaps"
    out_dir = tmp_path / "outs"
    out_dir.mkdir(parents=True, exist_ok=True)

    # generate intent (mock)
    p1 = subprocess.run([sys.executable, str(GEN), "--backend", "mock"], input="BTCUSDT 롱",
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p1.returncode == 0, p1.stderr

    # gate pass
    p2 = subprocess.run([sys.executable, str(GATE)], input=p1.stdout,
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p2.returncode == 0, p2.stderr

    # consume (override dirs)
    p3 = subprocess.run(
        [sys.executable, str(CONSUMER), "--audit-path", str(audit_path), "--snapshot-dir", str(snap_dir)],
        input=p2.stdout, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
    assert p3.returncode == 0, p3.stderr

    # chain verify
    ok = subprocess.run([sys.executable, str(VERIFY), "--path", str(audit_path)],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert ok.returncode == 0, ok.stderr

    # parse event
    evt = json.loads([ln for ln in audit_path.read_text().splitlines() if ln.strip()][-1])
    jid = evt["judgment_id"]
    ref = evt["outcome_ref"]
    assert isinstance(ref, str) and jid in ref and ref.endswith(".json")

    # record outcome to tmp outs (write tool writes to default dir; we simulate by writing manually here)
    # easiest: write into repo default and just assert file exists there by jid
    p4 = subprocess.run([sys.executable, str(RECORD), "--judgment-id", jid, "--label", "WIN", "--pnl_r", "1.2"],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    assert p4.returncode == 0, p4.stderr

    out = json.loads(p4.stdout)
    path = Path(out["path"])
    assert path.exists()
    rec = json.loads(path.read_text().strip())
    assert rec["schema"] == "outcome_record.v1"
    assert rec["judgment_id"] == jid
