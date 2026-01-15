from __future__ import annotations

from datetime import datetime, timezone
import uuid
from typing import List, Dict

from core.learning.contracts import LearningSample
from core.learning.proposals import PolicyPatchProposal


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _group_by_channel(samples: List[LearningSample]) -> Dict[str, List[LearningSample]]:
    m: Dict[str, List[LearningSample]] = {}
    for s in samples:
        m.setdefault(s.channel, []).append(s)
    return m


def generate_policy_patch_proposals(
    samples: List[LearningSample],
    window_days: int,
    min_confirmed: int = 5,
) -> List[PolicyPatchProposal]:
    confirmed = [s for s in samples if s.human_confirmed and s.outcome_label]
    by_ch = _group_by_channel(confirmed)

    proposals: List[PolicyPatchProposal] = []

    for ch, ss in by_ch.items():
        if len(ss) < min_confirmed:
            continue

        total = len(ss)
        false_alarms = sum(1 for s in ss if s.outcome_label == "false_alarm")
        incidents = sum(1 for s in ss if s.outcome_label in ("incident", "near_miss"))

        far = false_alarms / total if total else 0.0
        ir = incidents / total if total else 0.0

        # v0.1 conservative heuristic
        if ch == "childcare" and ir > 0.0:
            patch_type = "THRESHOLD_TUNE"
            patch = {"direction": "MORE_SENSITIVE", "notes": "Childcare incidents present; prioritize safety."}
            rationale = f"[{ch}] Incident rate {ir:.2f} detected in confirmed outcomes. Safety-first: increase sensitivity."
        elif ir >= 0.10:
            patch_type = "THRESHOLD_TUNE"
            patch = {"direction": "MORE_SENSITIVE", "notes": "Incidents observed in confirmed outcomes."}
            rationale = f"[{ch}] Incident rate {ir:.2f} suggests under-detection risk; suggest more sensitive thresholds."
        elif far >= 0.70 and ir == 0.0:
            patch_type = "THRESHOLD_TUNE"
            patch = {"direction": "LESS_SENSITIVE", "notes": "High false alarms with zero incidents (confirmed)."}
            rationale = f"[{ch}] False alarm rate {far:.2f} with zero incidents suggests over-sensitivity; suggest less sensitive thresholds."
        else:
            patch_type = "NO_CHANGE"
            patch = {"notes": "No strong signal for tuning under current confirmed sample distribution."}
            rationale = f"[{ch}] Confirmed outcomes do not justify threshold tuning."

        evidence_sample_ids = [s.sample_id for s in ss[:50]]
        evidence_scene_ids = list({s.scene_id for s in ss[:200]})
        evidence_snapshot_ids = [s.snapshot_id for s in ss if s.snapshot_id][:200]

        proposals.append(
            PolicyPatchProposal(
                proposal_id="pp_" + uuid.uuid4().hex,
                ts_created=_now_iso(),
                window_days=window_days,
                channel=ch,
                sample_count=total,
                confirmed_count=total,
                false_alarm_rate=far,
                incident_rate=ir,
                patch_type=patch_type,
                patch=patch,
                rationale=rationale,
                evidence_sample_ids=evidence_sample_ids,
                evidence_scene_ids=evidence_scene_ids,
                evidence_snapshot_ids=evidence_snapshot_ids,
            )
        )

    return proposals
