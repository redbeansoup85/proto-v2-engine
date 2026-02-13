import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
IN_PATH = ROOT / "var" / "local_llm" / "dry_run_validated.json"
OUT_PATH = ROOT / "var" / "local_llm" / "gate_decision.json"

def main():
    d = json.loads(IN_PATH.read_text(encoding="utf-8"))

    # Minimal Gate rules for Meta 3.0 plumbing
    reason_codes = []
    decision = "APPROVE"

    if d.get("risk_level") == "HIGH":
        decision = "REJECT"
        reason_codes.append("RISK_HIGH")

    conf = float(d.get("confidence", 0.0))
    if conf < 0.55:
        decision = "REJECT"
        reason_codes.append("LOW_CONF")

    out = {
        "decision": decision,
        "reason_codes": reason_codes,
        "override_required": False,
        "source": "gate_min.v1"
    }

    OUT_PATH.write_text(json.dumps(out, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"OK: wrote {OUT_PATH}")

if __name__ == "__main__":
    main()
