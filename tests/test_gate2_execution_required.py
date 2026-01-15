import json
import pytest

from core.C_action.plan_from_receipt import build_delivery_plan_from_receipt

def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")
    return str(p)

def test_execution_channel_requires_gate2(tmp_path):
    """
    For execution-class channels (e.g., trading),
    receipt.meta.execution_request_path MUST exist.
    """
    receipt = {
        "proposal_id": "pp_test",
        "meta": {
            "channel": "trading",
            # execution_request_path intentionally missing
        },
        "evidence": {
            "evidence_scene_ids": ["scene_test"]
        }
    }

    p = _write(tmp_path, "receipt_missing_gate2.json", receipt)

    with pytest.raises(ValueError) as e:
        build_delivery_plan_from_receipt(p)

    assert "ExecutionAuthorization required" in str(e.value)

def test_execution_channel_with_gate2_passes(tmp_path):
    """
    When execution_request_path exists and is valid,
    plan build must pass.
    """
    # Minimal valid execution request (Gate-2)
    exec_req = {
        "auto_action": False,
        "judgment_ref": "RECEIPT_PATH_WILL_BE_REPLACED",
        "responsibility": {
            "decision": "ACCEPT",
            "actor_id": "tester",
            "actor_role": "owner",
            "ts": "2026-01-06T00:00:00Z",
            "judgment_ref": "RECEIPT_PATH_WILL_BE_REPLACED"
        },
        "scope": {"domain": "family"},
        "limit": {"max_order_count": 1},
        "timebox": {"valid_from": "2026-01-06T00:00:00Z", "valid_until": "2026-01-06T01:00:00Z"}
    }

    exec_req_path = _write(tmp_path, "exec_req.json", exec_req)

    receipt = {
        "proposal_id": "pp_test",
        "meta": {
            "channel": "trading",
            "execution_request_path": exec_req_path
        },
        "evidence": {
            "evidence_scene_ids": ["scene_test"]
        }
    }

    receipt_path = _write(tmp_path, "receipt_ok.json", receipt)

    # Patch judgment_ref to receipt path (SSoT invariant)
    er = json.loads((tmp_path / "exec_req.json").read_text(encoding="utf-8"))
    er["judgment_ref"] = receipt_path
    er["responsibility"]["judgment_ref"] = receipt_path
    (tmp_path / "exec_req.json").write_text(json.dumps(er, ensure_ascii=False, indent=2), encoding="utf-8")

    plan = build_delivery_plan_from_receipt(receipt_path)
    assert plan.channel == "trading"
