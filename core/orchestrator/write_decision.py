from __future__ import annotations

import hashlib
import json
import os
import time
from dataclasses import asdict, is_dataclass
from enum import Enum
from typing import Any, Dict

from core.C_action.queue_consumer import _load_json, _save_json
from core.orchestrator.routing.recommendation_router import RecommendationRouter


def _truthy_env(name: str) -> bool:
    return os.getenv(name, "").strip().lower() in {"1", "true", "yes", "y", "on"}


def _now_iso() -> str:
    # CI determinism lock (optional)
    # Enable with: METAOS_CI_DETERMINISTIC_ORCH_DECISION=1
    if _truthy_env("METAOS_CI_DETERMINISTIC_ORCH_DECISION"):
        return "1970-01-01T00:00:00Z"
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())



def _jsonable(obj: Any) -> Any:
    """Convert dataclasses/enums/tuples to JSON-serializable structures (deterministic)."""
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


def build_orch_decision_from_inbox(inbox_path: str) -> Dict[str, Any]:
    inbox = _load_json(inbox_path)

    plan = inbox.get("plan") or {}
    channel = inbox.get("channel") or "unknown"
    plan_id = plan.get("plan_id") or "unknown"

    # recs는 list[dict] 가정 (orch_payload이 plan 자체를 넣으므로, recs는 meta에서 들어오는 형태를 우선 지원)
    # meta.recommendations가 없으면 빈 리스트
    meta = inbox.get("meta") or {}
    recs = meta.get("recommendations") or inbox.get("recommendations") or []
    if not isinstance(recs, list):
        recs = [recs]

    severity = (meta.get("severity") or inbox.get("severity") or "low")
    decision_mode = (meta.get("decision_mode") or inbox.get("decision_mode") or "")

    router = RecommendationRouter()
    decision = router.route(
        channel=str(channel),
        severity=str(severity),
        decision_mode=str(decision_mode),
        recs=recs,  # type: ignore[arg-type]
        meta={"plan_id": plan_id, "inbox_path": inbox_path},
    )

    # 결정 아티팩트(SSOT)
    out = {
        "schema": "orch_decision.v1",
        "ts_iso": _now_iso(),
        "kind": "ORCH_DECISION",
        "channel": channel,
        "plan_id": plan_id,
        "inbox_path": inbox_path,
        "inbox_sha256": _canonical_sha256(inbox),
        "decision": _jsonable(decision),
    }
    out["decision_sha256"] = _canonical_sha256(out["decision"])
    out["routing_capsule_sha256"] = _canonical_sha256({
        "inbox_sha256": out.get("inbox_sha256"),
        "decision_sha256": out.get("decision_sha256"),
    })
    return out


def write_orch_decision(inbox_path: str, out_base_dir: str = "logs/orchestrator/decisions") -> str:
    obj = build_orch_decision_from_inbox(inbox_path)
    ch = obj.get("channel") or "unknown"
    plan_id = obj.get("plan_id") or "unknown"
    out_path = os.path.join(out_base_dir, ch, f"{plan_id}.json")
    _save_json(out_path, obj)
    return out_path
