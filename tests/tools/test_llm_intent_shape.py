import json
import os
import subprocess
import sys


def test_llm_generate_intent_shape_mock():
    env = os.environ.copy()
    env["LLM_BACKEND"] = "mock"

    p = subprocess.run(
        [sys.executable, "tools/local/llm_generate_intent.py"],
        input="BTC 롱 드라이런 해줘",
        text=True,
        capture_output=True,
        env=env,
    )
    assert p.returncode == 0, (p.stdout or "") + "\n" + (p.stderr or "")

    obj = json.loads(p.stdout)
    # required shape
    for k in ["schema", "domain_id", "intent_id", "asset", "side", "mode", "notes"]:
        assert k in obj

    assert obj["schema"] == "sentinel_trade_intent.v1"
    assert obj["domain_id"] == "sentinel.trade"
    assert obj["mode"] == "DRY_RUN"
    assert obj["side"] in ("LONG", "SHORT", "FLAT")
    assert isinstance(obj["asset"], str) and len(obj["asset"]) >= 3
    assert isinstance(obj["intent_id"], str) and obj["intent_id"].startswith("INTENT-")
