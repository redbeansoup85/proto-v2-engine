import time

from core.learning_os.config import LearningCanonConfig
from core.learning_os.observation_store import ObservationStore
from core.learning_os.windowing import select_window
from core.learning_os.sampling import check_sample_sufficiency
from core.learning_os.stability import check_stability_v1
from core.learning_os.rate_limiter import RateLimiter
from core.learning_os.proposal_builder import build_policy_proposal
from core.learning_os.proposal_emitter import emit_proposal_if_allowed

from core.governance.proposal_validator import CanonParams


class InMemoryWriter:
    def __init__(self):
        self.items = []

    def write(self, item):
        self.items.append(item)


def test_emitter_blocks_human_gate_required():
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
    for d in ["up", "up", "up", "up", "up"]:
        store.append(d)

    window = select_window(store.all(), mode="events", n_events=10)
    sample = check_sample_sufficiency(window, n_min=cfg.n_min)
    st = check_stability_v1(window, k_confirmations=cfg.k_confirmations, epsilon_max=cfg.epsilon_max)

    # External blast radius triggers human gate
    proposal = build_policy_proposal(
        cfg=cfg,
        baseline_policy_snapshot_id="snap-1",
        baseline_policy_hash="ph",
        domain="policy",
        subsystem="x",
        severity="high",
        blast_radius="external",
        patch_format="jsonpatch",
        patch_content=[],
        explain_current="a",
        explain_proposed="b",
        rationale="c",
        expected_impact="d",
        rollback_scope="e",
        risks=["reputation risk"],
        assumptions=[],
        evidence_refs=[],
        sample_check=sample,
        stability=st,
        created_at="2026-01-07T00:00:00Z",
    )

    writer = InMemoryWriter()
    limiter = RateLimiter(period_seconds=60, limit_x=1)

    d = emit_proposal_if_allowed(
        proposal=proposal,
        cfg=cfg,
        canon_params=CanonParams(n_min=cfg.n_min, k_confirmations=cfg.k_confirmations, epsilon_max=cfg.epsilon_max, limit_x=cfg.limit_x),
        embedded_canon_version="1.0",
        embedded_pack_version="1.0",
        writer=writer,
        limiter=limiter,
        limiter_key="policy:x",
        now=time.time(),
    )

    assert d.emitted is False
    assert d.reason.startswith("HUMAN_GATE_REQUIRED")
    assert writer.items == []


def test_emitter_emits_when_allowed_and_rate_limited():
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
    for d in ["down", "up", "up", "up", "up"]:
        store.append(d)

    window = select_window(store.all(), mode="events", n_events=10)
    sample = check_sample_sufficiency(window, n_min=cfg.n_min)
    st = check_stability_v1(window, k_confirmations=cfg.k_confirmations, epsilon_max=cfg.epsilon_max)

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
        rollback_scope="simple rollback; single-step revert",
        risks=[],
        assumptions=[],
        evidence_refs=[],
        sample_check=sample,
        stability=st,
        created_at="2026-01-07T00:00:00Z",
    )

    writer = InMemoryWriter()
    limiter = RateLimiter(period_seconds=60, limit_x=1)

    t = time.time()
    d1 = emit_proposal_if_allowed(
        proposal=proposal,
        cfg=cfg,
        canon_params=CanonParams(n_min=cfg.n_min, k_confirmations=cfg.k_confirmations, epsilon_max=cfg.epsilon_max, limit_x=cfg.limit_x),
        embedded_canon_version="1.0",
        embedded_pack_version="1.0",
        writer=writer,
        limiter=limiter,
        limiter_key="policy:x",
        now=t,
    )
    assert d1.emitted is True
    assert len(writer.items) == 1

    # Second emission should be blocked by rate limiter
    d2 = emit_proposal_if_allowed(
        proposal=proposal,
        cfg=cfg,
        canon_params=CanonParams(n_min=cfg.n_min, k_confirmations=cfg.k_confirmations, epsilon_max=cfg.epsilon_max, limit_x=cfg.limit_x),
        embedded_canon_version="1.0",
        embedded_pack_version="1.0",
        writer=writer,
        limiter=limiter,
        limiter_key="policy:x",
        now=t + 1,
    )
    assert d2.emitted is False
    assert d2.reason == "RATE_LIMIT_EXCEEDED"
    assert len(writer.items) == 1
