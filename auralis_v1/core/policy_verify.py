import hashlib, yaml, sys, os

GENESIS = os.getenv("AURALIS_GENESIS_PATH", "/app/../seal/GENESIS.yaml")
LOCK4   = os.getenv("LOCK4_POLICY_PATH", "/app/policies/LOCK4.yaml")

def sha(p): return hashlib.sha256(open(p,"rb").read()).hexdigest()

g = yaml.safe_load(open(GENESIS))
if sha(LOCK4) != g["auralis_genesis"]["lock_constitution"]["hash_sha256"]:
    sys.exit(1)
