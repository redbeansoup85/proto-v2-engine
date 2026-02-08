import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def test_loop_gate_emits_gate_findings_envelope_v1():
    proc = subprocess.run(
        ["python", "tools/gates/loop_gate.py", "--root", "tasks"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
    )

    assert proc.stdout.strip(), f"expected stdout JSON, got: {proc.stdout!r} {proc.stderr!r}"

    obj = json.loads(proc.stdout)

    assert obj["gate"] == "loop-gate"
    assert obj["version"] == "v1"
    assert obj["status"] in ("PASS", "FAIL")
    assert isinstance(obj["findings"], list)

    for f in obj["findings"]:
        assert f["severity"] in ("ERROR", "WARN", "INFO")
        assert "rule_id" in f and f["rule_id"]
        assert "file" in f and f["file"]
        assert "message" in f and f["message"]
        if f.get("line") is not None:
            assert isinstance(f["line"], int) and f["line"] >= 1
