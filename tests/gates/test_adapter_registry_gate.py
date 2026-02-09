import subprocess
import sys


def test_gate_cli_passes():
    r = subprocess.run(
        [sys.executable, "tools/gates/adapter_registry_gate.py"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, (r.stdout or "") + "\n" + (r.stderr or "")
