from __future__ import annotations
import argparse, hashlib, json
from pathlib import Path
from typing import Any, List

import jsonschema

GATE_ID = "GATE-SENTINEL-INTENT-V1"

FORBIDDEN_KEYS = {
    "execute","execution","place_order","order","orders",
    "position","positions","qty","quantity","size","leverage",
    "entry_price","stop_loss","take_profit","order_type",
    "reduce_only","api_key","secret","token",
    "private_key","seed_phrase","mnemonic"
}

def sha256(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def find_forbidden(obj: Any, path="$") -> List[str]:
    hits = []
    if isinstance(obj, dict):
        for k, v in obj.items():
            p = f"{path}.{k}"
            if k in FORBIDDEN_KEYS:
                hits.append(p)
            hits.extend(find_forbidden(v, p))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            hits.extend(find_forbidden(v, f"{path}[{i}]"))
    return hits

def load_schema() -> dict:
    root = Path(__file__).resolve().parents[2]
    return json.loads((root / "schemas/sentinel_trade_intent.v1.schema.json").read_text())

def gate(payload: dict, raw: bytes) -> dict:
    fp = sha256(raw)

    forbidden = find_forbidden(payload)
    if forbidden:
        return {"ok": False, "reason": "FORBIDDEN_FIELD_PRESENT", "paths": forbidden, "fp": fp}

    if payload.get("mode") != "DRY_RUN":
        return {"ok": False, "reason": "MODE_NOT_DRY_RUN", "paths": ["$.mode"], "fp": fp}

    if payload.get("schema_version") != "sentinel_trade_intent.v1":
        return {"ok": False, "reason": "SCHEMA_VERSION_MISMATCH", "paths": ["$.schema_version"], "fp": fp}

    if payload.get("producer", {}).get("domain") != "sentinel":
        return {"ok": False, "reason": "PRODUCER_INVALID", "paths": ["$.producer.domain"], "fp": fp}

    schema = load_schema()
    try:
        jsonschema.Draft202012Validator(schema).validate(payload)
    except jsonschema.ValidationError as e:
        return {"ok": False, "reason": "SCHEMA_INVALID", "paths": [str(e.path)], "fp": fp}

    return {"ok": True, "reason": "PASS", "paths": [], "fp": fp}

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True)
    args = ap.parse_args()

    raw = Path(args.path).read_bytes()
    payload = json.loads(raw.decode())

    res = gate(payload, raw)
    out = {
        "gate_id": GATE_ID,
        "status": "PASS" if res["ok"] else "FAIL_CLOSED",
        "reason": res["reason"],
        "offending_paths": res["paths"],
        "payload_fingerprint": res["fp"]
    }
    print(json.dumps(out, ensure_ascii=False, indent=2))
    raise SystemExit(0 if res["ok"] else 2)

if __name__ == "__main__":
    main()
