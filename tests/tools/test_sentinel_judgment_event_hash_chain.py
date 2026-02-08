import json
import subprocess
import sys
from pathlib import Path

GEN = Path("tools/local/llm_generate_intent.py")
GATE = Path("tools/gates/sentinel_trade_intent_schema_gate.py")
CONSUMER = Path("tools/sentinel/consume_trade_intent.py")
VERIFY = Path("tools/audits/verify_judgment_event_chain.py")

def _run_pipeline(text: str, audit_path: Path):
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

def test_hash_chain_verifies_and_detects_tamper(tmp_path):
    audit_path = tmp_path / "chain.jsonl"

    _run_pipeline("BTCUSDT 롱", audit_path)
    _run_pipeline("SOLUSDT 숏", audit_path)

    # verify OK
    ok = subprocess.run(
        [sys.executable, str(VERIFY), "--path", str(audit_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert ok.returncode == 0, ok.stderr

    # tamper last line (flip one char)
    lines = audit_path.read_text(encoding="utf-8").splitlines()
    obj = json.loads(lines[-1])
    obj["card_id"] = obj["card_id"] + "-TAMPER"
    lines[-1] = json.dumps(obj, sort_keys=True, separators=(",", ":"))
    audit_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    bad = subprocess.run(
        [sys.executable, str(VERIFY), "--path", str(audit_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert bad.returncode == 2
    assert "HASH_MISMATCH" in bad.stderr
