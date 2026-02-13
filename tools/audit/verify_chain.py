from __future__ import annotations
import argparse
import json
from pathlib import Path
from jsonschema import Draft202012Validator
from tools.audit.chain_hasher import event_hash

def _load_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))

def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    out = []
    for line in path.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line:
            continue
        out.append(json.loads(line))
    return out

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--schema", required=True)
    ap.add_argument("--chain", required=True)
    args = ap.parse_args()

    schema = _load_json(Path(args.schema))
    Draft202012Validator.check_schema(schema)
    v = Draft202012Validator(schema)

    chain = _read_jsonl(Path(args.chain))

    prev_hash = "GENESIS"
    for idx, ev in enumerate(chain):
        errors = sorted(v.iter_errors(ev), key=lambda e: e.path)
        if errors:
            print(f"FAIL-CLOSED: schema violation at index={idx} event_id={ev.get('event_id')}")
            for e in errors[:5]:
                print(f"- {list(e.path)}: {e.message}")
            return 1

        hp = ev.get("hash_prev") or ev.get("prev_hash")
        if not isinstance(hp, str) or not hp.strip():
            print(f"FAIL-CLOSED: missing hash_prev/prev_hash at index={idx}")
            return 1

        if idx == 0:
            if hp != "GENESIS":
                print("FAIL-CLOSED: first event must have hash_prev=GENESIS")
                return 1
        else:
            if hp != prev_hash:
                print(f"FAIL-CLOSED: broken chain link at index={idx} (hash_prev mismatch)")
                return 1

        prev_hash = event_hash(ev)

    print("OK: chain verified")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
