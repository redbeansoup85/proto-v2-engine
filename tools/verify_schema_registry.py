#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

# Ensure project root is importable when run as a script (fail-closed)
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import json
from typing import Any, Dict

from core.canonical_json import canonical_json
from core.hasher import _sha256_bytes  # internal util; keep unless removed

REGISTRY = Path("Judgment_Data/registry/schema_registry.jsonl")
SCHEMA_DIR = Path("Judgment_Data/schemas")

def die(msg: str) -> None:
    print(f"[FAIL-CLOSED] {msg}", file=sys.stderr)
    raise SystemExit(1)

def load_registry() -> Dict[str, Dict[str, Any]]:
    if not REGISTRY.exists():
        die(f"missing registry file: {REGISTRY}")
    out: Dict[str, Dict[str, Any]] = {}
    for i, line in enumerate(REGISTRY.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        obj = json.loads(line)
        sid = obj.get("schema_id")
        if not isinstance(sid, str):
            die(f"registry line {i}: missing schema_id")
        out[sid] = obj
    return out

def compute_schema_hash(schema_path: Path) -> str:
    if not schema_path.exists():
        die(f"missing schema file: {schema_path}")
    obj = json.loads(schema_path.read_text(encoding="utf-8"))
    canon = canonical_json(obj)
    return _sha256_bytes(canon)

def main() -> None:
    reg = load_registry()
    # 현재 Phase-1에서 강제할 스키마만 체크 (필요 시 확장)
    target_id = "JOS-JUDGMENT-COMMON-v1.0"
    if target_id not in reg:
        die(f"registry missing schema_id={target_id}")

    entry = reg[target_id]
    declared = entry.get("schema_hash")
    if not isinstance(declared, str) or not declared.startswith("sha256:"):
        die(f"registry schema_hash invalid for {target_id}: {declared!r}")

    schema_path = SCHEMA_DIR / f"{target_id}.json"
    computed = compute_schema_hash(schema_path)

    if computed != declared:
        die(
            f"schema_hash mismatch for {target_id}\n"
            f"  declared: {declared}\n"
            f"  computed: {computed}\n"
            f"Fix: update registry OR schema file (LOCK requires exact match)."
        )

    print(f"OK: schema_registry matches schema file for {target_id}")

if __name__ == "__main__":
    main()
