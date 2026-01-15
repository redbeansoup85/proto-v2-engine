# proto-v2-engine/multi_reality_os/core/engine_cognitive_flow.py

from typing import Dict, List

from ..models.scene_base import SceneBase
from ..models.perspective_layer import PerspectiveLayer
from ..models.reality_mesh import RealityMesh
from ..models.cognitive_node import CognitiveNode
from ..models.cognitive_flow import ActorCognitiveFlow, CognitiveFlowMap


def _build_event_line(scene: SceneBase, timeline_length: int) -> List[CognitiveNode]:
    """
    임시/단순 버전:
    - T0: 씬 시작 (description 사용)
    - T1~T(n-1): 간단한 placeholder 노드
    나중에 실제 event list를 Scene에 붙이면 이 로직만 교체하면 된다.
    """
    nodes: List[CognitiveNode] = []

    # T0: 씬 시작
    nodes.append(
        CognitiveNode(
            time_index=0,
            label="scene_start",
            thought=scene.description,
            emotion={},
            decision_tendency=None,
            decision_strength=0.0,
            significance=0.7,
        )
    )

    # 나머지 타임포인트는 기본 placeholder
    for t in range(1, timeline_length):
        nodes.append(
            CognitiveNode(
                time_index=t,
                label=f"T{t}",
                thought=f"Timeline point T{t} for scene {scene.scene_id}",
                emotion={},
                decision_tendency=None,
                decision_strength=0.0,
                significance=0.3,
            )
        )

    return nodes


def _infer_decision_tendency(pl: PerspectiveLayer) -> str:
    """
    PL의 scenario_projection 등을 바탕으로
    가장 강한 선택 경향성을 간단하게 추론.
    - 시나리오 이름에 quit/leave/escape가 들어가면 'avoid'
    - accept/stay/take가 들어가면 'approach'
    - 그 외는 'consider'
    """
    if not pl.scenario_projection:
        return "consider"

    best_scenario = max(pl.scenario_projection, key=pl.scenario_projection.get)

    lowered = best_scenario.lower()
    if any(key in lowered for key in ["quit", "leave", "escape"]):
        return "avoid"
    if any(key in lowered for key in ["accept", "stay", "take"]):
        return "approach"
    return "consider"


def _build_actor_flow_for_simple_timeline(
    actor_id: str,
    pl: PerspectiveLayer,
    timeline_length: int,
) -> ActorCognitiveFlow:
    """
    현재는 '시간에 따른 변화'를 정교하게 추적하지 않고,
    기본 감정 상태를 시간에 따라 약간씩 증폭시키는 심플 버전.
    - 나중에 Event / Society OS / Emotion OS와 연동하여
      실제 타임라인 변화 데이터를 반영하는 구조로 확장 가능.
    """
    nodes: List[CognitiveNode] = []

    # emotion source 우선순위: emotional_state > emotional_bias
    base_anxiety = pl.emotional_state.get("anxiety") if pl.emotional_state else None
    if base_anxiety is None:
        base_anxiety = pl.emotional_bias.get("anxiety", 0.0)

    base_anxiety = max(0.0, min(1.0, base_anxiety))

    decision_tendency = _infer_decision_tendency(pl)

    for t in range(timeline_length):
        # 예시: 시간이 지날수록 약간씩 압력이 쌓이는 '점진적 상승'
        scaled_anxiety = max(0.0, min(1.0, base_anxiety + 0.1 * t))

        node = CognitiveNode(
            time_index=t,
            label=f"{actor_id}_T{t}",
            thought=f"Actor {actor_id} cognition at T{t}",
            emotion={"anxiety": scaled_anxiety},
            decision_tendency=decision_tendency,
            decision_strength=scaled_anxiety,  # anxiety가 커질수록 선택 확신도도 증가한다고 가정
            significance=0.5 + 0.1 * t,
        )
        nodes.append(node)

    return ActorCognitiveFlow(actor_id=actor_id, nodes=nodes)


def generate_cognitive_flow(
    scene: SceneBase,
    pls: Dict[str, PerspectiveLayer],
    mesh: RealityMesh,
    timeline_length: int = 5,
) -> CognitiveFlowMap:
    """
    Scene + PL + Mesh에서 Cognitive Flow Map을 생성하는 엔진의 1차 버전.

    - Scene: 사건의 전체 설명 + 구조적 압력 정보
    - PLs: 각 Actor가 상황을 어떻게 인지/감정적으로 받아들이는지
    - Mesh: 전역 갈등/정렬 상태 (지금은 사용 빈도 낮지만, 앞으로 가중치로 반영 가능)

    반환:
    - CognitiveFlowMap: event_line + actor_flows가 포함된 전체 인지 흐름 맵
    """
    # 1) 사건 타임라인 생성
    event_line = _build_event_line(scene, timeline_length)

    # 2) 각 Actor별 Cognitive Flow 생성
    actor_flows: Dict[str, ActorCognitiveFlow] = {}
    for actor_id, pl in pls.items():
        actor_flows[actor_id] = _build_actor_flow_for_simple_timeline(
            actor_id=actor_id,
            pl=pl,
            timeline_length=timeline_length,
        )

    # 3) 통합 Cognitive Flow Map 반환
    return CognitiveFlowMap(
        scene_id=scene.scene_id,
        timeline_length=timeline_length,
        event_line=event_line,
        actor_flows=actor_flows,
    )
