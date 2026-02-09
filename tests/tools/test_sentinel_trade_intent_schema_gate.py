import json
import subprocess
import sys
from pathlib import Path

GATE = Path("tools/gates/sentinel_trade_intent_schema_gate.py")

def _run_gate(obj):
    return subprocess.run(
        [sys.executable, str(GATE)],
        input=json.dumps(obj).encode("utf-8"),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )

def test_gate_pass_through_valid_intent():
    obj = {
        "schema": "sentinel_trade_intent.v1",
        "domain_id": "sentinel.trade",
        "intent_id": "INTENT-ABCDEFG1",
        "mode": "DRY_RUN",
        "asset": "BTCUSDT",
        "side": "LONG",
        "notes": "ok",
    }
    p = _run_gate(obj)
    assert p.returncode == 0, p.stderr.decode("utf-8", errors="replace")

    out = json.loads(p.stdout.decode("utf-8", errors="replace"))
    assert out == obj  # pass-through must preserve content

def test_gate_fail_extra_key():
    obj = {
        "schema": "sentinel_trade_intent.v1",
        "domain_id": "sentinel.trade",
        "intent_id": "INTENT-ABCDEFG1",
        "mode": "DRY_RUN",
        "asset": "BTCUSDT",
        "side": "LONG",
        "notes": "ok",
        "qty": 1,  # forbidden
    }
    p = _run_gate(obj)
    assert p.returncode == 2
    err = p.stderr.decode("utf-8", errors="replace")
    assert "UNEXPECTED_KEYS" in err

def test_gate_fail_mode_not_dry_run():
    obj = {
        "schema": "sentinel_trade_intent.v1",
        "domain_id": "sentinel.trade",
        "intent_id": "INTENT-ABCDEFG1",
        "mode": "LIVE",
        "asset": "BTCUSDT",
        "side": "LONG",
        "notes": "ok",
    }
    p = _run_gate(obj)
    assert p.returncode == 2
    err = p.stderr.decode("utf-8", errors="replace")
    assert "MODE_NOT_DRY_RUN" in err
