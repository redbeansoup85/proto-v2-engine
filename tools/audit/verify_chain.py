#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

# NOTE:
# event_hash()는 "payload 기반 해시" 류일 수 있음.
# 우리 체인 링크 검증은 "row가 들고 있는 hash"와 prev_hash 링크를 기준으로 해야 함.
from tools.audit.chain_hasher import event_hash


def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out: list[dict] = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out


def _is_nonempty_str(x: Any) -> bool:
    return isinstance(x, str) and bool(x.strip())


def _get_prev_hash(ev: dict) -> str | None:
    # top-level preferred
    if _is_nonempty_str(ev.get("prev_hash")):
        return str(ev["prev_hash"])
    if _is_nonempty_str(ev.get("hash_prev")):
        return str(ev["hash_prev"])

    # nested fallbacks
    ch = ev.get("chain")
    if isinstance(ch, dict):
        if _is_nonempty_str(ch.get("prev_hash")):
            return str(ch["prev_hash"])
        if _is_nonempty_str(ch.get("hash_prev")):
            return str(ch["hash_prev"])
        if _is_nonempty_str(ch.get("prev")):
            return str(ch["prev"])

    return None


def _get_row_hash(ev: dict) -> str | None:
    """
    Chain-link target hash.
    We prefer the explicit stored row hash; only if missing, we can fall back to
    computed event_hash(ev) as a last resort (still fail-closed if empty).
    """
    # top-level preferred
    if _is_nonempty_str(ev.get("hash")):
        return str(ev["hash"])

    # nested fallbacks
    ch = ev.get("chain")
    if isinstance(ch, dict):
        if _is_nonempty_str(ch.get("hash")):
            return str(ch["hash"])
        if _is_nonempty_str(ch.get("chain_hash")):
            return str(ch["chain_hash"])

    # last resort: computed
    try:
        h = event_hash(ev)
        if _is_nonempty_str(h):
            return str(h)
    except Exception:
        return None

    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True)
    ap.add_argument("--chain", required=True)
    args = ap.parse_args()

    schema = _load_json(Path(args.schema))
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)

    chain = _read_jsonl(Path(args.chain))

    prev_link = "GENESIS"

    for idx, ev in enumerate(chain):
        # 1) schema validation (fail-closed)
        errors = sorted(v.iter_errors(ev), key=lambda e: e.path)
        if errors:
            print(f"FAIL-CLOSED: schema violation at index={idx} event_id={ev.get('event_id')}")
            for e in errors[:5]:
                print(f"- {list(e.path)}: {e.message}")
            return 1

        # 2) prev hash extraction (fail-closed)
        hp = _get_prev_hash(ev)
        if not _is_nonempty_str(hp):
            print(f"FAIL-CLOSED: missing prev_hash/hash_prev at index={idx}")
            return 1

        # 3) chain link check (fail-closed)
        if idx == 0:
            if hp != "GENESIS":
                print("FAIL-CLOSED: first event must have prev_hash/hash_prev=GENESIS")
                return 1
        else:
            if hp != prev_link:
                print(f"FAIL-CLOSED: broken chain link at index={idx} (hash_prev mismatch)")
                return 1

        # 4) advance prev_link using stored row hash (preferred)
        row_hash = _get_row_hash(ev)
        if not _is_nonempty_str(row_hash):
            print(f"FAIL-CLOSED: missing row hash at index={idx} (expected hash/chain.hash)")
            return 1

        prev_link = row_hash

    print("OK: chain verified")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
