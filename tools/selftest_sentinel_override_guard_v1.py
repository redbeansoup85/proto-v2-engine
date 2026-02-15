#!/usr/bin/env python3
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]



def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, cwd=str(ROOT), text=True, capture_output=True)



def _assert_ok(cp: subprocess.CompletedProcess, what: str) -> None:
    if cp.returncode != 0:
        raise AssertionError(f"{what} failed rc={cp.returncode} stderr={cp.stderr} stdout={cp.stdout}")



def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        audit = str(Path(td) / "override_events.jsonl")
        policy_sha = "a" * 64
        decision_hash = "b" * 64

        cp = _run(
            [
                sys.executable,
                "tools/override/override_append.py",
                "--audit-jsonl",
                audit,
                "--type",
                "OVERRIDE_REQUESTED",
                "--ts",
                "2026-02-15T03:33:00Z",
                "--actor-role",
                "operator",
                "--actor-subject",
                "op-01",
                "--policy-sha256",
                policy_sha,
                "--target-decision-event-id",
                "dec_123",
                "--target-decision-hash",
                decision_hash,
                "--evidence-ref",
                "snapshot:/tmp/a.json",
                "--requested-action",
                "block_execution",
                "--reason-code",
                "ANOMALY_DETECTED",
                "--reason-text",
                "manual block",
                "--ttl-sec",
                "600",
            ]
        )
        _assert_ok(cp, "append request")

        req_id = json.loads(Path(audit).read_text(encoding="utf-8").splitlines()[0])["event_id"]

        cp = _run(
            [
                sys.executable,
                "tools/override/override_append.py",
                "--audit-jsonl",
                audit,
                "--type",
                "OVERRIDE_APPROVED",
                "--ts",
                "2026-02-15T03:34:00Z",
                "--actor-role",
                "approver",
                "--actor-subject",
                "approver-01",
                "--policy-sha256",
                policy_sha,
                "--target-decision-event-id",
                "dec_123",
                "--target-decision-hash",
                decision_hash,
                "--evidence-ref",
                "approval:/tmp/b.json",
                "--ref-request-event-id",
                req_id,
                "--scope",
                "BTCUSDT",
                "--expires-at",
                "2026-02-15T05:00:00Z",
                "--max-notional",
                "1000",
            ]
        )
        _assert_ok(cp, "append approval")

        cp = _run(
            [
                sys.executable,
                "tools/sentinel/sentinel_override_guard.py",
                "--audit-jsonl",
                audit,
                "--symbol",
                "BTCUSDT",
                "--now-ts",
                "2026-02-15T03:40:00Z",
            ]
        )
        _assert_ok(cp, "guard btc")
        out = json.loads(cp.stdout.strip().splitlines()[-1])
        if out.get("allow") is not False or out.get("reason") != "ACTIVE_OVERRIDE_BLOCK":
            raise AssertionError(f"unexpected guard result for BTCUSDT: {out}")

        cp = _run(
            [
                sys.executable,
                "tools/sentinel/sentinel_override_guard.py",
                "--audit-jsonl",
                audit,
                "--symbol",
                "ETHUSDT",
                "--now-ts",
                "2026-02-15T03:40:00Z",
            ]
        )
        _assert_ok(cp, "guard eth")
        out2 = json.loads(cp.stdout.strip().splitlines()[-1])
        if out2.get("allow") is not True:
            raise AssertionError(f"unexpected guard result for ETHUSDT: {out2}")

    print("SELFTEST_OK_GUARD")


if __name__ == "__main__":
    main()
