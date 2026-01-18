from infra.api.audit_sink import emit_audit_event


def test_emit_audit_event_does_not_raise():
    event = {
        "event": "enforce",
        "outcome": "allow",
        "approval_id": "apr-1",
        "envelope_id": "env-1",
        "authority_id": "auth-1",
        "issued_at": "2026-01-01T00:00:00Z",
        "expires_at": "2026-01-01T01:00:00Z",
    }
    emit_audit_event(event)
