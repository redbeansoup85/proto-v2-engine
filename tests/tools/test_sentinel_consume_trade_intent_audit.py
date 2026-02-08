import json
import subprocess
import sys
from pathlib import Path

CONSUMER = Path("tools/sentinel/consume_trade_intent.py")

def test_consumer_appends_jsonl(tmp_path):
    audit_path = tmp_path / "judgment_events.jsonl"

    intent = {
        "schema": "sentinel_trade_intent.v1",
        "domain_id": "sentinel.trade",
        "intent_id": "INTENT-ABCDEFG1",
        "mode": "DRY_RUN",
        "asset": "BTCUSDT",
        "side": "LONG",
        "notes": "ok",
    }

    p = subprocess.run(
        [sys.executable, str(CONSUMER), "--audit-path", str(audit_path)],
        input=json.dumps(intent).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    assert p.returncode == 0, p.stderr.decode("utf-8", errors="replace")

    # file exists and has one JSON line
    assert audit_path.exists()
    lines = audit_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(lines) == 1

    evt = json.loads(lines[0])
    assert evt["schema"] == "judgment_event.v1"
    assert evt["domain_id"] == "sentinel.trade"
    assert evt["intent_id"] == intent["intent_id"]
    assert evt["mode"] == "DRY_RUN"
    assert evt["status"] == "ACCEPTED"
