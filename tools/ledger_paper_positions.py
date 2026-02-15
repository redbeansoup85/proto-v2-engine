#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Ledger paper positions from fills.
- Supports:
  (1) --fills <paper_fill_event.v1>
  (2) --chain <paper_fills.jsonl>
- Aggregates per-symbol:
  - position_qty (signed: BUY +, SELL -)
  - avg_entry_price (for open position, simple WAP on same direction adds)
  - realized_pnl (USDT)
  - fees_paid (USDT)
  - last_fill_price
- Unrealized PnL requires --mark <price> per symbol or mark from last_fill_price if not provided (optional).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Dict, List, Optional, Tuple


class ContractError(Exception):
    pass


def _canonical_json(obj: Any) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True, separators=(",", ":"))

def load_json(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise ContractError(msg)

def is_iso_z(ts: str) -> bool:
    return isinstance(ts, str) and ts.endswith("Z") and "T" in ts

def validate_fill_event(doc: Dict[str, Any]) -> None:
    require(doc.get("schema") == "paper_fill_event.v1", "schema must be paper_fill_event.v1")
    require(doc.get("domain") == "SENTINEL", "domain must be SENTINEL")
    require(doc.get("kind") == "PAPER_FILL", "kind must be PAPER_FILL")
    require(isinstance(doc.get("fills"), list) and len(doc["fills"]) > 0, "fills must be non-empty list")
    require(is_iso_z(doc.get("ts_iso", "")), "ts_iso must be ISO-8601 Z")

def iter_chain(chain_path: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []
    if not os.path.exists(chain_path):
        return events
    with open(chain_path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            obj = json.loads(line)
            # allow chain objects which include hash fields
            if obj.get("schema") == "paper_fill_event.v1":
                events.append(obj)
    return events


# -------------------------
# Position math (simple)
# -------------------------

def sgn(side: str) -> int:
    return 1 if side == "BUY" else -1

def apply_fill(state: Dict[str, Any], fill: Dict[str, Any]) -> None:
    """
    state fields (per symbol):
      qty (signed)
      avg_px (for open position)
      realized_pnl
      fees
      last_px
    """
    side = fill["side"]
    qty = float(fill["qty"])
    px = float(fill["price"])
    fee = float(fill.get("fee", 0.0))

    pos_qty = float(state.get("qty", 0.0))
    avg_px = float(state.get("avg_px", 0.0))
    realized = float(state.get("realized_pnl", 0.0))
    fees = float(state.get("fees", 0.0))

    trade_qty_signed = qty * sgn(side)

    # If position direction matches trade direction -> increase position WAP
    if pos_qty == 0 or (pos_qty > 0 and trade_qty_signed > 0) or (pos_qty < 0 and trade_qty_signed < 0):
        new_qty = pos_qty + trade_qty_signed
        # WAP on absolute notional for same-direction adds
        if pos_qty == 0:
            new_avg = px
        else:
            # weights by abs qty
            new_avg = (abs(pos_qty) * avg_px + abs(trade_qty_signed) * px) / (abs(pos_qty) + abs(trade_qty_signed))
        pos_qty, avg_px = new_qty, new_avg
    else:
        # Trade reduces or flips position -> realize PnL on closed portion
        close_qty = min(abs(pos_qty), abs(trade_qty_signed))  # how much we close
        if pos_qty > 0 and trade_qty_signed < 0:
            # closing a long by selling: pnl = (sell_px - avg_px) * close_qty
            realized += (px - avg_px) * close_qty
        elif pos_qty < 0 and trade_qty_signed > 0:
            # closing a short by buying: pnl = (avg_px - buy_px) * close_qty
            realized += (avg_px - px) * close_qty

        new_qty = pos_qty + trade_qty_signed

        if new_qty == 0:
            avg_px = 0.0
        else:
            # If flip happens, remaining qty takes entry px = current px
            if (pos_qty > 0 and new_qty < 0) or (pos_qty < 0 and new_qty > 0):
                avg_px = px
            # else partial reduce keeps avg_px

        pos_qty = new_qty

    fees += fee
    state["qty"] = pos_qty
    state["avg_px"] = avg_px
    state["realized_pnl"] = realized
    state["fees"] = fees
    state["last_px"] = px


def main() -> int:
    ap = argparse.ArgumentParser()
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--fills", help="paper_fill_event.v1 path")
    g.add_argument("--chain", help="var/audit_chain/paper_fills.jsonl path")
    ap.add_argument("--out", required=True, help="output ledger json path")
    ap.add_argument("--mark", action="append", default=[], help="MARK in form SYMBOL=PRICE (optional)")
    args = ap.parse_args()

    try:
        marks: Dict[str, float] = {}
        for m in args.mark:
            if "=" not in m:
                raise ContractError("--mark must be SYMBOL=PRICE")
            sym, px = m.split("=", 1)
            marks[sym] = float(px)

        events: List[Dict[str, Any]] = []
        if args.fills:
            doc = load_json(args.fills)
            validate_fill_event(doc)
            events = [doc]
        else:
            events = iter_chain(args.chain)

        ledger: Dict[str, Dict[str, Any]] = {}
        for ev in events:
            validate_fill_event(ev)
            for f in ev["fills"]:
                sym = f["symbol"]
                st = ledger.get(sym) or {"qty": 0.0, "avg_px": 0.0, "realized_pnl": 0.0, "fees": 0.0, "last_px": 0.0}
                apply_fill(st, f)
                ledger[sym] = st

        # Unrealized PnL (optional)
        out_positions: Dict[str, Any] = {}
        for sym, st in ledger.items():
            qty = float(st["qty"])
            avg_px = float(st["avg_px"])
            last_px = float(st["last_px"])
            mark_px = float(marks.get(sym, last_px if last_px > 0 else 0.0))

            unreal = 0.0
            if qty != 0 and mark_px > 0 and avg_px > 0:
                if qty > 0:
                    unreal = (mark_px - avg_px) * abs(qty)
                else:
                    unreal = (avg_px - mark_px) * abs(qty)

            out_positions[sym] = {
                "position_qty": qty,
                "avg_entry_price": avg_px,
                "last_fill_price": last_px,
                "mark_price": mark_px,
                "realized_pnl": float(st["realized_pnl"]),
                "unrealized_pnl": unreal,
                "fees_paid": float(st["fees"]),
            }

        out_doc = {
            "schema": "paper_positions_ledger.v1",
            "domain": "SENTINEL",
            "ts_iso": "",  # deterministic output; leave blank
            "positions": out_positions,
        }

        os.makedirs(os.path.dirname(args.out), exist_ok=True)
        with open(args.out, "w", encoding="utf-8") as f:
            f.write(_canonical_json(out_doc))
            f.write("\n")

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
