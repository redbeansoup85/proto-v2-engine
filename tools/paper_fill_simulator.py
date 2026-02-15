#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Paper Fill Simulator v1 (compat)

Accepts two input shapes:

(A) Flat paper_order_intent.v1 (legacy)
  {
    "schema":"paper_order_intent.v1",
    "domain":"SENTINEL"|"SENTINEL_EXEC",
    "ts_iso":"...Z",
    "snapshot":{"ts_iso":"...Z","close":...},
    "orders":[{"symbol","side","qty","order_type","client_order_id?"}]
  }

(B) Sentinel paper orders intent (current)
  {
    "schema":"paper_order_intent.v1",
    "domain":"SENTINEL_EXEC",
    "kind":"INTENT",
    "intent":{
      "ts":"YYYYmmddTHHMMSSZ",
      "execution_mode":"paper",
      "orders":[{"symbol","side","leverage", "sizing":{"equity_pct":...}, ...}]
    }
  }

For (B), we derive:
- per-order snapshot close from: /tmp/metaos_snapshots/{SYMBOL}_{TF}/snapshot_{TS}.json (default TF=15m)
- qty from: (PAPER_EQUITY_USDT * equity_pct * leverage) / snapshot_close
  * PAPER_EQUITY_USDT is REQUIRED when qty not provided.

Fill model:
- 1 order -> 1 fill
- price = per-order snapshot close (+/- slippage bps depending on side)
- fee = notional * fee_bps
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Tuple


# -------------------------
# Canonical JSON + hashing
# -------------------------

