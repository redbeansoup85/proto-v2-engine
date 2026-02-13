import json
import uuid
from pathlib import Path
from datetime import datetime, timezone

ROOT = Path(__file__).resolve().parents[2]
DRY = ROOT / "var/local_llm/dry_run_validated.json"
OUT = ROOT / "var/local_llm/normalized_input.json"

def now_iso():
    return datetime.now(timezone.utc).isoformat()

def main():
    dry = json.loads(DRY.read_text(encoding="utf-8"))
    # In v1, we map dry_run fields directly into features.
    doc = {
        "input_id": str(uuid.uuid4()),
        "domain": "SENTINEL",
        "ts": now_iso(),
        "features": {
            "intent": dry.get("intent"),
            "confidence": dry.get("confidence"),
            "risk_level": dry.get("risk_level")
        }
    }
    OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=2), encoding="utf-8")
    print("OK:", OUT)

if __name__ == "__main__":
    main()
