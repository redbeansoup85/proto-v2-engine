from core.execution.idempotency_guard import IdempotencyGuard


def test_idempotency_guard_blocks_replay():
    g = IdempotencyGuard()

    ok1, cnt1 = g.check_and_mark("apr-1", "env-1")
    assert ok1 is True
    assert cnt1 == 1

    ok2, cnt2 = g.check_and_mark("apr-1", "env-1")
    assert ok2 is False
    assert cnt2 == 2
