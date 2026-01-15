import math
from typing import Dict, List

from .intervention_effects import apply_intervention_to_persona
from ..models.equilibrium_state import AgentState, EquilibriumStep, EquilibriumResult


MAX_STEPS = 30
EQUILIBRIUM_THRESHOLD = 0.005    # 변화량이 이 이하이면 안정으로 판단
STABILITY_WINDOW = 4             # n 스텝 연속 유지되면 안정점


def compute_equilibrium(scene, actors, intervention=None):
    """
    Multi-Agent Equilibrium Engine
    scene: SceneBase
    actors: dict of actor_id → ActorPersona
    intervention: optional intervention spec
    """

    # Step 1: persona deep copy + intervention 적용
    persona_map = {aid: actors[aid].copy() for aid in actors}

    if intervention:
        target = intervention["target_actor"]
        persona_map[target] = apply_intervention_to_persona(
            persona_map[target],
            intervention
        )

    # Step 2: 초기 상태 생성
    trajectory: List[EquilibriumStep] = []
    prev_conflict = None
    stable_counter = 0
    equilibrium_point = None

    for t in range(MAX_STEPS):

        agents_state = {}

        # 1) 각 Actor의 다음 상태 계산
        for aid, persona in persona_map.items():

            base_pressure = scene.structural_pressure

            # anxiety 모델
            anxiety = (
                base_pressure
                * (1 + persona.emotional_reactivity.anxiety_sensitivity)
                * (1 + persona.biases.catastrophizing)
                * (persona.stress_profile.baseline_stress
                   + t * persona.stress_profile.stress_accumulation_rate)
            )

            # alignment 증가/감소 모델
            alignment = max(
                0.0,
                min(
                    1.0,
                    persona.social_traits.cooperation
                    - persona.social_traits.conflict_avoidance * anxiety * 0.1
                )
            )

            # decision tendency
            if anxiety > persona.emotional_reactivity.overwhelm_threshold:
                decision = "avoid"
            elif alignment > 0.5:
                decision = "consider"
            else:
                decision = "neutral"

            agents_state[aid] = AgentState(
                anxiety=float(anxiety),
                decision=decision,
                alignment=float(alignment),
            )

        # 2) 집단 conflict + alignment 계산
        conflict = sum([s.anxiety for s in agents_state.values()]) / len(agents_state)
        align_avg = sum([s.alignment for s in agents_state.values()]) / len(agents_state)

        step = EquilibriumStep(
            t=t,
            agents=agents_state,
            global_conflict=conflict,
            alignment_avg=align_avg,
        )
        trajectory.append(step)

        # 3) 안정점 감지
        if prev_conflict is not None:
            delta = abs(conflict - prev_conflict)
            if delta < EQUILIBRIUM_THRESHOLD:
                stable_counter += 1
            else:
                stable_counter = 0

            if stable_counter >= STABILITY_WINDOW:
                equilibrium_point = {
                    "timestep": t,
                    "state": {
                        "global_conflict": conflict,
                        "alignment": align_avg,
                        "risk": "stable" if conflict < 0.4 else "elevated",
                    },
                }
                break

        prev_conflict = conflict

    # Step 3: 패턴 분류
    from .pattern_classifier import classify_pattern
    pattern_type = classify_pattern(trajectory)

    # Step 4: 개입 민감도 분석 추가
    sensitivity = compute_intervention_sensitivity(trajectory)

    return EquilibriumResult(
        trajectory=trajectory,
        equilibrium_point=equilibrium_point,
        pattern_type=pattern_type,
        intervention_sensitivity=sensitivity,
    )


# ---------------------------------------------------------
# 🔥 신규 추가: Intervention Sensitivity 계산 함수
# ---------------------------------------------------------
def compute_intervention_sensitivity(trajectory: List[EquilibriumStep]) -> Dict[str, float]:
    """
    개입 효과를 단순 모델링:
    - conflict의 감소 속도와 최종 감소량을 기반으로 개입 민감도를 산출
    """

    if not trajectory:
        return {
            "emotional_support": 0.0,
            "role_adjustment": 0.0,
            "cognitive_reframe": 0.0,
            "leader_dialogue": 0.0,
        }

    base = trajectory[0].global_conflict
    end = trajectory[-1].global_conflict

    # conflict 감소량
    improvement = max(0.0, base - end)

    # 민감도 모델 (0~1 사이로 자동 정규화)
    return {
        "emotional_support": round(improvement * 0.8, 3),
        "role_adjustment": round(improvement * 1.1, 3),
        "cognitive_reframe": round(improvement * 0.6, 3),
        "leader_dialogue": round(improvement * 0.9, 3),
    }
