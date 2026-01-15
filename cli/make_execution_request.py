# cli/make_execution_request.py
from __future__ import annotations

import argparse
import json
import os
import time
from dataclasses import asdict
from typing import Any, Dict, Optional, Tuple

from core.contracts.orchestrator import (
    ExecutionAuthorizationRequest,
    ExecutionLimit,
    ExecutionScope,
    ExecutionTimebox,
    ResponsibilityAcceptance,
    ResponsibilityDecision,
    assert_execution_request_valid,
)


def _now_iso_utc() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _save_json(path: str, obj: Any) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2, sort_keys=True)
        f.write("\n")
    os.replace(tmp, path)


def _load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _parse_csv_tuple(s: Optional[str]) -> Tuple[str, ...]:
    if not s:
        return ()
    parts = [p.strip() for p in s.split(",")]
    return tuple([p for p in parts if p])


def _ensure_receipt_meta_exec_path(receipt_path: str, exec_req_path: str) -> None:
    r = _load_json(receipt_path)
    meta = r.get("meta") or {}
    meta["execution_request_path"] = exec_req_path
    r["meta"] = meta
    _save_json(receipt_path, r)


def build_request(
    *,
    judgment_ref: str,
    actor_id: str,
    actor_role: str,
    domain: str,
    permitted_actions: Tuple[str, ...],
    assets: Tuple[str, ...],
    account_id: Optional[str],
    target_id: Optional[str],
    notes: Optional[str],
    max_notional_usd: Optional[float],
    max_order_count: Optional[int],
    max_daily_loss_usd: Optional[float],
    valid_from: str,
    valid_until: str,
    request_payload_json: Optional[str],
) -> ExecutionAuthorizationRequest:
    responsibility = ResponsibilityAcceptance(
        decision=ResponsibilityDecision.ACCEPT,
        actor_id=actor_id,
        actor_role=actor_role,
        ts=_now_iso_utc(),
        judgment_ref=judgment_ref,
        reason=None,
        metadata=None,
    )

    scope = ExecutionScope(
        domain=domain,
        permitted_actions=permitted_actions,
        assets=assets,
        account_id=account_id,
        target_id=target_id,
        notes=notes,
    )

    limit_ = ExecutionLimit(
        max_notional_usd=max_notional_usd,
        max_order_count=max_order_count,
        max_daily_loss_usd=max_daily_loss_usd,
        metadata=None,
    )

    timebox = ExecutionTimebox(valid_from=valid_from, valid_until=valid_until)

    payload: Optional[Dict[str, Any]] = None
    if request_payload_json:
        payload = json.loads(request_payload_json)

    req = ExecutionAuthorizationRequest(
        auto_action=False,
        responsibility=responsibility,
        scope=scope,
        limit=limit_,
        timebox=timebox,
        judgment_ref=judgment_ref,
        request_payload=payload,
        metadata=None,
    )

    assert_execution_request_valid(req)
    return req


def main() -> None:
    ap = argparse.ArgumentParser(
        prog="make_execution_request",
        description="Create Gate 2 ExecutionAuthorizationRequest artifact (non-executing).",
    )

    ap.add_argument("--judgment-ref", required=True)

    ap.add_argument("--actor-id", required=True)
    ap.add_argument("--actor-role", default="owner")

    ap.add_argument("--domain", default="family")
    ap.add_argument("--permitted-actions", default="")
    ap.add_argument("--assets", default="")
    ap.add_argument("--account-id", default=None)
    ap.add_argument("--target-id", default=None)
    ap.add_argument("--notes", default=None)

    ap.add_argument("--max-notional-usd", type=float, default=None)
    ap.add_argument("--max-order-count", type=int, default=None)
    ap.add_argument("--max-daily-loss-usd", type=float, default=None)

    ap.add_argument("--valid-from", required=True)
    ap.add_argument("--valid-until", required=True)

    ap.add_argument("--request-payload-json", default=None)

    ap.add_argument("--out-dir", default="logs/outbox/execution_requests")
    ap.add_argument("--filename", default=None)
    ap.add_argument("--attach-to-receipt", default=None)

    args = ap.parse_args()

    permitted_actions = _parse_csv_tuple(args.permitted_actions)
    assets = _parse_csv_tuple(args.assets)

    req = build_request(
        judgment_ref=args.judgment_ref,
        actor_id=args.actor_id,
        actor_role=args.actor_role,
        domain=args.domain,
        permitted_actions=permitted_actions,
        assets=assets,
        account_id=args.account_id,
        target_id=args.target_id,
        notes=args.notes,
        max_notional_usd=args.max_notional_usd,
        max_order_count=args.max_order_count,
        max_daily_loss_usd=args.max_daily_loss_usd,
        valid_from=args.valid_from,
        valid_until=args.valid_until,
        request_payload_json=args.request_payload_json,
    )

    ts_tag = time.strftime("%Y%m%d_%H%M%S", time.gmtime())
    safe_jref = args.judgment_ref.replace("/", "_").replace(":", "_").replace(" ", "_")
    fname = args.filename or f"exec_req__{safe_jref}__{ts_tag}.json"
    out_path = os.path.join(args.out_dir, fname)

    _save_json(out_path, asdict(req))

    if args.attach_to_receipt:
        _ensure_receipt_meta_exec_path(args.attach_to_receipt, out_path)

    print(out_path, flush=True)


if __name__ == "__main__":
    main()
