import json
import subprocess
import sys
from pathlib import Path


def run_gate(root: Path):
    p = subprocess.run(
        [sys.executable, "tools/public_docs_gate.py", "--root", str(root)],
        cwd=root,
        text=True,
        capture_output=True,
    )
    return p.returncode, p.stdout.strip().splitlines()[-1]


def test_pass(tmp_path: Path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "docs/public").mkdir(parents=True)

    gate = Path("tools/public_docs_gate.py").read_text()
    (tmp_path / "tools/public_docs_gate.py").write_text(gate)

    (tmp_path / "docs/public/README.md").write_text(
        "Public spec only.\n", encoding="utf-8"
    )

    code, last = run_gate(tmp_path)
    assert code == 0
    assert json.loads(last)["status"] == "PASS"


def test_fail(tmp_path: Path):
    (tmp_path / "tools").mkdir()
    (tmp_path / "docs/public").mkdir(parents=True)

    gate = Path("tools/public_docs_gate.py").read_text()
    (tmp_path / "tools/public_docs_gate.py").write_text(gate)

    (tmp_path / "docs/public/PIPELINE.md").write_text(
        "Uses var/ai internally.\n", encoding="utf-8"
    )

    code, last = run_gate(tmp_path)
    assert code == 1
    assert json.loads(last)["status"] == "FAIL"
