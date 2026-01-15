from typing import Dict
from ..models.scene_base import SceneBase
from ..models.actor_profile import ActorPersona
from ..models.interpretation_card import InterpretationCard


def interpret_scene(scene: SceneBase, actors: Dict[str, ActorPersona]) -> InterpretationCard:
    """
    SceneBase 구조 + ActorPersona들의 성향을 기반으로
    'Scene Interpretation Card' 를 생성한다.
    """

    # 1) 구조적 압력 해석
    struct_msg = []
    p = scene.structural_pressure

    if p < 0.3:
        struct_msg.append("구조적 압력은 낮아 장기적으로 안정적인 씬입니다.")
    elif p < 0.6:
        struct_msg.append("중간 수준의 구조적 압력이 존재하며, 변화에 민감한 시기입니다.")
    else:
        struct_msg.append("구조적 압력이 매우 높아 갈등이 쉽게 발생하는 취약한 씬입니다.")

    if scene.constraints:
        if scene.constraints.get("time_to_handover", 1.0) < 0.5:
            struct_msg.append("시간 제약이 커서 의사결정 스트레스가 누적되는 환경입니다.")

    # 2) Actor 프로파일 분석
    actor_msgs = []
    for aid, actor in actors.items():
        m = []

        if actor.emotional_reactivity.anxiety_sensitivity > 0.7:
            m.append("불안 민감도가 높아 작은 변화에도 반응합니다.")

        if actor.social_traits.cooperation > 0.7:
            m.append("협력 성향이 높아 조정 가능성이 높습니다.")

        if actor.biases.catastrophizing > 0.6:
            m.append("과도한 부정적 예측 편향이 있어 리스크를 확대 해석할 수 있습니다.")

        if actor.change_aversion > 0.6:
            m.append("변화 회피 성향이 커서 새로운 역할 배치에 저항할 수 있습니다.")

        if not m:
            m.append("전반적으로 안정적인 대응 패턴을 보입니다.")

        actor_msgs.append(f"{aid}: " + " ".join(m))

    # 3) 관계적 흐름 요약
    if len(actors) == 2:
        # 두 명일 때는 특별히 관계성을 강조
        keys = list(actors.keys())
        a, b = actors[keys[0]], actors[keys[1]]

        relation_msg = []
        diff = abs(a.change_aversion - b.change_aversion)

        if diff > 0.4:
            relation_msg.append("두 Actor의 변화 수용도 차이가 커서 시선 충돌 가능성이 높습니다.")
        else:
            relation_msg.append("두 Actor는 비교적 비슷한 속도로 상황을 받아들입니다.")

    else:
        relation_msg = ["관계망 규모가 커져 상호작용 복잡성이 증가한 씬입니다."]

    # 4) 최종 InterpretationCard 생성
    return InterpretationCard(
        title=scene.title,
        structural_summary=" ".join(struct_msg),
        actor_summaries=actor_msgs,
        relation_summary=" ".join(relation_msg),
        risk_level=_compute_risk_level(scene, actors),
    )


def _compute_risk_level(scene: SceneBase, actors: Dict[str, ActorPersona]) -> str:
    """
    씬의 구조적 압력 + Actor 프로파일 기반으로 정성적 위험 레벨 부여.
    """

    pressure = scene.structural_pressure
    avg_anxiety = sum(
        actor.emotional_reactivity.anxiety_sensitivity
        for actor in actors.values()
    ) / len(actors)

    if pressure > 0.6 and avg_anxiety > 0.5:
        return "HIGH"

    if pressure > 0.4 or avg_anxiety > 0.5:
        return "MEDIUM"

    return "LOW"
