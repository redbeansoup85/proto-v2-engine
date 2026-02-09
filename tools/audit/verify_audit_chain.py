from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA_ID = "kernel.observe_event.v1"

_SCHEMA = {
    "$schema": "https://json-schema.org/draft/2020-12/schema",
    "title": "Kernel Observe Event v1",
    "type": "object",
    "additionalProperties": False,
    "required": ["event_id", "ts", "schema_id", "kind", "meta", "preview"],
    "properties": {
        "event_id": {"type": "string", "minLength": 1},
        "ts": {"type": "string", "minLength": 1},
        "schema_id": {"type": "string", "const": SCHEMA_ID},
        "kind": {"type": "string", "minLength": 1},
        "meta": {"type": "object"},
        "preview": {"type": "object"},
    },
}


def _canonical_json(obj: dict[str, Any]) -> str:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _schema_hash() -> str:
    return _sha256_hex(_canonical_json(_SCHEMA).encode("utf-8"))


def verify_chain(path: Path) -> None:
    if not path.exists():
        raise RuntimeError(f"chain file missing: {path}")

    lines = path.read_text(encoding="utf-8").splitlines()
    prev_hash = "0" * 64
    expected_schema_hash = _schema_hash()

    for idx, line in enumerate(lines, start=1):
        raw = line.strip()
        if not raw:
            raise RuntimeError(f"blank line at {idx}")
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"invalid json at line {idx}: {exc}") from exc
        if not isinstance(row, dict):
            raise RuntimeError(f"invalid row type at line {idx}")
        if row.get("prev_hash") != prev_hash:
            raise RuntimeError(f"prev_hash mismatch at line {idx}")
        if row.get("schema_hash") != expected_schema_hash:
            raise RuntimeError(f"schema_hash mismatch at line {idx}")

        row_hash = row.get("hash")
        if not isinstance(row_hash, str):
            raise RuntimeError(f"missing hash at line {idx}")
        body = {k: v for k, v in row.items() if k != "hash"}
        calc = _sha256_hex(_canonical_json(body).encode("utf-8"))
        if calc != row_hash:
            raise RuntimeError(f"hash mismatch at line {idx}")

        # canonical_event_hash check is optional unless embedded event present
        ev = row.get("event")
        ev_hash = row.get("canonical_event_hash")
        if ev is not None and isinstance(ev, dict) and isinstance(ev_hash, str):
            calc_ev = _sha256_hex(_canonical_json(ev).encode("utf-8"))
            if calc_ev != ev_hash:
                raise RuntimeError(f"canonical_event_hash mismatch at line {idx}")

        prev_hash = row_hash


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify lock3 audit chain")
    parser.add_argument("--path", default="var/audit/lock3_chain.jsonl")
    args = parser.parse_args()
    try:
        verify_chain(Path(args.path))
        print("OK")
        return 0
    except Exception as exc:  # pragma: no cover
        print(f"ERROR: {exc}")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
