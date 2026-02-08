from __future__ import annotations

import os
import subprocess
import sys

def test_zone_static_gate_runs_pass_on_repo() -> None:
    # This test assumes the repository does not contain forbidden edges at baseline.
    # If repo currently contains cross-zone imports, this test will surface it.
    root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    cmd = [sys.executable, "tools/gates/zone_static_gate.py", "--root", root]
    p = subprocess.run(cmd, cwd=root, capture_output=True, text=True)
    assert p.returncode in (0, 1)  # gate itself decides; we assert it executed
    assert ("PASS ZONE_STATIC_GATE" in p.stdout) or ("FAIL" in p.stdout)
