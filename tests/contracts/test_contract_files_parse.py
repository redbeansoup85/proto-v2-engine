import json
from pathlib import Path

CONTRACTS = [
    "engine_request_v1.json",
    "engine_result_v1.json",
    "adapter_contract_v1.json",
]

def test_contract_json_parseable():
    base = Path("core/contracts")
    for name in CONTRACTS:
        p = base / name
        assert p.exists(), f"Missing contract: {p}"
        json.loads(p.read_text(encoding="utf-8"))
