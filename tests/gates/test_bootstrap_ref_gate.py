from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def run(cmd, cwd: Path):
    return subprocess.run(cmd, cwd=cwd, text=True, capture_output=True)


def test_gate_fails_when_missing_bootstrap(tmp_path: Path):
    (tmp_path / "execution_cards").mkdir(parents=True)

    gate = Path("tools/gates/bootstrap_ref_gate.py").resolve()
    assert gate.exists()

    (tmp_path / "execution_cards" / "bad.yaml").write_text(
        "id: X\nrequires:\n  - LOCK-2\n", encoding="utf-8"
    )

    r = run([sys.executable, str(gate), "--root", str(tmp_path)], cwd=tmp_path)
    assert r.returncode == 1
    assert "EXECUTION_CARD_BOOTSTRAP_REQUIRED" in (r.stdout + r.stderr)


def test_gate_passes_when_present(tmp_path: Path):
    (tmp_path / "execution_cards").mkdir(parents=True)

    gate = Path("tools/gates/bootstrap_ref_gate.py").resolve()
    assert gate.exists()

    (tmp_path / "execution_cards" / "good.yaml").write_text(
        "id: X\nrequires:\n  - LOCK-BOOTSTRAP\n  - LOCK-2\n",
        encoding="utf-8",
    )

    r = run([sys.executable, str(gate), "--root", str(tmp_path)], cwd=tmp_path)
    assert r.returncode == 0
    assert "OK:" in (r.stdout + r.stderr)
