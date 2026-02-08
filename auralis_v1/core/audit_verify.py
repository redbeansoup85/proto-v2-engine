import hashlib, json, os, sys

AUDIT = os.getenv("AURALIS_AUDIT_PATH", "/app/logs/audit.jsonl")
GENESIS = os.getenv("AURALIS_GENESIS_PATH", "/app/../seal/GENESIS.yaml")

def sha(b): return hashlib.sha256(b).hexdigest()

if not os.path.exists(AUDIT) or os.path.getsize(AUDIT) == 0:
    sys.exit(0)

g = sha(open(GENESIS,"rb").read()) if os.path.exists(GENESIS) else None
prev = "GENESIS"

for line in open(AUDIT):
    r = json.loads(line)
    if r["prev_hash"] != prev: sys.exit(1)
    h = r["hash"]
    x = dict(r); x.pop("hash")
    if sha(json.dumps(x,sort_keys=True).encode()) != h: sys.exit(1)
    if g and r["auralis_genesis_hash"] != g: sys.exit(1)
    prev = h
