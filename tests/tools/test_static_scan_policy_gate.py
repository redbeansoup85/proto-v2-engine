import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def test_no_scan_workflow_pass(tmp_path: Path):
    write(tmp_path / "policies/static_scan_ignore_allowlist.yaml", "version: 1\npaths: []\n")
    (tmp_path / ".github/workflows").mkdir(parents=True, exist_ok=True)
    rc, out, err = run([sys.executable, str(ROOT / "tools/gates/static_scan_policy_gate.py"), "--root", "."], tmp_path)
    assert rc == 0, (out, err)
