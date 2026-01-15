def classify_pattern(trajectory):
    values = [step.global_conflict for step in trajectory]

    # 안정 수렴
    if all(abs(values[i] - values[i-1]) < 0.01 for i in range(2, len(values))):
        return "stable_convergence"

    # 진동 패턴
    if any(
        (values[i] - values[i-1]) * (values[i+1] - values[i]) < 0
        for i in range(1, len(values)-1)
    ):
        return "oscillation"

    # 발산
    if values[-1] > values[0] * 1.5:
        return "divergence"

    # 두 안정점 중 하나
    return "bistable"
