from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

GATE_ID = "GATE-SENTINEL-INTENT-V1"
POLICY_PATH = Path("docs/governance/policies/POLICY-CONNECTOR-SENTINEL-OBSERVER-v1.yml")


def _canonical_json(obj: Any) -> bytes:
    return json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _fingerprint(payload: dict[str, Any]) -> str:
    return hashlib.sha256(_canonical_json(payload)).hexdigest()


def _load_policy() -> dict[str, Any]:
    data = yaml.safe_load(POLICY_PATH.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise RuntimeError("invalid policy shape")
    return data


def _deep_scan_forbidden_keys(obj: Any, forbidden: set[str], path: str = "$") -> list[str]:
    hits: list[str] = []
    if isinstance(obj, dict):
        for key, value in obj.items():
            next_path = f"{path}.{key}"
            if isinstance(key, str) and key.lower() in forbidden:
                hits.append(next_path)
            hits.extend(_deep_scan_forbidden_keys(value, forbidden, next_path))
    elif isinstance(obj, list):
        for idx, value in enumerate(obj):
            hits.extend(_deep_scan_forbidden_keys(value, forbidden, f"{path}[{idx}]"))
    return hits


def _get_path_value(obj: dict[str, Any], dotted: str) -> tuple[bool, Any]:
    cur: Any = obj
    for part in dotted.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return False, None
        cur = cur[part]
    return True, cur


def _parse_utc_timestamp(ts: str) -> datetime:
    norm = ts.replace("Z", "+00:00")
    parsed = datetime.fromisoformat(norm)
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def gate_payload(payload: dict[str, Any], policy: dict[str, Any]) -> dict[str, Any]:
    offending: list[str] = []
    warn_only = set(policy.get("warn_only", []))

    allow = policy.get("allow", {})
    allowed_domain = set((allow.get("producer", {}) or {}).get("domain", []))
    allowed_schema = set(allow.get("schema_version", []))
    allowed_mode = set(allow.get("mode", []))

    got_domain = ((payload.get("producer") or {}).get("domain"))
    if got_domain not in allowed_domain:
        offending.append("$.producer.domain")
    if payload.get("schema_version") not in allowed_schema:
        offending.append("$.schema_version")
    if payload.get("mode") not in allowed_mode:
        offending.append("$.mode")

    forbidden = {str(x).lower() for x in policy.get("forbidden_field_patterns", [])}
    offending.extend(_deep_scan_forbidden_keys(payload, forbidden))

    ts_cfg = policy.get("timestamp_drift", {}) or {}
    if ts_cfg.get("enabled", False):
        max_drift = int(ts_cfg.get("max_drift_seconds", 600))
        paths = ts_cfg.get("field_paths", [])
        now = datetime.now(timezone.utc)
        found_ts = False
        for path in paths:
            ok, val = _get_path_value(payload, path)
            if not ok:
                continue
            found_ts = True
            if not isinstance(val, str):
                offending.append(f"$.{path}")
                continue
            try:
                parsed = _parse_utc_timestamp(val)
            except Exception:
                offending.append(f"$.{path}")
                continue
            drift = abs((now - parsed).total_seconds())
            if drift > max_drift:
                if str(ts_cfg.get("on_violation", "FAIL_CLOSED")) == "WARN_ONLY":
                    # Explicit warn-only path; do not fail.
                    pass
                else:
                    offending.append(f"$.{path}")
        if not found_ts and "UNKNOWN_TIMESTAMP_FIELD" not in warn_only:
            offending.append("$.timestamp_drift.field_paths")

    status = "PASS" if not offending else "FAIL_CLOSED"
    reason = "PASS" if status == "PASS" else "POLICY_VIOLATION"
    return {
        "gate_id": policy.get("gate", {}).get("id", GATE_ID),
        "status": status,
        "reason": reason,
        "offending_paths": sorted(set(offending)),
        "payload_fingerprint": _fingerprint(payload),
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", required=True, help="Path to sentinel intent json")
    args = ap.parse_args()

    payload = json.loads(Path(args.path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        out = {
            "gate_id": GATE_ID,
            "status": "FAIL_CLOSED",
            "reason": "INVALID_PAYLOAD",
            "offending_paths": ["$"],
            "payload_fingerprint": hashlib.sha256(b"INVALID").hexdigest(),
        }
        print(json.dumps(out, ensure_ascii=False))
        return 2

    policy = _load_policy()
    out = gate_payload(payload, policy)
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["status"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
