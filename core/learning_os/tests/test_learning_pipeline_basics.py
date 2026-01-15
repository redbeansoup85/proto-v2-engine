import time

from core.learning_os.config import LearningCanonConfig
from core.learning_os.observation_store import ObservationStore
from core.learning_os.windowing import select_window
from core.learning_os.sampling import check_sample_sufficiency
from core.learning_os.stability import check_stability_v1
from core.learning_os.rate_limiter import RateLimiter
from core.learning_os.proposal_builder import build_policy_proposal


def test_window_sampling_stability_and_rate_limit():
    cfg = LearningCanonConfig(
        window_mode="events",
        t_window="7d",
        n_events_window=10,
        n_min=5,
        k_confirmations=3,
        epsilon_max=0.5,
        period="7d",
        limit_x=1,
        cooldown="7d",
        rest_period="7d",
    )

    store = ObservationStore()
    # stable tail: last 3 are 'up'
    for d in ["down", "up", "up", "up", "up"]:
        store.append(d)

    window = select_window(store.all(), mode="events", n_events=10)
    sample = check_sample_sufficiency(window, n_min=cfg.n_min)
    assert sample.ok is True

    st = check_stability_v1(window, k_confirmations=cfg.k_confirmations, epsilon_max=cfg.epsilon_max)
    assert st.ok is True

    limiter = RateLimiter(period_seconds=60, limit_x=1)
    d1 = limiter.check_and_record("policy:x", now=time.time())
    assert d1.allowed is True
    d2 = limiter.check_and_record("policy:x", now=time.time())
    assert d2.allowed is False

    proposal = build_policy_proposal(
        cfg=cfg,
        baseline_policy_snapshot_id="snap-1",
        baseline_policy_hash="ph",
        domain="policy",
        subsystem="x",
        severity="low",
        blast_radius="local",
        patch_format="jsonpatch",
        patch_content=[],
        explain_current="a",
        explain_proposed="b",
        rationale="c",
        expected_impact="d",
        rollback_scope="e",
        risks=[],
        assumptions=[],
        evidence_refs=[],
        sample_check=sample,
        stability=st,
        created_at="2026-01-07T00:00:00Z",
    )
    assert proposal.proposal_id.startswith("pp-")
    assert proposal.preconditions.sample.n_observed >= proposal.preconditions.sample.n_min
