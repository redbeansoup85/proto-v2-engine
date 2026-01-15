from typing import Dict, Any, List


class InterpretationEngine:

    @staticmethod
    def build_scene_overview(structural_pressures: Dict[str, float]) -> str:
        parts = []

        if structural_pressures.get("staffing_risk", 0) > 0.7:
            parts.append("역할 과부하와 인력 부족이 핵심 압력으로 작동하고 있으며")

        if structural_pressures.get("uncertainty", 0) > 0.6:
            parts.append("미래 불확실성이 인지적 긴장을 높이고 있고")

        if structural_pressures.get("training_load", 0) > 0.6:
            parts.append("훈련 부담이 구조적 제약을 만들고 있습니다.")

        if not parts:
            return "이 씬은 중간 수준의 구조적 압력 속에서 여러 Actor들의 인지가 서로 상호작용하는 상황입니다."

        return " ".join(parts)

    @staticmethod
    def extract_key_meanings(meaning_graph: Dict[str, float]) -> List[Dict[str, Any]]:
        sorted_items = sorted(
            meaning_graph.items(), key=lambda x: x[1], reverse=True
        )
        top = sorted_items[:4]

        enriched = []
        for node, score in top:
            reason = InterpretationEngine.describe_meaning(node)
            enriched.append({"node": node, "intensity": score, "reason": reason})

        return enriched

    @staticmethod
    def describe_meaning(node: str) -> str:
        mapping = {
            "unfair_burden": "책임이 비대칭적으로 전가된다고 느끼는 의미",
            "identity_threat": "역할 변화가 자아 정체성과 충돌하는 의미",
            "system_risk": "운영 유지 실패에 대한 위협으로 해석되는 의미",
            "left_alone": "지원 없이 과업이 주어졌다고 느끼는 의미",
        }
        return mapping.get(node, "상황 해석에 중요한 의미 노드")

    @staticmethod
    def build_actor_perspective(actor_meanings: Dict[str, Dict[str, float]],
                                cognitive_flow: Dict[str, Any]) -> Dict[str, str]:

        result = {}

        for actor_id, meanings in actor_meanings.items():
            strongest = max(meanings.items(), key=lambda x: x[1])[0]
            emotion_curve = [n["emotion"]["anxiety"] for n in cognitive_flow[actor_id]["nodes"]]
            trend = "상승" if emotion_curve[-1] > emotion_curve[0] else "안정"

            if strongest == "unfair_burden":
                summary = (
                    f"{actor_id}는 책임 증가를 '부당함'으로 해석하고 있으며, "
                    f"감정 곡선이 {trend}하고 있습니다."
                )
            elif strongest == "identity_threat":
                summary = (
                    f"{actor_id}는 역할 변화가 정체성에 압박을 준다고 느끼고 있으며, "
                    f"감정 곡선이 {trend} 중입니다."
                )
            elif strongest == "system_risk":
                summary = (
                    f"{actor_id}는 상황을 시스템 유지 관점에서 해석하고 있으며 "
                    f"문제를 해결하려는 경향이 강화되고 있습니다."
                )
            else:
                summary = (
                    f"{actor_id}는 여러 의미를 복합적으로 해석하며 "
                    f"상황 변화를 주의 깊게 관찰하고 있습니다."
                )

            result[actor_id] = summary

        return result

    @staticmethod
    def explain_conflict(conflict_forecast: Dict[str, Any]) -> str:
        hotspots = conflict_forecast.get("hotspots", [])

        if not hotspots:
            return "이 씬에서는 두 Actor 간의 갈등이 뚜렷한 Hotspot으로 나타나지 않습니다."

        strongest = max(hotspots, key=lambda h: h["conflict_score"])
        reason = strongest.get("reason", "")

        return (
            f"T{strongest['time_index']} 시점에서 갈등이 급격히 증가합니다. "
            f"핵심 원인은 '{reason}' 때문으로 보입니다."
        )

    @staticmethod
    def describe_emotional_dynamics(cognitive_flow: Dict[str, Any]) -> str:
        parts = []
        for actor, flow in cognitive_flow.items():
            start = flow["nodes"][0]["emotion"]["anxiety"]
            end = flow["nodes"][-1]["emotion"]["anxiety"]
            dir = "상승" if end > start else "감소"
            parts.append(f"{actor}의 anxiety는 {start:.2f} → {end:.2f} ({dir})")

        return " / ".join(parts)

    @staticmethod
    def build_hotspot_summary(conflict_forecast: Dict[str, Any]) -> List[str]:
        hotspots = conflict_forecast.get("hotspots", [])
        results = []

        for h in hotspots:
            results.append(
                f"T{h['time_index']} – {h['actors']} / score={h['conflict_score']:.2f} / {h['reason']}"
            )

        return results

    @staticmethod
    def infer_root_cause(meaning_graph: Dict[str, float]) -> str:
        top = max(meaning_graph.items(), key=lambda x: x[1])[0]

        if top == "unfair_burden":
            return "핵심 원인은 '부당함'에 대한 인지적 해석이 강하게 작동한 것입니다."
        if top == "identity_threat":
            return "핵심 원인은 '정체성 위협'이 갈등을 증폭시키는 방향으로 작동한 것입니다."
        if top == "system_risk":
            return "핵심 원인은 '운영 리스크' 관점의 해석이 중심에 있기 때문입니다."

        return "핵심 갈등 원인은 의미 충돌과 감정 증가의 상호 강화입니다."

    @staticmethod
    def build_resolution_path(root: str) -> str:
        if "부당함" in root:
            return "역할 배분의 배경과 기간을 명확히 설명하고 지원 자원을 제공하면 갈등이 완화될 수 있습니다."
        if "정체성" in root:
            return "역할 변경이 일시적임을 명시하고 자율성을 보장하면 안정화됩니다."
        if "리스크" in root:
            return "운영 압박을 공유하되 감정적 안전 신호를 함께 제공하는 것이 필요합니다."

        return "맥락 공유, 감정 인정, 지원 자원 명확화가 해결의 핵심 경로입니다."

    @staticmethod
    def extract_intervention_points(conflict_forecast: Dict[str, Any]) -> List[str]:
        points = []

        for h in conflict_forecast.get("hotspots", []):
            t = h["time_index"]
            points.append(f"T{t} 직전: {h['reason']} 완화介入 필요")

        return points

    @staticmethod
    def build_interpretation_card(
        scene: Dict[str, Any],
        meaning_graph: Dict[str, float],
        actor_meanings: Dict[str, Dict[str, float]],
        cognitive_flow: Dict[str, Any],
        conflict_forecast: Dict[str, Any],
    ) -> Dict[str, Any]:

        overview = InterpretationEngine.build_scene_overview(scene["structural_pressures"])
        key_meanings = InterpretationEngine.extract_key_meanings(meaning_graph)
        perspectives = InterpretationEngine.build_actor_perspective(actor_meanings, cognitive_flow)
        conflict_explain = InterpretationEngine.explain_conflict(conflict_forecast)
        emotional_dynamics = InterpretationEngine.describe_emotional_dynamics(cognitive_flow)
        hotspots = InterpretationEngine.build_hotspot_summary(conflict_forecast)
        root = InterpretationEngine.infer_root_cause(meaning_graph)
        resolution = InterpretationEngine.build_resolution_path(root)
        interventions = InterpretationEngine.extract_intervention_points(conflict_forecast)

        return {
            "scene_overview": overview,
            "key_meanings": key_meanings,
            "actor_perspectives": perspectives,
            "conflict_explanation": conflict_explain,
            "emotional_dynamics": emotional_dynamics,
            "timeline_hotspots": hotspots,
            "root_cause": root,
            "resolution_path": resolution,
            "intervention_points": interventions,
        }
