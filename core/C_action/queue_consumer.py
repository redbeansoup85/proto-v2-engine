# core/C_action/queue_consumer.py
from __future__ import annotations

import glob
import hashlib
import json
import os
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.C_action.contracts import DeliveryPlan
from core.C_action.execution_gate import enforce_execution_gate_for_queue_item  # ✅ Gate 2 enforcement


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _now_iso() -> str:
    # CI determinism lock (optional)
    # Enable with: METAOS_CI_DETERMINISTIC_CONSUMER=1
    if os.getenv("METAOS_CI_DETERMINISTIC_CONSUMER", "").strip().lower() in {"1", "true", "yes", "y", "on"}:
        return "1970-01-01T00:00:00Z"
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sha8(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()[:8]


def _stable_idempotency_seed(queue_item_path: str) -> str:
    """
    Deterministic idempotency seed across runs.

    DO NOT hash full queue_item_path because CI uses temp dirs like:
      /tmp/metaos_ci_local.<RAND>/...
    which would change every run and break replay stability (LOCK9).

    Preferred stable seed:
      - queue filename stem, e.g. dp_3ca5c80427e7097f from dp_3ca5c80427e7097f.json
    """
    try:
        return Path(queue_item_path).stem  # stable across temp roots
    except Exception:
        # ultra-safe fallback (still avoids temp root influence)
        return os.path.splitext(os.path.basename(queue_item_path))[0]


def _safe_id(plan_id: Optional[str], queue_item_path: str) -> str:
    """
    Ensure processed filename never collides:
    - if plan_id exists and not "unknown": use it
    - else derive from queue filename + mtime
    """
    pid = (plan_id or "").strip()
    if pid and pid.lower() != "unknown":
        return pid
    st = os.stat(queue_item_path)
    basis = f"{os.path.basename(queue_item_path)}:{int(st.st_mtime)}:{st.st_size}"
    return f"unknown_{_sha8(basis)}"


def _plan_from_queue_item(q: Dict[str, Any]) -> DeliveryPlan:
    plan_path = q.get("plan_path")
    if isinstance(plan_path, str) and os.path.exists(plan_path):
        d = _load_json(plan_path)
        return DeliveryPlan(**d)

    return DeliveryPlan(
        plan_id=q.get("plan_id"),
        proposal_id=q.get("proposal_id"),
        ts_iso=q.get("ts_iso"),
        channel=q.get("channel"),
        policy_version=q.get("policy_version"),
        policy_sha256=q.get("policy_sha256"),
        noop_apply=bool(q.get("noop_apply")),
        warnings=q.get("warnings") or [],
        approvers_used=q.get("approvers_used") or [],
        receipt_path=q.get("receipt_path"),
        evidence_scene_ids=q.get("evidence_scene_ids") or [],
        evidence_sample_ids=q.get("evidence_sample_ids") or [],
        evidence_snapshot_ids=q.get("evidence_snapshot_ids") or [],
    )


def consume_one(queue_item_path: str, base_dir: str = "logs/queues") -> str:
    """
    Consume a pending queue item:
      - emit processed artifact:
        logs/queues/<channel>/processed/<safe_plan_id>.json
      - does NOT execute any external actions (read-only)
    Returns processed artifact path.
    """
    q = _load_json(queue_item_path)

    # 🔒 Gate 2: Execution Authorization enforcement (execution-class channels only)
    # If channel is in EXECUTION_CHANNELS, q must include a valid execution_request_path
    enforce_execution_gate_for_queue_item(q)

    plan = _plan_from_queue_item(q)

    channel = (plan.channel or q.get("channel") or "unknown")
    safe_plan_id = _safe_id(plan.plan_id or q.get("plan_id"), queue_item_path)

    processed_path = os.path.join(base_dir, channel, "processed", f"{safe_plan_id}.json")

    processed = dict(q)
    processed.update(
        {
            "status": "PROCESSED",
            "processed_ts_iso": _now_iso(),
            "processor": "queue_consumer",
            "action_executed": False,
            # 전달/처리 결과를 명시적으로 남김(실행 없음)
            "delivery_status": {
                "mode": "ARTIFACT_ONLY",
                "executed": False,
                "forwarded_to_orchestrator": False,
                "forward_payload_path": None,
                "notes": [],
            },
            "plan": asdict(plan),
            # ✅ Deterministic across runs: dp_id seed (filename stem), not temp path
            "idempotency_key": _sha8(_stable_idempotency_seed(queue_item_path)),
        }
    )

    _save_json(processed_path, processed)

    # best-effort: remove original pending item to avoid re-processing
    try:
        os.remove(queue_item_path)
    except Exception:
        # pending이 남아도 processed가 이미 있으므로 재처리 위험 낮음
        pass

    return processed_path


def consume_pending(channel: Optional[str] = None, limit: int = 50, base_dir: str = "logs/queues") -> List[str]:
    if channel:
        pattern = os.path.join(base_dir, channel, "pending", "*.json")
    else:
        pattern = os.path.join(base_dir, "*", "pending", "*.json")

    paths = sorted(glob.glob(pattern), key=os.path.getmtime)[: max(0, int(limit))]
    out: List[str] = []
    for p in paths:
        out.append(consume_one(p, base_dir=base_dir))
    return out
