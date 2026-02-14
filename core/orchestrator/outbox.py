from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict, List

from core.C_action.queue_consumer import _load_json, _save_json


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _now_iso() -> str:
    # CI determinism lock (optional)
    # Enable with: METAOS_CI_DETERMINISTIC_ORCH_OUTBOX=1
    if _truthy_env("METAOS_CI_DETERMINISTIC_ORCH_OUTBOX"):
        return "1970-01-01T00:00:00Z"
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _jsonable(obj: Any) -> Any:
    if is_dataclass(obj):
        return {k: _jsonable(v) for k, v in asdict(obj).items()}
    if isinstance(obj, Enum):
        return obj.value
    if isinstance(obj, dict):
        return {str(k): _jsonable(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_jsonable(x) for x in obj]
    if isinstance(obj, set):
        return sorted([_jsonable(x) for x in obj], key=lambda x: json.dumps(x, sort_keys=True, ensure_ascii=False))
    return obj


def _canonical_sha256(obj: Any) -> str:
    obj2 = _jsonable(obj)
    b = json.dumps(obj2, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(b).hexdigest()


def split_outbox_from_decision(decision_path: str, outbox_base_dir: str = "logs/orchestrator/outbox") -> List[str]:
    d = _load_json(decision_path)

    plan_id = d.get("plan_id") or "unknown"
    channel = d.get("channel") or "unknown"

    dec = d.get("decision") or {}
    deliveries = dec.get("deliveries") or []
    if not isinstance(deliveries, list):
        deliveries = [deliveries]

    # outbox index: stable ordering
    # deliveries는 router가 만든 순서가 의미가 있으므로 그대로 보존한다.
    out_paths: List[str] = []
    for i, delivery in enumerate(deliveries, 1):
        delivery_obj = _jsonable(delivery)

        out = {
            "schema": "orch_outbox_item.v1",
            "ts_iso": _now_iso(),
            "kind": "ORCH_OUTBOX_ITEM",
            "channel": channel,
            "plan_id": plan_id,
            "decision_sha256": d.get("decision_sha256"),
            "decision_ref": f"sha256:{d.get('decision_sha256')}",
            "routing_capsule_sha256": d.get("routing_capsule_sha256"),
            "index": i,
            "delivery": delivery_obj,
        }
        out["delivery_sha256"] = _canonical_sha256(out["delivery"])
        out["outbox_item_sha256"] = _canonical_sha256(
            {
                "decision_sha256": out.get("decision_sha256"),
                "index": out.get("index"),
                "delivery_sha256": out.get("delivery_sha256"),
            }
        )

        out_path = os.path.join(outbox_base_dir, channel, plan_id, f"delivery_{i:03d}.json")
        _save_json(out_path, out)
        out_paths.append(out_path)

    return out_paths
