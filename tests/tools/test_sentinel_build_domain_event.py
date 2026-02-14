import json
import subprocess
import sys
from pathlib import Path

TOOL = Path("tools/sentinel_build_domain_event.py")


def test_build_domain_event_and_validate(tmp_path):
    out = tmp_path / "domain_event.json"
    p = subprocess.run(
        [
            sys.executable,
            str(TOOL),
            "--symbol",
            "BTCUSDT",
            "--score",
            "88",
            "--confidence",
            "0.91",
            "--risk-level",
            "medium",
            "--tags",
            "warn,bybit",
            "--evidence",
            "ref_kind=FILEPATH ref=/tmp/norm.json",
            "--ci",
            "--out",
            str(out),
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    assert p.returncode == 0, p.stderr
    assert out.exists()

    evt = json.loads(out.read_text(encoding="utf-8"))
    assert evt["schema"] == "domain_event.v1"
    assert evt["domain"] == "sentinel"
    assert evt["kind"] == "SIGNAL"
    assert evt["signal"]["type"] == "BYBIT_ALERT"
    assert evt["signal"]["symbol"] == "BTCUSDT"
    assert evt["ts_iso"] == "1970-01-01T00:00:00Z"
    assert evt["event_id"] == "SENTINEL:SIGNAL:BYBIT_ALERT:BTCUSDT:0:1"
