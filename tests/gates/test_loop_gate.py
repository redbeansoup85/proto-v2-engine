from __future__ import annotations
import json, subprocess
from pathlib import Path

def _run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    out = p.stdout.strip().splitlines()[-1] if p.stdout.strip() else ""
    return p.returncode, json.loads(out)

def test_loop_gate_pass_minimal(tmp_path: Path):
    root = tmp_path / "tasks"
    d = root / "domainA" / "task1"
    d.mkdir(parents=True)
    (d / "TASK_LOOP.yaml").write_text(
        'CREATED_AT_UTC: "2026-02-08T00:00:00Z"\n'
        "INTENT: x\nEXPECTED_OUTCOME: x\nEXECUTION: x\nNEXT_ACTION: x\nRESULT: OPEN\n",
        encoding="utf-8",
    )
    rc, data = _run(["python", "tools/gates/loop_gate.py", "--root", str(root)], Path("."))
    assert rc == 0 and data["status"] == "PASS" and data["findings"] == []

def test_loop_gate_fail_missing_key(tmp_path: Path):
    root = tmp_path / "tasks"
    d = root / "domainA" / "task1"
    d.mkdir(parents=True)
    (d / "TASK_LOOP.yaml").write_text(
        'CREATED_AT_UTC: "2026-02-08T00:00:00Z"\nINTENT: x\n',
        encoding="utf-8",
    )
    rc, data = _run(["python", "tools/gates/loop_gate.py", "--root", str(root)], Path("."))
    assert rc == 1 and data["status"] == "FAIL"
    assert any(f["rule_id"] == "TASK_LOOP_REQUIRED_KEY_MISSING" for f in data["findings"])
