from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from core.policy_store.store import PolicyStore, sha256_of_obj


IN_PATH_DEFAULT = "data/learning/policy_patch_proposals.jsonl"
OUT_PATH_DEFAULT = "logs/patch_proposals/proposals.jsonl"
POLICY_DIR_DEFAULT = "data/policies"


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def read_jsonl(path: str) -> List[Dict[str, Any]]:
    if not os.path.exists(path):
        raise FileNotFoundError(path)
    out = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def append_jsonl(path: str, rec: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False, sort_keys=True) + "\n")


def make_threshold_tune_patch_ops(channel: str, direction: str) -> List[Dict[str, Any]]:
    """
    Minimal mapping:
    - LESS_SENSITIVE: increase thresholds a bit (harder to trigger)
    - MORE_SENSITIVE: decrease thresholds a bit (easier to trigger)

    You can refine these later per-signal/per-policy.
    """
    # step size: conservative
    delta = 0.05
    if direction == "MORE_SENSITIVE":
        delta = -0.05

    # we only touch known keys that exist in our policy skeleton
    keys = [
        "high_negative_child_emotion",
        "stress_pattern_detected",
    ]

    ops = []
    for k in keys:
        ops.append(
            {
                "op": "replace",
                "path": f"/thresholds/{channel}/{k}",
                # NOTE: we don't know current value here; we will compute at runtime in a later version.
                # For MVP, we set a suggested target value relative to defaults.
                "value": None,
            }
        )
    # We'll fill 'value' after reading current policy snapshot in convert()
    return ops


def fill_values_from_policy(policy: Dict[str, Any], ops: List[Dict[str, Any]], channel: str, direction: str) -> List[Dict[str, Any]]:
    delta = 0.05
    if direction == "MORE_SENSITIVE":
        delta = -0.05

    filled = []
    for op in ops:
        if op["op"] != "replace":
            filled.append(op)
            continue
        path = op["path"]
        # path: /thresholds/<channel>/<key>
        parts = path.strip("/").split("/")
        key = parts[-1]
        cur = policy.get("thresholds", {}).get(channel, {}).get(key)
        if cur is None:
            # if missing, skip (safe)
            continue
        new_val = float(cur) + float(delta)
        # clamp 0..1
        new_val = max(0.0, min(1.0, new_val))
        filled.append({"op": "replace", "path": path, "value": round(new_val, 4)})
    return filled


def convert_one(raw: Dict[str, Any], policy_dir: str) -> Optional[Dict[str, Any]]:
    patch_type = raw.get("patch_type")
    if patch_type != "THRESHOLD_TUNE":
        return None

    channel = raw.get("channel") or "childcare"
    patch = raw.get("patch") or {}
    direction = patch.get("direction") or "LESS_SENSITIVE"

    store = PolicyStore(policy_dir)
    latest = store.latest()

    base_ops = make_threshold_tune_patch_ops(channel, direction)
    ops = fill_values_from_policy(latest.policy, base_ops, channel, direction)
    if not ops:
        return None

    proposal_id = raw.get("proposal_id")
    evidence = {
        "rationale": raw.get("rationale"),
        "patch_type": patch_type,
        "patch": patch,
        "evidence_sample_ids": raw.get("evidence_sample_ids"),
        "evidence_scene_ids": raw.get("evidence_scene_ids"),
        "evidence_snapshot_ids": raw.get("evidence_snapshot_ids"),
        "metrics": {
            "window_days": raw.get("window_days"),
            "sample_count": raw.get("sample_count"),
            "confirmed_count": raw.get("confirmed_count"),
            "false_alarm_rate": raw.get("false_alarm_rate"),
            "incident_rate": raw.get("incident_rate"),
        },
    }

    out = {
        "proposal_id": proposal_id,
        "ts_iso": raw.get("ts_created") or now_iso(),
        "policy_target_version": latest.version,
        "policy_target_sha256": latest.sha256,
        "artifact_hash": sha256_of_obj(raw),  # raw proposal hash
        "evidence": evidence,
        "patch_ops": ops,
    }
    return out


def main(in_path: str = IN_PATH_DEFAULT, out_path: str = OUT_PATH_DEFAULT, policy_dir: str = POLICY_DIR_DEFAULT) -> None:
    raws = read_jsonl(in_path)
    os.makedirs(os.path.dirname(out_path), exist_ok=True)

    # overwrite output each run (so it’s deterministic)
    if os.path.exists(out_path):
        os.remove(out_path)

    wrote = 0
    for r in raws:
        converted = convert_one(r, policy_dir)
        if converted is None:
            continue
        append_jsonl(out_path, converted)
        wrote += 1

    print(f"converted={wrote} -> {out_path}")


if __name__ == "__main__":
    main()
