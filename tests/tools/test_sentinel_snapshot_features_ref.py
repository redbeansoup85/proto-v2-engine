import json
import subprocess
import sys
from pathlib import Path

GEN = Path("tools/local/llm_generate_intent.py")
GATE = Path("tools/gates/sentinel_trade_intent_schema_gate.py")
CONSUMER = Path("tools/sentinel/consume_trade_intent.py")
VERIFY = Path("tools/audits/verify_judgment_event_chain.py")

def test_features_ref_points_to_existing_snapshot(tmp_path):
    audit_path = tmp_path / "chain.jsonl"
    snap_dir = tmp_path / "snapshots"

    # generate intent (mock)
    p1 = subprocess.run(
        [sys.executable, str(GEN), "--backend", "mock"],
        input="BTCUSDT 롱",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p1.returncode == 0, p1.stderr

    # gate pass-through
    p2 = subprocess.run(
        [sys.executable, str(GATE)],
        input=p1.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p2.returncode == 0, p2.stderr

    # consume and write snapshot + chain
    p3 = subprocess.run(
        [sys.executable, str(CONSUMER), "--audit-path", str(audit_path), "--snapshot-dir", str(snap_dir)],
        input=p2.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p3.returncode == 0, p3.stderr

    # verify chain OK
    ok = subprocess.run(
        [sys.executable, str(VERIFY), "--path", str(audit_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert ok.returncode == 0, ok.stderr

    # parse last event
    lines = [ln for ln in audit_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    evt = json.loads(lines[-1])
    ref = evt["features_ref"]
    assert isinstance(ref, str) and ref != "n/a"

    # in this test we passed --snapshot-dir, so file should exist there by filename
    fname = Path(ref).name
    snap_path = snap_dir / fname
    assert snap_path.exists()

    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    assert snap["schema"] == "market_snapshot.v1"
