#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
from pathlib import Path
from datetime import datetime, timezone


STATE_DIR = Path("/tmp/metaos_domain_events/_state")


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--verify", "HEAD"], text=True).strip()
    except Exception:
        return "n/a"


def clamp(v: float, lo: float, hi: float) -> float:
    return lo if v < lo else hi if v > hi else v


def load_json(path: Path) -> dict:
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return obj


def _state_path(symbol: str, tf: str) -> Path:
    # tf까지 분리해서 상태 충돌 방지(15m/1h 동시 운용 대비)
    return STATE_DIR / f"prev_oi_{symbol}_{tf}.json"


def _read_prev_oi(symbol: str, tf: str) -> float | None:
    p = _state_path(symbol, tf)
    if not p.exists():
        return None
    prev = load_json(p)
    v = prev.get("open_interest")
    if not isinstance(v, (int, float)):
        raise ValueError(f"state open_interest must be numeric: {p}")
    return float(v)


def _write_prev_oi(symbol: str, tf: str, oi: float, ts_iso: str) -> None:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    p = _state_path(symbol, tf)
    tmp = p.with_suffix(".json.tmp")
    tmp.write_text(
        json.dumps(
            {"symbol": symbol, "timeframe": tf, "open_interest": float(oi), "ts_iso": ts_iso},
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tmp.replace(p)


def score_v2(snapshot: dict, deriv: dict, symbol: str, tf: str) -> tuple[int, str | None, str, float]:
    """
    v2 adds OI delta using local state:
      - Uses current OI vs previous OI to compute pct change
      - Boosts score on OI spikes (proxy for positioning expansion)
      - Lowers score on OI dumps (unwind)
    """

    score = 50.0

    # --- Derivatives ---
    d = deriv.get("derivatives", {})
    if not isinstance(d, dict):
        d = {}

    oi = d.get("open_interest")
    lsr = d.get("long_short_ratio")

    if oi is None:
        raise ValueError("derivatives.open_interest missing")
    if not isinstance(oi, (int, float)):
        raise ValueError("derivatives.open_interest must be numeric")
    oi = float(oi)

    if lsr is not None and not isinstance(lsr, (int, float)):
        raise ValueError("derivatives.long_short_ratio must be numeric when present")
    lsr_v = float(lsr) if isinstance(lsr, (int, float)) else None

    # L/S skew (account ratio proxy)
    if lsr_v is not None:
        if lsr_v >= 1.50:
            score += 15.0
        elif lsr_v >= 1.20:
            score += 8.0
        elif lsr_v <= 0.70:
            score -= 15.0
        elif lsr_v <= 0.85:
            score -= 8.0

    # --- OI delta (state-based) ---
    prev_oi = _read_prev_oi(symbol, tf)
    oi_delta_pct: float | None = None
    if prev_oi is not None and prev_oi > 0:
        oi_delta_pct = (oi - prev_oi) / prev_oi * 100.0

        # Spike / dump buckets (TF-aware; tuned for practical OI movement)
        # Deadzone: ignore micro OI noise
        if abs(oi_delta_pct) < 0.01:
            oi_delta_pct = 0.0

        TH = {
            "1h":  {"s": 999.0, "m": 999.0, "l": 999.0},
            "15m": {"s": 0.01, "m": 0.03, "l": 0.06},
        }.get(tf, {"s": 0.20, "m": 0.50, "l": 1.00})

        if oi_delta_pct >= TH["l"]:
            score += 20.0
        elif oi_delta_pct >= TH["m"]:
            score += 12.0
        elif oi_delta_pct >= TH["s"]:
            score += 6.0
        elif oi_delta_pct <= -TH["l"]:
            score -= 20.0
        elif oi_delta_pct <= -TH["m"]:
            score -= 12.0
        elif oi_delta_pct <= -TH["s"]:
            score -= 6.0
    else:
        # 첫 사이클은 delta 없음: 너무 강하게 치우치지 않게
        score += 0.0

    # --- Candle (from snapshot.ohlc) ---
    ohlc = snapshot.get("ohlc")
    if not isinstance(ohlc, dict):
        raise ValueError("snapshot.ohlc must be object")
    for k in ("open", "high", "low", "close", "volume"):
        if k not in ohlc:
            raise ValueError(f"snapshot.ohlc.{k} missing")
        if not isinstance(ohlc[k], (int, float)):
            raise ValueError(f"snapshot.ohlc.{k} must be numeric")

    o = float(ohlc["open"])
    c = float(ohlc["close"])
    if c > o:
        score += 5.0
    elif c < o:
        score -= 5.0

    score = int(round(clamp(score, 0.0, 100.0)))

    # direction
    if score >= 65:
        direction = "long"
    elif score <= 35:
        direction = "short"
    else:
        direction = "neutral"

    # risk_level
    if score >= 80 or score <= 20:
        risk = "high"
    elif score >= 60 or score <= 40:
        risk = "medium"
    else:
        risk = "low"

    # confidence
    # - delta가 있으면 confidence 상향
    # - 방향이 neutral이면 낮게
    conf = 0.50
    if direction == "neutral":
        conf = 0.55
    else:
        conf = 0.50 + min(abs(score - 50) / 100.0, 0.35)

    if oi_delta_pct is not None:
        # delta magnitude가 클수록 조금 더 신뢰
        conf += min(abs(oi_delta_pct) / 100.0, 0.10)

    conf = float(clamp(conf, 0.0, 1.0))
    return score, direction, risk, conf, oi_delta_pct


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--symbol", required=True)
    ap.add_argument("--tf", required=True)
    ap.add_argument("--snapshot-path", required=True)
    ap.add_argument("--deriv-path", required=True)
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    snap_p = Path(args.snapshot_path)
    der_p = Path(args.deriv_path)
    if not snap_p.exists():
        print(f"FAIL-CLOSED: snapshot-path not found: {snap_p}")
        return 1
    if not der_p.exists():
        print(f"FAIL-CLOSED: deriv-path not found: {der_p}")
        return 1

    try:
        snapshot = load_json(snap_p)
        deriv = load_json(der_p)

        ts_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        event_id_ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")

        # score v2 (OI delta state)
        score, direction, risk_level, confidence, oi_delta_pct = score_v2(snapshot, deriv, args.symbol, args.tf)

        # write state (prev OI) AFTER successful score computation (fail-closed)
        oi_now = float(deriv.get("derivatives", {}).get("open_interest"))
        _write_prev_oi(args.symbol, args.tf, oi_now, ts_iso)

        event = {
            "schema": "domain_event.v1",
            "domain": "sentinel",
            "kind": "SIGNAL",
            "event_id": f"{args.symbol}-{args.tf}-{event_id_ts}",
            "ts_iso": ts_iso,
            "signal": {
                "type": "BYBIT_ALERT",
                "symbol": args.symbol,
                "timeframe": args.tf,
                "score": int(score),
                "direction": direction,
                "risk_level": risk_level,
                "confidence": float(confidence),
            },
            "evidence_refs": [
                {"ref_kind": "FILEPATH", "ref": str(snap_p)},
                {"ref_kind": "FILEPATH", "ref": str(der_p)},
            ],
            "meta": {
                "producer": "real_mode",
                "version": "v2",
                "build_sha": git_sha(),
            },
        }

        out_p = Path(args.out)
        out_p.parent.mkdir(parents=True, exist_ok=True)
        out_p.write_text(json.dumps(event, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_p} score={score} dir={direction} risk={risk_level} conf={confidence:.2f} oiΔ={oi_delta_pct if oi_delta_pct is not None else 'n/a'}%")
        return 0

    except Exception as e:
        print(f"FAIL-CLOSED: {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
