from pathlib import Path
from tools.gates.lock2_gate import scan_tree

def test_lock2_gate_blocks_execution_refs_outside_approval(tmp_path: Path):
    # outside approval path: should fail
    (tmp_path / "x.py").write_text("from infra.api.endpoints import execution\n", encoding="utf-8")
    findings = scan_tree(tmp_path)
    assert len(findings) >= 1

def test_lock2_gate_allows_execution_refs_in_approval_path(tmp_path: Path):
    # inside approval path: allowed (for wiring), by design
    ap = tmp_path / "approval_gate.py"
    ap.write_text("from infra.api.endpoints import execution\n", encoding="utf-8")
    findings = scan_tree(tmp_path)
    assert findings == []
