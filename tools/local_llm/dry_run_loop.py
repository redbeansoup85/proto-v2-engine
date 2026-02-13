import json
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, Tuple


ROOT = Path(__file__).resolve().parents[2]
OUT_DIR = ROOT / "var" / "local_llm"
OUT_DIR.mkdir(parents=True, exist_ok=True)

LLAMA_MODEL = "llama3.1:70b"
MISTRAL_MODEL = "mistral:latest"


def ollama_run(model: str, prompt: str) -> str:
    p = subprocess.run(
        ["ollama", "run", model],
        input=prompt,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    out = (p.stdout or "").strip()
    if p.returncode != 0 and not out:
        raise RuntimeError(f"ollama failed: {p.stderr.strip()}")
    return out


def extract_json(text: str) -> Dict[str, Any]:
    s = text.find("{")
    e = text.rfind("}")
    if s == -1 or e == -1 or e <= s:
        raise ValueError("No JSON object found in model output")
    blob = text[s : e + 1]
    return json.loads(blob)


def normalize_constants(obj: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(obj)
    out["mode"] = "DRY_RUN"
    out["engine_version"] = "3.0"
    return out


def validate_dry_run(obj: Dict[str, Any]) -> Tuple[bool, str]:
    # Required keys
    req = ["intent", "confidence", "risk_level", "policy_refs", "mode", "engine_version"]
    for k in req:
        if k not in obj:
            return False, f"missing key: {k}"

    # No extra keys (strict)
    extra = sorted(set(obj.keys()) - set(req))
    if extra:
        return False, f"extra keys not allowed: {extra}"

    # intent
    if obj["intent"] not in ("LONG", "SHORT", "HOLD"):
        return False, f"intent invalid: {obj['intent']}"

    # confidence
    conf = obj["confidence"]
    if not isinstance(conf, (int, float)):
        return False, f"confidence must be number: {type(conf)}"
    if conf < 0.0 or conf > 1.0:
        return False, f"confidence out of range: {conf}"

    # risk_level
    if obj["risk_level"] not in ("LOW", "MEDIUM", "HIGH"):
        return False, f"risk_level invalid: {obj['risk_level']}"

    # policy_refs
    pr = obj["policy_refs"]
    if not isinstance(pr, list):
        return False, "policy_refs must be array"
    if not all(isinstance(x, str) for x in pr):
        return False, "policy_refs items must be strings"

    # constants
    if obj["mode"] != "DRY_RUN":
        return False, f"mode must be DRY_RUN: {obj['mode']}"
    if obj["engine_version"] != "3.0":
        return False, f"engine_version must be 3.0: {obj['engine_version']}"

    return True, ""


def make_prompt(snapshot: Dict[str, Any]) -> str:
    return (
        "You are Sentinel. Return ONE JSON object only. No markdown. No explanation.\n"
        "Keys: intent, confidence, risk_level, policy_refs, mode, engine_version.\n"
        "intent: LONG|SHORT|HOLD\n"
        "confidence: number 0.0..1.0\n"
        "risk_level: LOW|MEDIUM|HIGH\n"
        "policy_refs: array of strings\n"
        "mode: DRY_RUN\n"
        "engine_version: 3.0\n\n"
        f"SNAPSHOT:\n{json.dumps(snapshot, ensure_ascii=False)}\n"
    )


def make_repair_prompt(prev_text: str, err: str) -> str:
    return (
        "Fix the JSON to satisfy the required keys ONLY.\n"
        "Return ONE JSON object only. No markdown. No explanation.\n"
        "Required keys ONLY: intent, confidence, risk_level, policy_refs, mode, engine_version.\n"
        "mode must be DRY_RUN and engine_version must be 3.0.\n"
        f"Validation error: {err}\n"
        f"Previous output: {prev_text}\n"
    )


def main() -> int:
    if len(sys.argv) >= 2:
        snap_path = Path(sys.argv[1]).resolve()
        snapshot = json.loads(snap_path.read_text(encoding="utf-8"))
    else:
        snapshot = {
            "symbol": "BTCUSDT",
            "price": 69000.0,
            "funding": 0.0001,
            "open_interest": 123456789,
            "volume_15m": 9876543,
            "ts": "2026-02-13T16:00:00+11:00",
        }

    prompt = make_prompt(snapshot)
    raw = ollama_run(LLAMA_MODEL, prompt)

    gen_path = OUT_DIR / "dry_run_generated.txt"
    gen_path.write_text(raw, encoding="utf-8")

    obj = normalize_constants(extract_json(raw))
    ok, err = validate_dry_run(obj)

    attempt = 0
    while not ok and attempt < 2:
        attempt += 1
        repair_prompt = make_repair_prompt(raw, err)
        fixed_raw = ollama_run(MISTRAL_MODEL, repair_prompt)

        fix_path = OUT_DIR / ("dry_run_repaired.txt" if attempt == 1 else f"dry_run_repaired_{attempt}.txt")
        fix_path.write_text(fixed_raw, encoding="utf-8")

        raw = fixed_raw
        obj = normalize_constants(extract_json(raw))
        ok, err = validate_dry_run(obj)

    if not ok:
        raise RuntimeError(f"Validation still failed after repair: {err}")

    out_path = OUT_DIR / "dry_run_validated.json"
    out_path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    print("OK: DRY_RUN validated")
    print(f"- generated: {gen_path}")
    repaired = OUT_DIR / "dry_run_repaired.txt"
    if repaired.exists():
        print(f"- repaired:  {repaired}")
    print(f"- output:    {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
