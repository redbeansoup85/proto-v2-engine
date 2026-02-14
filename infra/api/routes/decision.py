# infra/api/routes/decision.py
from __future__ import annotations

from dataclasses import asdict
from datetime import datetime, timezone
import uuid

from fastapi import APIRouter, Depends

from core.contracts.policy import Channel
from core.contracts.scene import SceneContext, SceneStatus, SceneRef
from core.scene.context import make_context_key
from core.scene.aggregator import SceneRuntimeState, update_runtime_state, should_close
from core.learning.contracts import LearningSample  # ✅ B-2

from infra.api.schemas import DecisionIn, DecisionOut, PolicyDecisionOut, OrchestratorOut
from infra.api.deps import (
    get_l2,
    get_orchestrator,
    get_policy,
    get_scene_repo,
    get_scene_state_map,
    get_l3_learning,  # ✅ B-2
)
from tools.observe.observe_event import observe_event

router = APIRouter(prefix="/v1/decision", tags=["decision"])


@router.post("/ingest", response_model=DecisionOut)
def ingest(
    payload: DecisionIn,
    policy=Depends(get_policy),
    orch=Depends(get_orchestrator),
    l2=Depends(get_l2),
    scenes=Depends(get_scene_repo),
    scene_state_map=Depends(get_scene_state_map),
) -> DecisionOut:
    # 0) context key
    context_key = make_context_key(
        org_id=payload.meta.org_id,
        site_id=payload.meta.site_id,
        channel=payload.meta.channel,
        scene_id=payload.meta.scene_id,
    )

    context = SceneContext(
        org_id=payload.meta.org_id,
        site_id=payload.meta.site_id,
        channel=payload.meta.channel,
        context_key=context_key,
    )

    # 1) get or open active scene
    active = scenes.get_active_by_context(context_key)
    if active is None:
        active = scenes.open_new_scene(context=context, ts_start=payload.meta.window.start_ts)
    else:
        # promote OPEN -> ACTIVE on next event
        if active.status in (SceneStatus.OPEN, SceneStatus.IDLE):
            active = SceneRef(
                scene_id=active.scene_id,
                status=SceneStatus.ACTIVE,
                context=active.context,
                ts_start=active.ts_start,
                ts_end=None,
            )
            scenes.upsert_active(active)

    # attach scene_id into meta for snapshot + response
    payload_meta = payload.meta.model_copy(update={"scene_id": active.scene_id})

    observe_event(
        {
            "kind": "decision_ingest",
            "meta": {
                "org_id": payload_meta.org_id,
                "site_id": payload_meta.site_id,
                "channel": str(payload_meta.channel),
                "scene_id": active.scene_id,
                "context_key": context_key,
                "request_id": None,
                "source_path": "infra/api/routes/decision.py::ingest",
            },
            "preview": {
                "payload_keys": sorted(payload.model_dump().keys()),
                "signals_keys": sorted(payload.signals.keys()),
                "signals_count": len(payload.signals),
                "window_start_ts": payload_meta.window.start_ts,
                "window_end_ts": payload_meta.window.end_ts,
            },
        },
        channel=str(payload_meta.channel),
        source_path="infra/api/routes/decision.py::ingest",
        request_id=None,
    )

    # 2) Policy decision
    decision = policy.decide(channel=str(payload_meta.channel), signals=payload.signals)

    # 3) Orchestrator routing (execution-free)
    routing, recs, extra_codes = orch.route(channel=payload_meta.channel, severity=decision.severity)

    # 4) rationale codes (store as strings)
    rationale_codes = [c.value for c in decision.rationale_codes] + [c.value for c in extra_codes]

    # 5) runtime state update
    st = scene_state_map.get(active.scene_id) or SceneRuntimeState()
    st = update_runtime_state(st, decision, rationale_codes)
    scene_state_map[active.scene_id] = st

    # 6) memory snapshot placeholder (v0.1)
    # NOTE: channel enum vs str 혼재 방지: 여기서는 value/string로 통일
    ch_val = payload_meta.channel.value if hasattr(payload_meta.channel, "value") else str(payload_meta.channel)

    memory_snapshot = {
        "channel": ch_val,
        "accumulation_score": 0.0,
        "strike_count": 0,
        "cooldown_until_ts": None,
        "human_review_required": (payload_meta.channel == Channel.childcare),
        "last_decision": {"mode": decision.mode, "severity": decision.severity},
        "scene": {"scene_id": active.scene_id, "context_key": context_key, "status": active.status.value},
    }

    # 7) audit snapshot append-only
    snapshot = {
        "meta": payload_meta.model_dump(),
        "policy_decision": {
            "mode": decision.mode,
            "severity": decision.severity,
            "rationale_codes": rationale_codes,
        },
        "policy_memory_snapshot": memory_snapshot,
        "recommendations": [asdict(r) for r in recs],
        "orchestrator_routing": {
            "delivery_plan": routing.delivery_plan,
            "auto_action": routing.auto_action,
            "targets": list(routing.targets),
            "metadata": routing.metadata,
        },
        "scene": {
            "scene_id": active.scene_id,
            "context_key": context_key,
            "status": active.status.value,
        },
    }
    snapshot_id = l2.append_decision_snapshot(snapshot)
    snapshot["snapshot_id"] = snapshot_id

    # ✅ 7.5) B-2 Shadow Learning sample append (절대 흐름 방해 금지)
    try:
        l3 = get_l3_learning()
        sample = LearningSample(
            sample_id="ls_" + uuid.uuid4().hex,
            ts_created=datetime.now(timezone.utc).isoformat(),
            org_id=payload_meta.org_id,
            site_id=payload_meta.site_id,
            channel=ch_val,
            scene_id=active.scene_id,
            snapshot_id=snapshot_id,  # l2가 stamp해주면 들어오고, 아니면 None
            mode=decision.mode,
            severity=decision.severity,
            rationale_codes=rationale_codes,
            delivery_plan=routing.delivery_plan,
            signals=payload.signals,
            outcome_label=None,
            outcome_notes=None,
            human_confirmed=False,
            quality_score=1.0,
        )
        l3.append_sample(sample)
    except Exception:
        # Shadow learning은 실패해도 decision ingest를 절대 막지 않는다
        pass

    # 8) CLOSE if forced or conditions met
    force_close = bool(payload.signals.get("force_close", False))
    if force_close or should_close(st):
        peak_val = st.peak_severity.value if hasattr(st.peak_severity, "value") else str(st.peak_severity)

        summary_obj = {
            "scene_id": active.scene_id,
            "context": {
                "org_id": active.context.org_id,
                "site_id": active.context.site_id,
                "channel": (active.context.channel.value if hasattr(active.context.channel, "value") else str(active.context.channel)),
                "context_key": active.context.context_key,
            },
            "ts_start": active.ts_start,
            "ts_end": payload_meta.window.end_ts,
            "peak_severity": peak_val,
            "total_decisions": st.total_decisions,
            "key_rationale_codes": sorted(st.rationale_counter, key=st.rationale_counter.get, reverse=True)[:5],
            "delivery_types": [routing.delivery_plan],
            "human_interventions": [],
            "outcome_label": None,
        }

        # Persist summary via L2 repo helper (dict-based)
        if hasattr(l2, "append_scene_summary_dict"):
            l2.append_scene_summary_dict(summary_obj)

        # clear active + runtime
        scenes.clear_active(context_key)
        scene_state_map.pop(active.scene_id, None)

    # 9) API response
    return DecisionOut(
        meta=payload_meta,
        policy_decision=PolicyDecisionOut(
            mode=decision.mode,
            severity=decision.severity,
            rationale_codes=rationale_codes,
        ),
        policy_memory_snapshot=memory_snapshot,
        recommendations=[asdict(r) for r in recs],
        orchestrator_routing=OrchestratorOut(
            delivery_plan=routing.delivery_plan,
            auto_action=routing.auto_action,
        ),
    )
