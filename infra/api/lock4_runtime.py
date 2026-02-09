from __future__ import annotations

from pathlib import Path
from typing import Mapping, Optional, Union
import os
import subprocess


def resolve_lock4_sig_mode(env: Optional[Mapping[str, str]] = None) -> str:
    """
    Resolve LOCK4 signature enforcement mode.

    Policy:
    - default: "warn"
    - If LOCK4_SIG_MODE=enforce but LOCK4_PROMOTE_ENFORCE != "1": downgrade to "warn"
    - Only if both enforce + promote flag: "enforce"
    """
    e = env or os.environ
    mode = (e.get("LOCK4_SIG_MODE") or "").strip().lower()
    promote = (e.get("LOCK4_PROMOTE_ENFORCE") or "").strip()

    if mode != "enforce":
        return "warn"
    if promote != "1":
        return "warn"
    return "enforce"


def run_lock4_preflight_or_die(mode: str, workspace_dir: Union[str, Path]) -> int:
    """
    Run LOCK4 preflight via subprocess.

    Contract:
    - mode == "warn":   always return 0 (continue)
    - mode == "enforce": return rc (fail-fast decision handled by caller)
    """
    wd = str(workspace_dir)

    proc = subprocess.run(
        ["python", "-m", "tools.gates.lock4_preflight", "--workspace", wd],
        capture_output=True,
        text=True,
    )
    rc = int(getattr(proc, "returncode", 1) or 0)

    if mode == "warn":
        return 0
    return rc


def preflight_lock4_runtime(
    env: Optional[Mapping[str, str]] = None,
    workspace_dir: Optional[Union[str, Path]] = None,
) -> int:
    """
    Convenience wrapper used by runtime startup.

    Returns:
      0 on success or warn-mode continuation
      non-zero in enforce mode when preflight fails
    """
    mode = resolve_lock4_sig_mode(env)
    wd = workspace_dir or os.getcwd()
    return run_lock4_preflight_or_die(mode, wd)
