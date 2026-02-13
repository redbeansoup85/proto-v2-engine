import hashlib, json, os, time

AUDIT_PATH = os.getenv("AURALIS_AUDIT_PATH", "/app/logs/audit.jsonl")
GENESIS_PATH = os.getenv("AURALIS_GENESIS_PATH", "/app/../seal/GENESIS.yaml")

def _sha256(s: bytes) -> str:
    return hashlib.sha256(s).hexdigest()

def _genesis_hash() -> str:
    if not os.path.exists(GENESIS_PATH):
        return "MISSING_GENESIS"
    with open(GENESIS_PATH, "rb") as f:
        return _sha256(f.read())

def append_audit(event: dict) -> dict:
    os.makedirs(os.path.dirname(AUDIT_PATH), exist_ok=True)

    prev_hash = "GENESIS"
    if os.path.exists(AUDIT_PATH) and os.path.getsize(AUDIT_PATH) > 0:
        with open(AUDIT_PATH, "rb") as f:
            lines = f.read().splitlines()
            if lines:
                prev = json.loads(lines[-1].decode("utf-8"))
                prev_hash = prev["hash"]

    event = {
        "ts": event.get("ts", int(time.time())),
        "auralis_genesis_hash": _genesis_hash(),
        **event,
        "prev_hash": prev_hash,
    }
    payload = json.dumps(event, sort_keys=True, ensure_ascii=False).encode("utf-8")
    record = {**event, "hash": _sha256(payload)}

    with open(AUDIT_PATH, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return record
