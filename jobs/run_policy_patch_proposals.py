# jobs/run_policy_patch_proposals.py
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from typing import Any, Dict, Optional, List

from infra.api.deps import (
    get_policy_patch_repo,
    get_auto_proposal_receipt_repo,
    get_approval_queue,
    get_l3_learning,
)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _truthy(v: Any) -> bool:
    if v is True:
        return True
    if isinstance(v, (int, float)) and v > 0:
        return True
    if isinstance(v, str) and v.strip().lower() in ("true", "yes", "y", "1", "high"):
        return True
    return False


def _extract_high_risk_samples(
    samples: List[Dict[str, Any]],
    *,
    min_quality: float,
) -> List[Dict[str, Any]]:
    """
    Evidence rule (v2-alpha, current schema):
    - quality_score >= min_quality
    - human_confirmed == True (if field exists)
    - signals.high_risk is truthy
    """
    evidence: List[Dict[str, Any]] = []
    for s in samples:
        q = float(s.get("quality_score") or 0.0)
        if q < min_quality:
            continue

        if "human_confirmed" in s and not bool(s.get("human_confirmed")):
            continue

        sig = s.get("signals") or {}
        if _truthy(sig.get("high_risk")):
            evidence.append(s)

    return evidence


def run(
    *,
    channel: Optional[str],
    window_days: int,
    limit_samples: int,
    dry_run: bool,
    min_quality: float,
    min_evidence: int,
) -> Dict[str, Any]:
    """
    v2-alpha job:
    - read recent L3 learning samples
    - generate auto policy patch proposal(s)
    - write proposal artifact + receipt + approval enqueue (if queued)

    IMPORTANT:
    - Does not apply patches.
    - Does not execute actions.
    """
    l3 = get_l3_learning()
    proposals_repo = get_policy_patch_repo()
    receipts_repo = get_auto_proposal_receipt_repo()
    approvals = get_approval_queue()

    # repo compatibility: list_recent() (we added alias)
    samples = l3.list_recent(limit=limit_samples) if hasattr(l3, "list_recent") else []

    if channel:
        samples = [s for s in samples if (s.get("channel") == channel)]

    ts = _now_iso()
    receipt: Dict[str, Any] = {
        "receipt_id": f"apr_{ts}",
        "ts": ts,
        "auto_proposed_by": "learning_os_v2",
        "channel": channel or "any",
        "window_days": window_days,
        "input_sample_count": len(samples),
        "evidence_sample_count": 0,
        "result": "SKIPPED",
        "reason": None,
        "proposal_id": None,
    }

    if len(samples) == 0:
        receipt["reason"] = "no_input_samples"
        if not dry_run:
            receipts_repo.append(receipt)
        return {"ok": True, "receipt": receipt, "proposal": None}

    # --- Evidence extraction (current schema: signals.high_risk) ---
    evidence = _extract_high_risk_samples(samples, min_quality=min_quality)
    receipt["evidence_sample_count"] = len(evidence)

    if len(evidence) < int(min_evidence):
        receipt["reason"] = "insufficient_evidence_samples"
        if not dry_run:
            receipts_repo.append(receipt)
        return {"ok": True, "receipt": receipt, "proposal": None}

    # --- Patch proposal (alpha, schema-aligned) ---
    # Confirmed policy schema snippet:
    # {
    #   "thresholds": {
    #     "childcare": {
    #       "high_negative_child_emotion": 0.95,
    #       "stress_pattern_detected": 0.95
    #     }
    #   },
    #   "rules": [...],
    #   "version": 1
    # }
    #
    # Alpha stance: conservative tightening for stress_pattern_detected threshold.
    # (In beta, read current value from PolicyStore; alpha can use a stable baseline.)
    current_stress = 0.95
    new_stress = min(0.99, current_stress + 0.01)

    patch = [
        {
            "op": "replace",
            "path": "/thresholds/childcare/stress_pattern_detected",
            "value": new_stress,
        }
    ]

    # channel inference fallback
    eff_channel = channel or (evidence[0].get("channel") or "unknown")

    proposal = {
        "proposal_id": f"pp_{ts.replace(':','').replace('.','')}",
        "ts_created": ts,
        "window_days": window_days,
        "channel": eff_channel,

        # metrics (alpha)
        "sample_count": len(samples),
        "confirmed_count": sum(1 for s in evidence if bool(s.get("human_confirmed", True))),
        "false_alarm_rate": 0.0,  # unknown until outcomes accumulate
        "incident_rate": 0.0,     # unknown until outcomes accumulate

        "patch_type": "JSONPatch",
        "patch": patch,

        "rationale": (
            "Auto-proposed threshold adjustment based on LearningSample signals.high_risk evidence "
            f"(count={len(evidence)}). Proposed change: /thresholds/childcare/stress_pattern_detected "
            f"{current_stress} -> {new_stress}. Human approval required."
        ),

        "evidence_sample_ids": [s.get("sample_id") for s in evidence if s.get("sample_id")],
        "evidence_scene_ids": [s.get("scene_id") for s in evidence if s.get("scene_id")],
        "evidence_snapshot_ids": [s.get("snapshot_id") for s in evidence if s.get("snapshot_id")],
    }

    receipt["result"] = "QUEUED"
    receipt["proposal_id"] = proposal["proposal_id"]

    if not dry_run:
        proposals_repo.append(proposal)
        receipts_repo.append(receipt)
        approval_id = approvals.enqueue(proposal)
    else:
        approval_id = "dry_run"

    return {
        "ok": True,
        "receipt": receipt,
        "proposal": proposal,
        "approval_id": approval_id,
    }


def main() -> None:
    p = argparse.ArgumentParser(description="Run v2-alpha auto policy patch proposal job")
    p.add_argument("--channel", type=str, default="", help="childcare|fnb|trading or empty for any")
    p.add_argument("--window-days", type=int, default=7)
    p.add_argument("--limit-samples", type=int, default=200)
    p.add_argument("--min-quality", type=float, default=0.5)
    p.add_argument("--min-evidence", type=int, default=1)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    out = run(
        channel=args.channel.strip() or None,
        window_days=int(args.window_days),
        limit_samples=int(args.limit_samples),
        dry_run=bool(args.dry_run),
        min_quality=float(args.min_quality),
        min_evidence=int(args.min_evidence),
    )

    print(out)


if __name__ == "__main__":
    main()
