#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

if __package__ is None or __package__ == "":
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from tools.gates.gate_provider_ingest import get_allowed_schema_ids


def compute_sha256(path: str | Path) -> str:
    p = Path(path)
    data = p.read_bytes()
    return hashlib.sha256(data).hexdigest()


def load_registry(path: str | Path) -> dict:
    p = Path(path)
    return json.loads(p.read_text(encoding="utf-8"))


def _violation(reason: str, path: str, expected: Any, got: Any) -> dict:
    return {
        "reason": reason,
        "path": path,
        "expected": expected,
        "got": got,
    }


def verify_registry(registry_path: str = "schemas/schema_registry.lock.json") -> list[dict]:
    p = Path(registry_path)
    registry = load_registry(p)
    violations: list[dict] = []

    checks = [
        ("constitution", registry["constitution"]["file"], registry["constitution"]["sha256"]),
        ("envelope_schema", registry["envelope_schema"]["schema_file"], registry["envelope_schema"]["sha256"]),
        ("provider_gate", registry["provider_gate"]["file"], registry["provider_gate"]["sha256"]),
    ]
    for name, file_path, expected_sha in checks:
        got_sha = compute_sha256(file_path)
        if got_sha != expected_sha:
            violations.append(
                _violation(
                    "sha_mismatch",
                    f"{name}.sha256",
                    expected_sha,
                    got_sha,
                )
            )

    expected_allowlist = registry.get("allowed_provider_schema_ids")
    got_allowlist = get_allowed_schema_ids(p)
    if got_allowlist != expected_allowlist:
        violations.append(
            _violation(
                "allowlist_mismatch",
                "allowed_provider_schema_ids",
                expected_allowlist,
                got_allowlist,
            )
        )

    return violations


def main() -> int:
    ap = argparse.ArgumentParser(description="Schema registry drift gate (fail-closed).")
    ap.add_argument("--verify", action="store_true")
    args = ap.parse_args()

    if not args.verify:
        return 1

    try:
        violations = verify_registry()
    except Exception as exc:  # noqa: BLE001
        violations = [_violation("registry_verify_error", "schemas/schema_registry.lock.json", "valid_registry", str(exc))]

    for item in violations:
        print(json.dumps(item, sort_keys=True, ensure_ascii=False))
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
