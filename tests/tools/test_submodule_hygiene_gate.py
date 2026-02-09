import subprocess, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return p.returncode, p.stdout, p.stderr

def write(p: Path, s: str):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(s, encoding="utf-8")

def test_no_submodules_pass(tmp_path: Path):
    run(["git","init"], tmp_path)
    write(tmp_path / "policies/submodules_allowlist.yaml", "version: 1\nentries: []\n")
    rc, out, err = run([sys.executable, str(ROOT / "tools/gates/submodule_hygiene_gate.py"), "--root", "."], tmp_path)
    assert rc == 0, (out, err)
