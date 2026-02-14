#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path


def _load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:
        raise ValueError(f"cannot load JSON {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return data


def _state_path(state_dir: Path, symbol: str) -> Path:
    return state_dir / f"prev_{symbol}.json"


def _extract_ohlc(snapshot: dict, item: dict, symbol: str) -> dict:
    timeframe = item.get("timeframe")
    if timeframe is not None and not isinstance(timeframe, str):
        raise ValueError(f"{symbol}: timeframe must be string when present")

    # prefer explicit ohlc block if provided
    ohlc = snapshot.get("ohlc")
    if isinstance(ohlc, dict):
        needed = ("open", "high", "low", "close", "volume")
        for k in needed:
            if k not in ohlc:
                raise ValueError(f"{symbol}: snapshot.ohlc.{k} missing")
            if not isinstance(ohlc[k], (int, float)):
                raise ValueError(f"{symbol}: snapshot.ohlc.{k} must be numeric")
        return {
            "open": float(ohlc["open"]),
            "high": float(ohlc["high"]),
            "low": float(ohlc["low"]),
            "close": float(ohlc["close"]),
            "volume": float(ohlc["volume"]),
        }

    # fallback: read per-timeframe close/price if available
    tfs = snapshot.get("timeframes")
    if timeframe and isinstance(tfs, dict):
        tf_obj = tfs.get(timeframe)
        if isinstance(tf_obj, dict):
            close = tf_obj.get("close", tf_obj.get("price"))
            if close is not None and not isinstance(close, (int, float)):
                raise ValueError(f"{symbol}: snapshot.timeframes[{timeframe}].close/price must be numeric")
            volume = tf_obj.get("volume")
            if volume is not None and not isinstance(volume, (int, float)):
                raise ValueError(f"{symbol}: snapshot.timeframes[{timeframe}].volume must be numeric when present")
            close_v = float(close) if close is not None else None
            return {
                "open": None,
                "high": None,
                "low": None,
                "close": close_v,
                "volume": float(volume) if volume is not None else None,
            }

    raise ValueError(f"{symbol}: cannot extract OHLC from snapshot")


def _fmt_num(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.4f}"


def _print_alert(symbol: str, alert_type: str, score: int, prev_score: int | None, risk: str, conf: float) -> None:
    prev = "n/a" if prev_score is None else str(prev_score)
    print(f"ALERT {symbol} {alert_type} score={score} prev={prev} risk={risk} conf={conf:.2f}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--summary-file", required=True)
    ap.add_argument("--state-dir", default="/tmp/metaos_domain_events/_state")
    args = ap.parse_args()

    try:
        summary = _load_json(Path(args.summary_file))
        items = summary.get("items")
        if not isinstance(items, list):
            raise ValueError("summary.items must be a list")

        state_dir = Path(args.state_dir)
        state_dir.mkdir(parents=True, exist_ok=True)

        print("SYMBOL | SCORE | DIR | RISK | CONF | OPEN | HIGH | LOW | CLOSE | VOLUME | TS")
        for item in items:
            if not isinstance(item, dict):
                raise ValueError("summary.items entries must be objects")
            symbol = item.get("symbol")
            score = item.get("score")
            direction = item.get("direction")
            risk_level = item.get("risk_level")
            confidence = item.get("confidence")
            ts_iso = item.get("ts_iso")
            snapshot_path = item.get("snapshot_path")

            if not isinstance(symbol, str) or not symbol:
                raise ValueError("item.symbol must be non-empty string")
            if not isinstance(score, int):
                raise ValueError(f"{symbol}: item.score must be int")
            if direction not in ("long", "short", "neutral", None):
                raise ValueError(f"{symbol}: item.direction invalid")
            if risk_level not in ("low", "medium", "high"):
                raise ValueError(f"{symbol}: item.risk_level invalid")
            if not isinstance(confidence, (int, float)):
                raise ValueError(f"{symbol}: item.confidence must be number")
            if not isinstance(ts_iso, str) or not ts_iso:
                raise ValueError(f"{symbol}: item.ts_iso must be non-empty string")
            if not isinstance(snapshot_path, str) or not snapshot_path:
                raise ValueError(f"{symbol}: item.snapshot_path must be non-empty string")

            snapshot = _load_json(Path(snapshot_path))
            ohlc = _extract_ohlc(snapshot, item, symbol)

            prev_path = _state_path(state_dir, symbol)
            prev_score: int | None = None
            prev_risk: str | None = None
            prev_conf: float | None = None
            if prev_path.exists():
                prev = _load_json(prev_path)
                prev_score = prev.get("score")
                prev_risk = prev.get("risk_level")
                prev_conf = prev.get("confidence")
                if not isinstance(prev_score, int):
                    raise ValueError(f"{symbol}: prev.score must be int")
                if prev_risk not in ("low", "medium", "high"):
                    raise ValueError(f"{symbol}: prev.risk_level invalid")
                if not isinstance(prev_conf, (int, float)):
                    raise ValueError(f"{symbol}: prev.confidence must be number")

            if prev_score is not None and abs(score - prev_score) >= 20:
                _print_alert(symbol, "SCORE_JUMP", score, prev_score, risk_level, float(confidence))
            if prev_risk is not None and prev_risk != "high" and risk_level == "high":
                _print_alert(symbol, "RISK_UP", score, prev_score, risk_level, float(confidence))
            if prev_conf is not None and (float(prev_conf) - float(confidence)) >= 0.20:
                _print_alert(symbol, "CONF_DROP", score, prev_score, risk_level, float(confidence))

            print(
                f"{symbol} | {score} | {direction or 'n/a'} | {risk_level} | {float(confidence):.2f} | "
                f"{_fmt_num(ohlc['open'])} | {_fmt_num(ohlc['high'])} | {_fmt_num(ohlc['low'])} | "
                f"{_fmt_num(ohlc['close'])} | {_fmt_num(ohlc['volume'])} | {ts_iso}"
            )

            prev_path.write_text(
                json.dumps(
                    {
                        "symbol": symbol,
                        "score": score,
                        "risk_level": risk_level,
                        "confidence": float(confidence),
                        "ts_iso": ts_iso,
                    },
                    ensure_ascii=False,
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
        return 0
    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