def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_hex(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()


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
# Contract helpers
# -------------------------

class ContractError(Exception):
    pass


def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ContractError(msg)


def is_iso_z(ts: str) -> bool:
    return isinstance(ts, str) and ts.endswith("Z") and "T" in ts


def ts_compact_to_iso(ts: str) -> str:
    # 20260215T011155Z -> 2026-02-15T01:11:55Z
    require(isinstance(ts, str) and len(ts) == 16 and ts.endswith("Z") and "T" in ts, f"bad compact ts: {ts}")
    return f"{ts[0:4]}-{ts[4:6]}-{ts[6:8]}T{ts[9:11]}:{ts[11:13]}:{ts[13:15]}Z"


# -------------------------
# Model
# -------------------------

@dataclass(frozen=True)
class ModelParams:
    fee_bps: float
    slippage_bps: float
    fee_ccy: str
    sim_model: str
    snapshot_tf: str


def compute_fill_price(snapshot_close: float, side: str, slippage_bps: float) -> float:
    slip = snapshot_close * (slippage_bps / 10_000.0)
    return snapshot_close + slip if side == "BUY" else snapshot_close - slip


def compute_fee(qty: float, price: float, fee_bps: float) -> float:
    return (qty * price) * (fee_bps / 10_000.0)


def load_snapshot_close(symbol: str, tf: str, ts_compact: str) -> Tuple[str, float]:
    # Use exact TS file for determinism
    snap_path = Path(f"/tmp/metaos_snapshots/{symbol}_{tf}/snapshot_{ts_compact}.json")
    require(snap_path.exists(), f"missing snapshot: {snap_path}")
    snap = json.loads(snap_path.read_text(encoding="utf-8"))
    close = float(snap["ohlc"]["close"])
    ts_iso = snap.get("ts_iso") or ts_compact_to_iso(ts_compact)
    require(is_iso_z(ts_iso), f"snapshot.ts_iso must be ISO-8601 Z, got={ts_iso}")
    return ts_iso, close


# -------------------------
# Input normalization
# -------------------------

def normalize_input(
    doc: Dict[str, Any],
    input_path: str,
    params: ModelParams,
) -> Tuple[str, Dict[str, Any], List[Dict[str, Any]]]:
    """
    Returns:
      ts_compact (YYYYmmddTHHMMSSZ),
      snapshot {ts_iso, close}  # representative (first order) snapshot for backward-friendly fields
      orders   [{symbol, side, qty, order_type, client_order_id, order_index, snapshot_* fields}]
    """
    require(doc.get("schema") == "paper_order_intent.v1", "schema must be paper_order_intent.v1")

    # Shape A (flat legacy)
    if isinstance(doc.get("orders"), list) and isinstance(doc.get("snapshot"), dict):
        require(doc.get("domain") in ("SENTINEL", "SENTINEL_EXEC"), "domain must be SENTINEL or SENTINEL_EXEC")
        require(is_iso_z(doc.get("ts_iso", "")), "ts_iso must be ISO-8601 Z")

        snap = doc["snapshot"]
        require(is_iso_z(snap.get("ts_iso", "")), "snapshot.ts_iso must be ISO-8601 Z")
        require(isinstance(snap.get("close"), (int, float)) and float(snap["close"]) > 0, "snapshot.close must be > 0")

        orders_in = doc["orders"]
        require(len(orders_in) > 0, "orders must be non-empty")

        orders: List[Dict[str, Any]] = []
        for i, o in enumerate(orders_in):
            require(isinstance(o, dict), f"orders[{i}] must be object")
            require(isinstance(o.get("symbol"), str) and o["symbol"], f"orders[{i}].symbol required")
            require(o.get("side") in ("BUY", "SELL"), f"orders[{i}].side must be BUY/SELL")
            require(isinstance(o.get("qty"), (int, float)) and float(o["qty"]) > 0, f"orders[{i}].qty must be > 0")
            require(o.get("order_type", "MARKET") in ("MARKET",), f"orders[{i}].order_type must be MARKET (v1)")

            orders.append(
                {
                    "symbol": o["symbol"],
                    "side": o["side"],
                    "qty": float(o["qty"]),
                    "order_type": o.get("order_type", "MARKET"),
                    "client_order_id": o.get("client_order_id", ""),
                    "order_index": i,
                    # legacy shape has a single snapshot; stamp it per-order too
                    "snapshot_ts_iso": snap["ts_iso"],
                    "snapshot_close": float(snap["close"]),
                    "snapshot_tf": params.snapshot_tf,
                }
            )

        # infer compact TS from ts_iso if possible (best-effort)
        ts_iso = doc["ts_iso"]
        ts_compact = doc.get("ts") or ""
        if not ts_compact:
            try:
                base = ts_iso.split(".")[0]  # strip micros
                ts_compact = base[0:4] + base[5:7] + base[8:10] + "T" + base[11:13] + base[14:16] + base[17:19] + "Z"
            except Exception:
                ts_compact = ""

        return ts_compact, {"ts_iso": snap["ts_iso"], "close": float(snap["close"])}, orders

    # Shape B (current sentinel paper orders intent)
    require(doc.get("domain") == "SENTINEL_EXEC", "domain must be SENTINEL_EXEC for intent-shape")
    require(doc.get("kind") == "INTENT", "kind must be INTENT for intent-shape")

    intent = doc.get("intent")
    require(isinstance(intent, dict), "intent must be object")

    ts_compact = intent.get("ts")
    require(isinstance(ts_compact, str) and ts_compact, "intent.ts required")

    orders_in = intent.get("orders")
    require(isinstance(orders_in, list) and len(orders_in) > 0, "intent.orders must be non-empty list")

    equity_usdt = os.environ.get("PAPER_EQUITY_USDT", "").strip()

    orders: List[Dict[str, Any]] = []
    snap_ts_iso = None
    snap_close = None

    for i, o in enumerate(orders_in):
        require(isinstance(o, dict), f"intent.orders[{i}] must be object")

        sym = o.get("symbol")
        side = o.get("side")

        require(isinstance(sym, str) and sym, f"intent.orders[{i}].symbol required")
        require(side in ("BUY", "SELL"), f"intent.orders[{i}].side must be BUY/SELL")

        # per-order snapshot close (symbol-specific)
        o_snap_ts_iso, o_snap_close = load_snapshot_close(sym, params.snapshot_tf, ts_compact)

        # representative snapshot (first order) for backward-friendly fields
        if snap_ts_iso is None:
            snap_ts_iso = o_snap_ts_iso
            snap_close = float(o_snap_close)

        # qty: prefer explicit qty if present; else compute from sizing.equity_pct
        qty_val = o.get("qty", None)
        if qty_val is not None:
            require(isinstance(qty_val, (int, float)) and float(qty_val) > 0, f"intent.orders[{i}].qty must be > 0")
            qty = float(qty_val)
        else:
            sizing = o.get("sizing", {})
            require(isinstance(sizing, dict), f"intent.orders[{i}].sizing must be object")

            eq_pct = sizing.get("equity_pct", None)
            require(eq_pct is not None, f"intent.orders[{i}] missing qty and sizing.equity_pct")
            require(isinstance(eq_pct, (int, float)) and float(eq_pct) > 0, f"intent.orders[{i}].sizing.equity_pct must be > 0")
            require(equity_usdt != "", "PAPER_EQUITY_USDT is required when qty is not provided")

            lev = float(o.get("leverage", 1))
            require(lev > 0, f"intent.orders[{i}].leverage must be > 0")

            notional = float(equity_usdt) * float(eq_pct) * lev
            qty = notional / float(o_snap_close)
            require(qty > 0, f"computed qty <= 0 for order[{i}]")

        orders.append(
            {
                "symbol": sym,
                "side": side,
                "qty": float(qty),
                "order_type": "MARKET",
                "client_order_id": o.get("client_order_id", ""),
                "order_index": i,
                # per-order snapshot fields
                "snapshot_ts_iso": o_snap_ts_iso,
                "snapshot_close": float(o_snap_close),
                "snapshot_tf": params.snapshot_tf,
            }
        )

    require(snap_ts_iso is not None and snap_close is not None, "failed to resolve snapshot for intent orders")
    return ts_compact, {"ts_iso": str(snap_ts_iso), "close": float(snap_close)}, orders


def build_event_id(
    input_path: str,
    ts_iso: str,
    snapshot: Dict[str, Any],
    orders: List[Dict[str, Any]],
    params: ModelParams,
) -> str:
    seed = {
        "schema": "paper_fill_event.v1",
        "source_path": os.path.abspath(input_path),
        "ts_iso": ts_iso,
        "snapshot": {"ts_iso": snapshot["ts_iso"], "close": float(snapshot["close"])},
        "orders": orders,
        "model": {
            "fee_bps": params.fee_bps,
            "slippage_bps": params.slippage_bps,
            "fee_ccy": params.fee_ccy,
            "sim_model": params.sim_model,
            "snapshot_tf": params.snapshot_tf,
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
    ap.add_argument("--snapshot-tf", default=os.environ.get("PAPER_SNAPSHOT_TF", "15m"))
    args = ap.parse_args()

    try:
        doc = load_json(args.input)
        params = ModelParams(
            fee_bps=float(args.fee_bps),
            slippage_bps=float(args.slippage_bps),
            fee_ccy=str(args.fee_ccy),
            sim_model="MARKET_AT_SNAPSHOT_CLOSE_V1",
            snapshot_tf=str(args.snapshot_tf),
        )

        ts_compact, snapshot, orders = normalize_input(doc, args.input, params)

        # Event ts_iso: deterministic
        if ts_compact:
            event_ts_iso = ts_compact_to_iso(ts_compact)
        else:
            event_ts_iso = doc.get("ts_iso", "")
            require(is_iso_z(event_ts_iso), "ts_iso required (or intent.ts)")

        snapshot_close = float(snapshot["close"])
        snapshot_ts_iso = snapshot["ts_iso"]

        # per-symbol snapshot refs (audit)
        per_symbol: Dict[str, Any] = {}
        for o in orders:
            sym = o.get("symbol")
            if isinstance(sym, str) and sym:
                per_symbol[sym] = {
                    "tf": o.get("snapshot_tf", params.snapshot_tf),
                    "ts_iso": o.get("snapshot_ts_iso", snapshot_ts_iso),
                    "close": float(o.get("snapshot_close", snapshot_close)),
                }

        fills: List[Dict[str, Any]] = []
        for o in orders:
            side = o["side"]
            qty = float(o["qty"])

            o_close = float(o.get("snapshot_close", snapshot_close))
            o_ts_iso = o.get("snapshot_ts_iso", snapshot_ts_iso)

            px = compute_fill_price(o_close, side, params.slippage_bps)
            fee = compute_fee(qty, px, params.fee_bps)

            fills.append(
                {
                    "symbol": o["symbol"],
                    "side": side,
                    "qty": qty,
                    "price": round(px, 10),
                    "fee": round(fee, 10),
                    "fee_ccy": params.fee_ccy,
                    "fill_ts_iso": o_ts_iso,
                    "order_index": int(o.get("order_index", 0)),
                    "client_order_id": o.get("client_order_id", ""),
                }
            )

        event_id = build_event_id(args.input, event_ts_iso, snapshot, orders, params)

        out_doc: Dict[str, Any] = {
            "schema": "paper_fill_event.v1",
            "domain": "SENTINEL",
            "kind": "PAPER_FILL",
            "event_id": event_id,
            "ts_iso": event_ts_iso,
            "source": {
                "ref": os.path.abspath(args.input),
                "snapshot_ref": {
                    # representative (backward-friendly)
                    "ts_iso": snapshot_ts_iso,
                    "close": snapshot_close,
                    "tf": params.snapshot_tf,
                    # detailed per-symbol refs (fix)
                    "per_symbol": per_symbol,
                },
            },
            "fills": fills,
            "meta": {
                "sim_model": params.sim_model,
                "fee_bps": params.fee_bps,
                "slippage_bps": params.slippage_bps,
                "fee_ccy": params.fee_ccy,
                "policy_sha256": args.policy_sha256,
                "generated_at_iso": "",  # deterministic
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
