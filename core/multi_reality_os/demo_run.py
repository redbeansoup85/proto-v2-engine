# proto-v2-engine/multi_reality_os/demo_run.py

from datetime import datetime

from core.multi_reality_os.models.actor_profile import ActorProfile
from core.multi_reality_os.core.builder_scene import build_scene
from core.multi_reality_os.core.builder_perspective import build_perspective_layers
from core.multi_reality_os.core.engine_mesh import build_reality_mesh
from core.multi_reality_os.core.engine_cognitive_flow import generate_cognitive_flow
from core.multi_reality_os.core.engine_consensus import compute_consensus
from core.multi_reality_os.core.conflict_forecast_engine import compute_conflict_forecast

def run_demo():
    # 1) Scene 정의 (예: 세컨 매니저 퇴사 고민 씬)
    scene = build_scene(
        scene_id="demo:kana_second_manager",
        title="세컨 매니저 퇴사 고민",
        description="통합 매니저 퇴사 이후, 세컨 매니저에게 책임과 백키친 업무까지 전가되는 상황.",
        actors=["second_manager", "owner"],
        pressures={
            "staffing_risk": 0.8,
            "training_load": 0.7,
            "uncertainty": 0.6,
        },
        constraints={"time_to_handover": 0.5},
    )

    # 2) Actor Profile 설정
    actor_profiles = [
        ActorProfile(
            actor_id="second_manager",
            name="Second Manager",
            value_weights={"stability": 0.9, "workload": 0.8},
            risk_tolerance=0.3,
            change_aversion=0.8,
            time_horizon_pref="short",
        ),
        ActorProfile(
            actor_id="owner",
            name="Owner",
            value_weights={"store_stability": 0.9, "cost_control": 0.7},
            risk_tolerance=0.6,
            change_aversion=0.4,
            time_horizon_pref="mid",
        ),
    ]

    # 3) Perspective Layers 생성
    pls = build_perspective_layers(scene, actor_profiles)

    # 4) Reality Mesh 생성
    mesh = build_reality_mesh(scene, pls)

    # 5) Cognitive Flow Map 생성
    cfm = generate_cognitive_flow(scene, pls, mesh, timeline_length=5)

    # 6) Consensus 계산
    consensus = compute_consensus(mesh)

    # 7) Conflict Forecast 계산
    forecast = compute_conflict_forecast(mesh, cfm)

    # 8) 콘솔 출력 (간단 확인용)
    print("=== Scene ===")
    print(scene)

    print("\n=== Perspective Layers ===")
    for actor_id, pl in pls.items():
        print(f"[{actor_id}] ->", pl)

    print("\n=== Reality Mesh ===")
    print("global_conflict:", mesh.global_conflict)
    print("global_alignment:", mesh.global_alignment)
    print("collapse_risk:", mesh.collapse_risk)
    print("links:", mesh.links)

    print("\n=== Cognitive Flow (per Actor) ===")
    for actor_id, flow in cfm.actor_flows.items():
        print(f"\nActor: {actor_id}")
        for node in flow.nodes:
            print(
                f"  T{node.time_index} | anxiety={node.emotion.get('anxiety',0):.2f} "
                f"| tendency={node.decision_tendency}"
            )

    print("\n=== Consensus ===")
    print(consensus)

    print("\n=== Conflict Forecast ===")
    print("overall_risk:", forecast.overall_risk)
    print("timeline_profile:", forecast.timeline_profile)
    print("hotspots:")
    for h in forecast.hotspots:
        print(f"  T{h.time_index} - {h.actor_id} (score={h.conflict_score:.2f}) reason={h.reason}")


if __name__ == "__main__":
    run_demo()
