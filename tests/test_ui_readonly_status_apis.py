from __future__ import annotations

import json
import time

from infra.api.endpoints import ui_status


def test_intent_latest_prefers_latest_outbox_file(tmp_path, monkeypatch):
    outbox_dir = tmp_path / "outbox"
    outbox_dir.mkdir(parents=True, exist_ok=True)
    older = outbox_dir / "intent_older.json"
    latest = outbox_dir / "intent_latest.json"
    older.write_text(json.dumps({"source": "outbox", "v": 1}), encoding="utf-8")
    time.sleep(0.01)
    latest.write_text(json.dumps({"source": "outbox", "v": 2}), encoding="utf-8")

    audit_file = tmp_path / "execution_intent.jsonl"
    audit_file.write_text(json.dumps({"source": "audit", "v": 999}) + "\n", encoding="utf-8")

    monkeypatch.setattr(ui_status, "OUTBOX_DIR", outbox_dir)
    monkeypatch.setattr(ui_status, "AUDIT_EXECUTION_INTENT", audit_file)

    resp = ui_status.get_latest_intent()
    assert resp == {"source": "outbox", "v": 2}


def test_audit_chain_status_handles_missing_files_as_na(tmp_path, monkeypatch):
    missing_exec = tmp_path / "missing_execution_intent.jsonl"
    missing_orders = tmp_path / "missing_paper_orders.jsonl"
    missing_fills = tmp_path / "missing_paper_fills.jsonl"

    monkeypatch.setattr(ui_status, "AUDIT_EXECUTION_INTENT", missing_exec)
    monkeypatch.setattr(ui_status, "AUDIT_PAPER_ORDERS", missing_orders)
    monkeypatch.setattr(ui_status, "AUDIT_PAPER_FILLS", missing_fills)

    resp = ui_status.get_audit_chain_status()
    assert resp == {
        "execution_intent": {"lines": "n/a", "last_hash": "n/a"},
        "paper_orders": {"lines": "n/a", "last_hash": "n/a"},
        "paper_fills": {"lines": "n/a", "last_hash": "n/a"},
    }


def test_executor_status_defaults_when_state_file_missing(tmp_path, monkeypatch):
    missing_status = tmp_path / "no_executor_status.json"
    missing_streak = tmp_path / "no_executor_fail_streak.txt"
    monkeypatch.setattr(ui_status, "EXECUTOR_STATUS_CANDIDATES", [missing_status])
    monkeypatch.setattr(ui_status, "EXECUTOR_FAIL_STREAK_FILE", missing_streak)

    resp = ui_status.get_executor_status()
    assert resp == {
        "fail_streak": 0,
        "last_http_code": "n/a",
        "last_event_id": "n/a",
    }
