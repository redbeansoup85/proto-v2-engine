#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
from pathlib import Path
from typing import Any

from tools.gates.gate_provider_ingest import validate_provider_envelope

TS_UTC = "2026-02-19T00:00:00Z"
REPO_ROOT = Path(__file__).resolve().parents[2]
LOCKFILE = REPO_ROOT / "schemas" / "schema_registry.lock.json"


def _payload_hash(body: dict[str, Any]) -> str:
    raw = json.dumps(body, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _envelope(*, run_id: str, event_id: str, schema_id: str, body: dict[str, Any]) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "event_id": event_id,
        "ts_utc": TS_UTC,
        "provider": {
            "provider_id": "sentinel",
            "provider_class": "SIGNAL_ONLY",
        },
        "payload": {
            "schema_id": schema_id,
            "schema_version": "1",
            "body": body,
        },
        "hash": {
            "hash_alg": "sha256",
            "payload_hash": _payload_hash(body),
        },
    }


def _with_cwd(cwd: Path):
    class _CwdCtx:
        def __enter__(self):
            self.prev = Path.cwd()
            os.chdir(cwd)
            return self

        def __exit__(self, exc_type, exc, tb):
            os.chdir(self.prev)

    return _CwdCtx()


def validate_or_record(envelope: dict[str, Any], *, exceptions_dir: Path) -> list[dict]:
    work_dir = exceptions_dir.parent
    work_dir.mkdir(parents=True, exist_ok=True)
    schemas_dir = work_dir / "schemas"
    schemas_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(LOCKFILE, schemas_dir / "schema_registry.lock.json")

    with _with_cwd(work_dir):
        return validate_provider_envelope(envelope)


def run_smoke(*, exceptions_dir: Path) -> int:
    try:
        valid = _envelope(
            run_id="RUN-SMOKE-OK",
            event_id="EVT-SMOKE-OK",
            schema_id="sentinel_raw_snapshot.v1",
            body={"symbol": "SOLUSDT", "tf": "15m"},
        )
        invalid = _envelope(
            run_id="RUN-SMOKE-BAD",
            event_id="EVT-SMOKE-BAD",
            schema_id="sentinel_raw_snapshot.v1",
            body={"x": {"qty": 1}},
        )

        v1 = validate_or_record(valid, exceptions_dir=exceptions_dir)
        print("OK" if not v1 else "REJECT")
        if v1:
            return 1

        v2 = validate_or_record(invalid, exceptions_dir=exceptions_dir)
        print("OK" if not v2 else "REJECT")
        if not v2:
            return 1

        exc_file = exceptions_dir / "RUN-SMOKE-BAD.jsonl"
        if not exc_file.exists():
            return 1

        lines = exc_file.read_text(encoding="utf-8").strip().splitlines()
        if len(lines) != 1:
            return 1
        row = json.loads(lines[0])
        violations = row.get("violations")
        if not isinstance(violations, list) or not violations:
            return 1
        if not any("qty" in str(v.get("path", "")) for v in violations if isinstance(v, dict)):
            return 1
        return 0
    except Exception:  # noqa: BLE001
        return 1


def main(exceptions_dir: str | None = None) -> int:
    if exceptions_dir is None:
        ap = argparse.ArgumentParser(description="Sentinel->Meta provider ingest smoke runner (fail-closed).")
        ap.add_argument("--exceptions-dir", default=str(REPO_ROOT / "Exceptions"))
        args = ap.parse_args()
        exceptions_path = Path(args.exceptions_dir)
    else:
        exceptions_path = Path(exceptions_dir)
    return run_smoke(exceptions_dir=exceptions_path)


if __name__ == "__main__":
    raise SystemExit(main())
