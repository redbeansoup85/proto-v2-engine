import json
import subprocess
import sys
from pathlib import Path

GEN = Path("tools/local/llm_generate_intent.py")
GATE = Path("tools/gates/sentinel_trade_intent_schema_gate.py")
CONSUMER = Path("tools/sentinel/consume_trade_intent.py")
VERIFY = Path("tools/audits/verify_judgment_event_chain.py")

def _run(text: str, audit_path: Path):
    p1 = subprocess.Popen(
        [sys.executable, str(GEN), "--backend", "mock"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out1, err1 = p1.communicate(text)
    assert p1.returncode == 0, err1

    p2 = subprocess.Popen(
        [sys.executable, str(GATE)],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out2, err2 = p2.communicate(out1)
    assert p2.returncode == 0, err2

    p3 = subprocess.run(
        [sys.executable, str(CONSUMER), "--audit-path", str(audit_path)],
        input=out2,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p3.returncode == 0, p3.stderr

def test_event_has_card_id_and_rule_hits(tmp_path):
    audit_path = tmp_path / "chain.jsonl"
    _run("BTCUSDT 롱", audit_path)

    lines = [ln for ln in audit_path.read_text(encoding="utf-8").splitlines() if ln.strip()]
    evt = json.loads(lines[-1])

    assert evt["schema"] == "judgment_event.v1"
    assert evt["status"] == "ACCEPTED"
    assert evt["card_id"] in ("CARD-SENTINEL-LONG-v1.0", "CARD-SENTINEL-SHORT-v1.0", "CARD-SENTINEL-FLAT-NOOP-v1.0")
    assert isinstance(evt["rule_hits"], list) and len(evt["rule_hits"]) >= 3

    # chain still verifies
    ok = subprocess.run(
        [sys.executable, str(VERIFY), "--path", str(audit_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert ok.returncode == 0, ok.stderr
