#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Paper Fill Simulator v1
- Input: paper_order_intent.v1 (one file)
- Output: paper_fill_event.v1 (one file), deterministic
- Default fill price: snapshot close
- Model: 1 order -> 1 fill
- Fee/Slippage: fixed bps
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import hashlib
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# -------------------------
# Canonical JSON + hashing
# -------------------------

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def now_iso_utc() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def write_json(path: str, obj: Dict[str, Any]) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(_canonical_json(obj))
        f.write("\n")
    os.replace(tmp, path)


# -------------------------
# Contract validation
# -------------------------

class ContractError(Exception):
    pass

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ContractError(msg)

def is_iso_z(ts: str) -> bool:
    # strict-ish: requires trailing Z
    return isinstance(ts, str) and ts.endswith("Z") and "T" in ts

def validate_order_intent(doc: Dict[str, Any]) -> None:
    require(doc.get("schema") == "paper_order_intent.v1", "schema must be paper_order_intent.v1")
    require(doc.get("domain") == "SENTINEL", "domain must be SENTINEL")
    require(is_iso_z(doc.get("ts_iso", "")), "ts_iso must be ISO-8601 Z")
    orders = doc.get("orders")
    require(isinstance(orders, list) and len(orders) > 0, "orders must be non-empty list")

    snap = doc.get("snapshot")
    require(isinstance(snap, dict), "snapshot must be object")
    require(is_iso_z(snap.get("ts_iso", "")), "snapshot.ts_iso must be ISO-8601 Z")
    require(isinstance(snap.get("close"), (int, float)) and snap["close"] > 0, "snapshot.close must be > 0 number")

    for i, o in enumerate(orders):
        require(isinstance(o, dict), f"orders[{i}] must be object")
        require(isinstance(o.get("symbol"), str) and o["symbol"], f"orders[{i}].symbol required")
        require(o.get("side") in ("BUY", "SELL"), f"orders[{i}].side must be BUY/SELL")
        require(isinstance(o.get("qty"), (int, float)) and o["qty"] > 0, f"orders[{i}].qty must be > 0")
        require(o.get("order_type", "MARKET") in ("MARKET",), f"orders[{i}].order_type must be MARKET (v1)")
        # optional: client_order_id
        if "client_order_id" in o:
            require(isinstance(o["client_order_id"], str) and o["client_order_id"], f"orders[{i}].client_order_id non-empty str")


# -------------------------
# Simulation model
# -------------------------

@dataclass(frozen=True)
class ModelParams:
    fee_bps: float
    slippage_bps: float
    fee_ccy: str
    sim_model: str

def compute_fill_price(snapshot_close: float, side: str, slippage_bps: float) -> float:
    # BUY -> pay higher, SELL -> receive lower
    slip = snapshot_close * (slippage_bps / 10_000.0)
    return snapshot_close + slip if side == "BUY" else snapshot_close - slip

def compute_fee(qty: float, price: float, fee_bps: float) -> float:
    # simple notional fee
    notional = qty * price
    return notional * (fee_bps / 10_000.0)

def build_event_id(input_path: str, input_doc: Dict[str, Any], params: ModelParams) -> str:
    # Deterministic ID based on canonical payload seed (no wall-clock)
    seed = {
        "schema": "paper_fill_event.v1",
        "source_path": os.path.abspath(input_path),
        "ts_iso": input_doc["ts_iso"],
        "snapshot": {
            "ts_iso": input_doc["snapshot"]["ts_iso"],
            "close": float(input_doc["snapshot"]["close"]),
        },
        "orders": input_doc["orders"],
        "model": {
            "fee_bps": params.fee_bps,
            "slippage_bps": params.slippage_bps,
            "fee_ccy": params.fee_ccy,
            "sim_model": params.sim_model,
        },
    }
    return "pfill_" + sha256_hex(_canonical_json(seed))[:24]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="paper_order_intent.v1 path")
    ap.add_argument("--out", required=True, help="paper_fill_event.v1 output path")
    ap.add_argument("--fee-bps", type=float, default=float(os.environ.get("PAPER_FEE_BPS", "6.0")))
    ap.add_argument("--slippage-bps", type=float, default=float(os.environ.get("PAPER_SLIPPAGE_BPS", "2.0")))
    ap.add_argument("--fee-ccy", default=os.environ.get("PAPER_FEE_CCY", "USDT"))
    ap.add_argument("--policy-sha256", default=os.environ.get("PAPER_FILL_POLICY_SHA256", ""))
    args = ap.parse_args()

    try:
        doc = load_json(args.input)
        validate_order_intent(doc)
        params = ModelParams(
            fee_bps=float(args.fee_bps),
            slippage_bps=float(args.slippage_bps),
            fee_ccy=str(args.fee_ccy),
            sim_model="MARKET_AT_SNAPSHOT_CLOSE_V1",
        )

        snapshot_close = float(doc["snapshot"]["close"])
        snapshot_ts = doc["snapshot"]["ts_iso"]

        fills: List[Dict[str, Any]] = []
        for idx, o in enumerate(doc["orders"]):
            side = o["side"]
            qty = float(o["qty"])
            px = compute_fill_price(snapshot_close, side, params.slippage_bps)
            fee = compute_fee(qty, px, params.fee_bps)

            fills.append({
                "symbol": o["symbol"],
                "side": side,
                "qty": qty,
                "price": round(px, 10),
                "fee": round(fee, 10),
                "fee_ccy": params.fee_ccy,
                "fill_ts_iso": snapshot_ts,
                "order_index": idx,
                "client_order_id": o.get("client_order_id", ""),
            })

        event_id = build_event_id(args.input, doc, params)

        out_doc: Dict[str, Any] = {
            "schema": "paper_fill_event.v1",
            "domain": "SENTINEL",
            "kind": "PAPER_FILL",
            "event_id": event_id,
            "ts_iso": doc["ts_iso"],  # event time = intent time (deterministic)
            "source": {
                "ref": os.path.abspath(args.input),
                "snapshot_ref": {
                    "ts_iso": snapshot_ts,
                    "close": snapshot_close,
                },
            },
            "fills": fills,
            "meta": {
                "sim_model": params.sim_model,
                "fee_bps": params.fee_bps,
                "slippage_bps": params.slippage_bps,
                "fee_ccy": params.fee_ccy,
                "policy_sha256": args.policy_sha256,
                "generated_at_iso": "",  # keep deterministic; leave blank (append tool can stamp if needed)
            },
        }

        write_json(args.out, out_doc)
        print(f"OK: wrote {args.out}")
        return 0

    except ContractError as e:
        print(f"CONTRACT_FAIL: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: {type(e).__name__}: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
