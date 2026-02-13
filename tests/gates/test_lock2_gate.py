from pathlib import Path
from tools.gates.lock2_gate import iter_scan_targets, scan_tree

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


def test_lock2_gate_pr_mode_uses_fallback_when_event_missing(monkeypatch, tmp_path: Path):
    f = tmp_path / "safe.py"
    f.write_text("print('ok')\n", encoding="utf-8")

    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    monkeypatch.setenv("GITHUB_EVENT_NAME", "pull_request")
    monkeypatch.setattr("tools.gates.lock2_gate._git_changed_files_from_pr_event", lambda: [])
    monkeypatch.setattr(
        "tools.gates.lock2_gate._git_changed_files_fallback",
        lambda: [str(f.relative_to(tmp_path))],
    )
    targets = iter_scan_targets(tmp_path)
    assert targets == [f]
