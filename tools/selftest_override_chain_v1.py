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



def _assert_fail(cp: subprocess.CompletedProcess, what: str) -> None:
    if cp.returncode == 0:
        raise AssertionError(f"{what} unexpectedly succeeded stdout={cp.stdout}")



def main() -> None:
    with tempfile.TemporaryDirectory() as td:
        audit = str(Path(td) / "override_events.jsonl")

        policy = "a" * 64
        decision_hash = "b" * 64

        req_cmd = [
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
            policy,
            "--target-decision-event-id",
            "dec_123",
            "--target-decision-hash",
            decision_hash,
            "--evidence-ref",
            "snapshot:/path/a.json",
            "--evidence-ref",
            "report:/path/b.json",
            "--requested-action",
            "block_execution",
            "--reason-code",
            "ANOMALY_DETECTED",
            "--reason-text",
            "anomaly",
            "--ttl-sec",
            "300",
        ]
        cp = _run(req_cmd)
        _assert_ok(cp, "append requested")

        lines = Path(audit).read_text(encoding="utf-8").splitlines()
        request_event_id = json.loads(lines[0])["event_id"]

        appr_cmd = [
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
            "ap-01",
            "--policy-sha256",
            policy,
            "--target-decision-event-id",
            "dec_123",
            "--target-decision-hash",
            decision_hash,
            "--evidence-ref",
            "approval:/path/c.json",
            "--ref-request-event-id",
            request_event_id,
            "--scope",
            "BTCUSDT",
            "--expires-at",
            "2026-02-15T05:34:00Z",
            "--max-notional",
            "1000",
        ]
        cp = _run(appr_cmd)
        _assert_ok(cp, "append approved")

        verify_cmd = [sys.executable, "tools/audit/verify_override_chain.py", "--audit-jsonl", audit]
        cp = _run(verify_cmd)
        _assert_ok(cp, "verify pass")

        rows = [json.loads(x) for x in Path(audit).read_text(encoding="utf-8").splitlines() if x.strip()]
        rows[1]["evidence_refs"] = ["tampered:/x"]
        Path(audit).write_text("\n".join(json.dumps(r, sort_keys=True, separators=(",", ":")) for r in rows) + "\n", encoding="utf-8")

        cp = _run(verify_cmd)
        _assert_fail(cp, "verify tampered")

        bad_cmd = [
            sys.executable,
            "tools/override/override_append.py",
            "--audit-jsonl",
            audit,
            "--type",
            "OVERRIDE_REQUESTED",
            "--ts",
            "2026-02-15T03:35:00Z",
            "--actor-role",
            "operator",
            "--actor-subject",
            "op-02",
            "--policy-sha256",
            policy,
            "--target-decision-event-id",
            "dec_124",
            "--target-decision-hash",
            decision_hash,
            "--requested-action",
            "block_execution",
            "--reason-code",
            "ANOMALY_DETECTED",
            "--reason-text",
            "anomaly",
            "--ttl-sec",
            "300",
        ]
        cp = _run(bad_cmd)
        _assert_fail(cp, "append evidence empty")

    print("SELFTEST_OK")


if __name__ == "__main__":
    main()
