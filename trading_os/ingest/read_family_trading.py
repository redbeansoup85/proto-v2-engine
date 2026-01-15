# trading_os/ingest/read_family_trading.py

from pathlib import Path
from datetime import datetime
import json

VAULT_ROOT = Path("trading_os/vault")

def load_session_log(path: Path) -> dict:
    with open(path, "r") as f:
        return json.load(f)

def write_vault(subdir: str, session_id: str, payload: dict):
    out_dir = VAULT_ROOT / subdir / session_id
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    out_file = out_dir / f"{ts}.json"

    with open(out_file, "w") as f:
        json.dump(payload, f, indent=2)

def ingest_family_trading_log(path: Path):
    log = load_session_log(path)

    session_id = log["meta"]["session_id"]

    # 1️⃣ manifests
    write_vault("manifests", session_id, log["meta"])

    # 2️⃣ contexts (관측)
    write_vault("contexts", session_id, log["observation"])

    # 3️⃣ exceptions
    if log.get("exceptions"):
        write_vault("exceptions", session_id, log["exceptions"])

    # 4️⃣ exec (판단)
    if log.get("judgment"):
        write_vault("exec", session_id, log["judgment"])

    # 5️⃣ executions (체결)
    if log.get("execution", {}).get("executed"):
        write_vault("executions", session_id, log["execution"])

    # 6️⃣ outcomes
    if log.get("outcome"):
        write_vault("outcomes", session_id, log["outcome"])

    # 7️⃣ learning
    if log.get("review"):
        write_vault("learning", session_id, log["review"])

    return session_id
