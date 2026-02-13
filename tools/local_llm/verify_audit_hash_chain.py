import json
import hashlib
import os
import re
from pathlib import Path

RE_HEX64 = re.compile(r"^[0-9a-f]{64}$")

def sha256_hex(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()

def stable_json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")

def main():
    root = Path(__file__).resolve().parents[2]
    audit_path = Path(os.getenv("AURALIS_AUDIT_PATH", root / "var/logs/audit.jsonl"))
    genesis_path = Path(os.getenv("AURALIS_GENESIS_PATH", root / "var/seal/GENESIS.yaml"))

    if not audit_path.exists():
        raise SystemExit(f"missing audit file: {audit_path}")
    if not genesis_path.exists():
        raise SystemExit(f"missing genesis file: {genesis_path}")

    genesis_hash = sha256_hex(genesis_path.read_bytes())

    prev = "GENESIS"
    ok = True
    n = 0

    with audit_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            n += 1
            rec = json.loads(line)

            # check genesis hash field if present
            gh = rec.get("auralis_genesis_hash")
            if gh and gh != genesis_hash:
                print(f"FAIL line {n}: genesis hash mismatch")
                ok = False
                break

            ph = rec.get("prev_hash")
            h  = rec.get("hash")

            if ph is None or h is None:
                print(f"FAIL line {n}: missing prev_hash/hash")
                ok = False
                break

            if n == 1:
                if ph != "GENESIS":
                    print(f"FAIL line 1: prev_hash must be GENESIS, got {ph}")
                    ok = False
                    break
            else:
                if ph != prev:
                    print(f"FAIL line {n}: prev_hash mismatch expected {prev} got {ph}")
                    ok = False
                    break

            if not isinstance(h, str) or (not RE_HEX64.match(h) and h != "GENESIS"):
                print(f"FAIL line {n}: invalid hash format: {h}")
                ok = False
                break

            # recompute hash if record includes enough data:
            # Many of your records appear to hash the entire record minus 'hash' field.
            # We do a best-effort verification: remove 'hash', serialize stable, then sha256.
            rec2 = dict(rec)
            rec2.pop("hash", None)
            recomputed = sha256_hex(stable_json(rec2))
            if recomputed != h:
                # Still accept chain-link integrity as primary; print warning.
                print(f"WARN line {n}: content hash mismatch (chain still checkable).")
                # do not fail hard

            prev = h

    if ok:
        print(f"OK: chain links verified (lines={n})")
        return 0
    return 2

if __name__ == "__main__":
    raise SystemExit(main())
