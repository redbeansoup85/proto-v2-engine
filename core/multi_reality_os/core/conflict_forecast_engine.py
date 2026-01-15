# proto-v2-engine/multi_reality_os/core/conflict_forecast_engine.py

from typing import List

from ..models.reality_mesh import RealityMesh
from ..models.cognitive_flow import CognitiveFlowMap
from ..models.conflict_forecast import ConflictForecast, ConflictPoint


def compute_conflict_forecast(
    mesh: RealityMesh,
    cfm: CognitiveFlowMap,
) -> ConflictForecast:
    """
    Reality Mesh(전역 갈등/붕괴) + Cognitive Flow(Actor별 감정/인지 흐름)를 사용해서
    '앞으로 갈등이 터질 수 있는 지점'을 예측하는 심플 버전 엔진.

    1) 시간별 평균 anxiety 값을 timeline_profile로 계산
    2) anxiety > 0.7인 Actor/시간 조합을 hotspot으로 수집
    3) mesh.global_conflict / mesh.collapse_risk / 평균 anxiety를 종합하여 overall_risk 계산
    """

    timeline_len = cfm.timeline_length
    timeline_profile: List[float] = []
    hotspots: List[ConflictPoint] = []

    for t in range(timeline_len):
        anx_values = []

        for actor_id, flow in cfm.actor_flows.items():
            if t < len(flow.nodes):
                node = flow.nodes[t]
                anxiety = node.emotion.get("anxiety", 0.0)
                anx_values.append(anxiety)

                # 불안이 높은 지점은 잠정 Hotspot
                if anxiety > 0.7:
                    hotspots.append(
                        ConflictPoint(
                            time_index=t,
                            actor_id=actor_id,
                            conflict_score=anxiety,
                            reason="high_anxiety",
                        )
                    )

        if anx_values:
            timeline_profile.append(sum(anx_values) / len(anx_values))
        else:
            timeline_profile.append(0.0)

    # Mesh 전역 갈등/붕괴 정보
    base_conflict = mesh.global_conflict
    collapse_risk = mesh.collapse_risk

    # 시간 평균 anxiety 계산
    if timeline_profile:
        avg_anxiety = sum(timeline_profile) / len(timeline_profile)
    else:
        avg_anxiety = 0.0

    # overall_risk: 평균 anxiety + 전역 갈등 + 붕괴위험의 평균
    overall_risk = (avg_anxiety + base_conflict + collapse_risk) / 3.0
    overall_risk = max(0.0, min(1.0, overall_risk))

    # 점수 낮은 hotspot은 정리 (임계치 0.7)
    hotspots = [h for h in hotspots if h.conflict_score >= 0.7]

    return ConflictForecast(
        scene_id=cfm.scene_id,
        timeline_profile=timeline_profile,
        hotspots=hotspots,
        overall_risk=overall_risk,
    )
