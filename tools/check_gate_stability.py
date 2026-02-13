#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from typing import Any, Dict, Tuple


def _read_text(path: str) -> str:
    with open(path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()


def _extract_replay_result(text: str) -> Dict[str, Any]:
    marker = "REPLAY_RESULT:"
    idx = text.rfind(marker)
    if idx < 0:
        raise ValueError("NO REPLAY_RESULT")

    tail = text[idx + len(marker):].strip()

    start = tail.find("{")
    if start < 0:
        raise ValueError("REPLAY_RESULT found but no JSON object start")

    s = tail[start:]
    depth = 0
    end = None
    for i, ch in enumerate(s):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break

    if end is None:
        raise ValueError("REPLAY_RESULT JSON appears truncated (brace mismatch)")

    return json.loads(s[:end])


def _loose_key(rr: Dict[str, Any]) -> Tuple[Any, Any, Any]:
    dry = rr.get("dry_run") or {}
    gate = rr.get("gate") or {}
    return (dry.get("intent"), dry.get("risk_level"), gate.get("decision"))


def _strict_gate_capsule(rr: Dict[str, Any]) -> Dict[str, Any]:
    gate = rr.get("gate") or {}

    reason_codes = gate.get("reason_codes") or []
    if isinstance(reason_codes, list):
        reason_codes_sorted = sorted([str(x) for x in reason_codes])
    else:
        reason_codes_sorted = [str(reason_codes)]

    return {
        "decision": gate.get("decision"),
        "override_required": gate.get("override_required"),
        "policy_id": gate.get("policy_id"),
        "policy_version": gate.get("policy_version"),
        "reason_codes_sorted": reason_codes_sorted,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("a_path")
    ap.add_argument("b_path")
    ap.add_argument(
        "--strict",
        action="store_true",
        help="Compare ONLY the gate capsule (decision/policy_id/version/reason_codes/override_required).",
    )
    args = ap.parse_args()

    a_txt = _read_text(args.a_path)
    b_txt = _read_text(args.b_path)

    try:
        a_rr = _extract_replay_result(a_txt)
    except Exception:
        print(f"NO REPLAY_RESULT in {args.a_path}")
        return 2

    try:
        b_rr = _extract_replay_result(b_txt)
    except Exception:
        print(f"NO REPLAY_RESULT in {args.b_path}")
        return 2

    if not args.strict:
        a = _loose_key(a_rr)
        b = _loose_key(b_rr)
        print("A:", a)
        print("B:", b)
        if a == b:
            print("OK_GATE_STABLE")
            return 0
        print("ERR_GATE_UNSTABLE")
        return 3

    a = _strict_gate_capsule(a_rr)
    b = _strict_gate_capsule(b_rr)

    print("A(strict):", json.dumps(a, ensure_ascii=False, sort_keys=True))
    print("B(strict):", json.dumps(b, ensure_ascii=False, sort_keys=True))

    if a == b:
        print("OK_GATE_STABLE_STRICT")
        return 0

    for k in sorted(set(a.keys()) | set(b.keys())):
        if a.get(k) != b.get(k):
            print(f"DIFF {k}: A={a.get(k)!r} B={b.get(k)!r}")
    print("ERR_GATE_UNSTABLE_STRICT")
    return 4


if __name__ == "__main__":
    raise SystemExit(main())
