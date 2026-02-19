from __future__ import annotations

import json
from pathlib import Path

from tools.judgment.judgment_ledger import append_judgment


def test_append_judgment_writes_jsonl(tmp_path: Path) -> None:
    ledger = tmp_path / "judgment.v1.jsonl"

    j = append_judgment(
        verdict="INFO",
        actor="test",
        reason="hello",
        domain="SENTINEL_EXEC",
        symbol="SOLUSDT",
        side="SHORT",
        policy_sha256="deadbeef",
        refs={"execution_intent_hash": "abc123"},
        ledger_path=ledger,
    )

    assert j["schema"] == "judgment.v1"
    assert j["actor"] == "test"
    assert j["verdict"] == "INFO"

    lines = ledger.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    parsed = json.loads(lines[0])
    assert parsed["schema"] == "judgment.v1"
    assert parsed["refs"]["execution_intent_hash"] == "abc123"
