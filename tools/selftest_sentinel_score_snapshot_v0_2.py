#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent
    out = Path("/tmp/metaos_snapshots/BTCUSDT/snapshot_001.json")
    cmd = [
        sys.executable,
        str(root / "tools" / "sentinel_score_snapshot_v0_2.py"),
        "--symbol",
        "BTCUSDT",
        "--ci",
        "--out",
        str(out),
    ]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    if proc.returncode != 0:
        raise SystemExit(proc.stderr.strip() or proc.stdout.strip() or "selftest failed")

    data = json.loads(out.read_text(encoding="utf-8"))
    required_top = ("schema", "symbol", "ts_iso", "timeframes", "derivatives", "score", "flags", "meta")
    for key in required_top:
        if key not in data:
            raise SystemExit(f"missing key: {key}")

    for tf in ("15m", "1h", "4h"):
        if tf not in data["timeframes"]:
            raise SystemExit(f"missing timeframe: {tf}")

    required_score = ("s15", "s1h", "s4h", "final", "direction", "risk_level", "confidence")
    for key in required_score:
        if key not in data["score"]:
            raise SystemExit(f"missing score key: {key}")

    print("OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
