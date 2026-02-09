import json
from pathlib import Path
from tools.gates.sentinel_intent_gate import gate

FIX = Path(__file__).parent / "fixtures"

def load(name):
    raw = (FIX / name).read_bytes()
    return json.loads(raw), raw

def test_ok():
    payload, raw = load("intent_ok.json")
    res = gate(payload, raw)
    assert res["ok"] is True

def test_forbidden():
    payload, raw = load("intent_forbidden_fields.json")
    res = gate(payload, raw)
    assert res["ok"] is False
    assert res["reason"] == "FORBIDDEN_FIELD_PRESENT"
