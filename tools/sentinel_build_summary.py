#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


TS_RE = re.compile(r"^[0-9]{8}T[0-9]{6}Z$")


def _repo_root() -> Path:
    return Path(__file__).resolve().parent.parent


def _parse_symbols(raw: str) -> list[str]:
    parts = [item.strip() for item in raw.split(",")]
    symbols = [item for item in parts if item]
    if not symbols:
        raise ValueError("symbols must contain at least one symbol")
    if len(symbols) != len(set(symbols)):
        raise ValueError("symbols must not contain duplicates")
    return symbols


def _parse_tfs(raw: str) -> list[str]:
    tfs = [x.strip() for x in raw.split() if x.strip()]
    if not tfs:
        raise ValueError("tfs must contain at least one timeframe")
    if len(tfs) != len(set(tfs)):
        raise ValueError("tfs must not contain duplicates")
    return tfs


def _validate_domain_event(repo_root: Path, event_path: Path) -> None:
    proc = subprocess.run(
        [sys.executable, str(repo_root / "sdk" / "validate_domain_event.py"), str(event_path)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        detail = proc.stderr.strip() or proc.stdout.strip() or "unknown validation error"
        raise ValueError(f"domain_event invalid ({event_path}): {detail}")


def _build_sha(repo_root: Path) -> str:
    proc = subprocess.run(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    if proc.returncode != 0:
        return "n/a"
    sha = proc.stdout.strip()
    return sha if re.fullmatch(r"[a-fA-F0-9]{7,64}", sha) else "n/a"


def _extract_snapshot_path(event: dict, symbol: str, tf: str, ts: str) -> str:
    # prefer evidence_refs FILEPATH that looks like snapshot
    evidence_refs = event.get("evidence_refs")
    if isinstance(evidence_refs, list):
        for ref in evidence_refs:
            if not isinstance(ref, dict):
                continue
            if ref.get("ref_kind") == "FILEPATH":
                candidate = ref.get("ref")
                if isinstance(candidate, str) and "/tmp/metaos_snapshots/" in candidate and "snapshot_" in candidate:
                    return candidate

    # fallback to our known path convention
    return f"/tmp/metaos_snapshots/{symbol}_{tf}/snapshot_{ts}.json"


def _read_leg(domain_root: Path, repo_root: Path, symbol: str, tf: str, ts: str) -> dict:
    # support both naming conventions just in case
    p1 = domain_root / symbol / f"domain_event_{ts}_{tf}.json"
    p2 = domain_root / symbol / f"domain_event_{ts}.json"  # legacy
    event_path = p1 if p1.exists() else p2
    if not event_path.exists():
        raise ValueError(f"missing domain_event file: {p1}")

    _validate_domain_event(repo_root, event_path)
    event = json.loads(event_path.read_text(encoding="utf-8"))

    signal = event.get("signal")
    if not isinstance(signal, dict):
        raise ValueError(f"signal must be object in {event_path}")

    leg = {
        "symbol": signal.get("symbol"),
        "timeframe": signal.get("timeframe") or tf,
        "ts_iso": event.get("ts_iso"),
        "score": signal.get("score"),
        "direction": signal.get("direction"),
        "risk_level": signal.get("risk_level"),
        "confidence": signal.get("confidence"),
        "snapshot_path": _extract_snapshot_path(event, symbol, tf, ts),
        "domain_event_path": str(event_path),
    }

    if leg["symbol"] != symbol:
        raise ValueError(f"symbol mismatch in {event_path}: expected {symbol}, got {leg['symbol']}")
    if not isinstance(leg["ts_iso"], str) or not leg["ts_iso"]:
        raise ValueError(f"invalid ts_iso in {event_path}")
    if not isinstance(leg["score"], int):
        raise ValueError(f"invalid score in {event_path}")
    if leg["direction"] not in (None, "long", "short", "neutral"):
        raise ValueError(f"invalid direction in {event_path}")
    if leg["risk_level"] not in ("low", "medium", "high"):
        raise ValueError(f"invalid risk_level in {event_path}")
    if not isinstance(leg["confidence"], (int, float)):
        raise ValueError(f"invalid confidence in {event_path}")
    if not isinstance(leg["snapshot_path"], str) or not leg["snapshot_path"]:
        raise ValueError(f"invalid snapshot_path in {event_path}")

    return leg



def _safe_num(v):
    return float(v) if isinstance(v, (int, float)) else None


def _load_snapshot_ohlc(snapshot_path: str) -> dict:
    try:
        snap = json.loads(Path(snapshot_path).read_text(encoding="utf-8"))
        if not isinstance(snap, dict):
            return {}
        # accept either flat keys or nested ohlc
        if isinstance(snap.get("ohlc"), dict):
            o = snap["ohlc"]
            return {
                "open": _safe_num(o.get("open")),
                "high": _safe_num(o.get("high")),
                "low": _safe_num(o.get("low")),
                "close": _safe_num(o.get("close")),
                "volume": _safe_num(o.get("volume")),
            }
        return {
            "open": _safe_num(snap.get("open")),
            "high": _safe_num(snap.get("high")),
            "low": _safe_num(snap.get("low")),
            "close": _safe_num(snap.get("close")),
            "volume": _safe_num(snap.get("volume")),
        }
    except Exception:
        return {}


def _range_pct_ohlc(ohlc: dict) -> float | None:
    o = ohlc.get("open")
    h = ohlc.get("high")
    l = ohlc.get("low")
    if o is None or h is None or l is None or o == 0:
        return None
    return (h - l) / o * 100.0


def _extract_oi_delta_pct(leg: dict) -> float | None:
    # try to find oi delta in leg extras if present
    # (we keep it permissive: if field not present -> None)
    for k in ("oi_delta_pct", "oiΔ_pct", "oi_delta"):
        v = leg.get(k)
        if isinstance(v, (int, float)):
            return float(v)
    # common place: leg["metrics"]["oi_delta_pct"]
    m = leg.get("metrics")
    if isinstance(m, dict) and isinstance(m.get("oi_delta_pct"), (int, float)):
        return float(m["oi_delta_pct"])
    return None


def _risk_dynamic_stable(cons: dict, leg_15m: dict | None, leg_1h: dict | None) -> str:
    # Conservative: only elevate to high on 2-of-4 confirmations.
    if cons.get("final_direction") not in ("long", "short"):
        return str(cons.get("final_risk_level", "medium"))

    score = int(cons.get("final_score", 0))

    oi15 = _extract_oi_delta_pct(leg_15m or {})
    cond_score = score >= 80
    cond_oi = (oi15 is not None) and (abs(oi15) >= 0.03)

    # 1h volatility range%
    rp = None
    if leg_1h and isinstance(leg_1h.get("snapshot_path"), str):
        ohlc = _load_snapshot_ohlc(leg_1h["snapshot_path"])
        rp = _range_pct_ohlc(ohlc)
        vol = ohlc.get("volume")
    else:
        vol = None

    cond_range = (rp is not None) and (rp >= 0.25)

    # Volume spike v1: if we have current volume only, cannot confirm spike -> False
    # (We keep conservative; later we'll add prev-volume state)
    cond_vol_spike = False

    hits = sum([cond_score, cond_oi, cond_range, cond_vol_spike])
    return "high" if hits >= 2 else "medium"



def _consensus_stable(leg_15m: dict | None, leg_1h: dict | None) -> dict:
    # Conservative / structure-stable consensus + dynamic risk (stable v1)

    final = {
        "final_score": 60,
        "final_direction": "neutral",
        "final_risk_level": "medium",
        "final_confidence": 0.55,
        "final_snapshot_path": (leg_1h or leg_15m or {}).get("snapshot_path"),
    }

    if not leg_15m or not leg_1h:
        return final

    d15, d1 = leg_15m.get("direction"), leg_1h.get("direction")
    s15, s1 = int(leg_15m.get("score", 0)), int(leg_1h.get("score", 0))
    c15, c1 = float(leg_15m.get("confidence", 0.55)), float(leg_1h.get("confidence", 0.55))

    trigger_ok = s15 >= 75 and d15 in ("long", "short")
    structure_ok = d1 == d15 and s1 >= 65

    if trigger_ok and structure_ok:
        final_dir = d15
        final_score = int(round((s15 + s1) / 2))
        final_conf = min(c15, c1) + 0.05
        if final_conf > 1.0:
            final_conf = 1.0

        base_risk = "high" if (s15 >= 85 and s1 >= 75) else "medium"

        final.update(
            {
                "final_score": final_score,
                "final_direction": final_dir,
                "final_risk_level": base_risk,
                "final_confidence": float(final_conf),
                "final_snapshot_path": leg_15m.get("snapshot_path") or leg_1h.get("snapshot_path"),
            }
        )

    # ---- dynamic risk (stable v1): 2-of-3 confirmations ----
    if final["final_direction"] in ("long", "short"):
        cond_score = final["final_score"] >= 80

        # OI delta: optional (if present in leg["metrics"]["oi_delta_pct"])
        oi15 = None
        m15 = leg_15m.get("metrics") if isinstance(leg_15m, dict) else None
        if isinstance(m15, dict) and isinstance(m15.get("oi_delta_pct"), (int, float)):
            oi15 = float(m15["oi_delta_pct"])
        cond_oi = (oi15 is not None) and (abs(oi15) >= 0.03)

        # 1h range%
        cond_range = False
        try:
            import json
            from pathlib import Path as _P
            snap_path = leg_1h.get("snapshot_path")
            if isinstance(snap_path, str) and snap_path:
                snap = json.loads(_P(snap_path).read_text(encoding="utf-8"))
                ohlc = snap.get("ohlc", snap)
                o = ohlc.get("open"); h = ohlc.get("high"); l = ohlc.get("low")
                if isinstance(o, (int, float)) and isinstance(h, (int, float)) and isinstance(l, (int, float)) and o != 0:
                    rp = (h - l) / o * 100.0
                    cond_range = rp >= 0.25
        except Exception:
            cond_range = False

        hits = sum([cond_score, cond_oi, cond_range])
        final["final_risk_level"] = "high" if hits >= 2 else "medium"

    return final
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--ts", required=True, help="UTC yyyymmddTHHMMSSZ")
    ap.add_argument("--symbols", required=True, help="comma-separated symbols")
    ap.add_argument("--tfs", default="15m 1h", help="space-separated timeframes (default: '15m 1h')")
    ap.add_argument("--domain-root", default="/tmp/metaos_domain_events")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    if not TS_RE.fullmatch(args.ts):
        print("FAIL-CLOSED: --ts must match yyyymmddTHHMMSSZ")
        return 1

    try:
        symbols = _parse_symbols(args.symbols)
        tfs = _parse_tfs(args.tfs)
        repo_root = _repo_root()
        domain_root = Path(args.domain_root)

        items: list[dict] = []
        for symbol in symbols:
            legs: dict[str, dict] = {}
            for tf in tfs:
                legs[tf] = _read_leg(domain_root, repo_root, symbol, tf, args.ts)

            leg_15m = legs.get("15m")
            leg_1h = legs.get("1h")

            cons = _consensus_stable(leg_15m, leg_1h)

            # Backward-compatible item fields used by console_dashboard:
            # symbol/ts_iso/score/direction/risk_level/confidence/snapshot_path/domain_event_path
            # -> map to final values
            ts_iso = (leg_1h or leg_15m)["ts_iso"]
            item = {
                "symbol": symbol,
                "ts_iso": ts_iso,
                "score": int(cons["final_score"]),
                "direction": cons["final_direction"],
                "risk_level": cons["final_risk_level"],
                "confidence": float(cons["final_confidence"]),
                "snapshot_path": cons["final_snapshot_path"],
                "domain_event_path": (leg_1h or leg_15m)["domain_event_path"],
                # extras
                "legs": legs,
                "final": cons,
            }

            # apply consensus FINAL -> item (dashboard reads item fields)
            if isinstance(leg_15m, dict) and isinstance(leg_1h, dict):
                final = _consensus_stable(leg_15m, leg_1h)
                if isinstance(final, dict):
                    item["score"] = int(final.get("final_score", item.get("score", 60)))
                    item["direction"] = final.get("final_direction", item.get("direction", "neutral"))
                    item["risk_level"] = final.get("final_risk_level", item.get("risk_level", "medium"))
                    item["confidence"] = float(final.get("final_confidence", item.get("confidence", 0.55)))
            if not isinstance(item["snapshot_path"], str) or not item["snapshot_path"]:
                raise ValueError(f"{symbol}: final snapshot_path missing")

            items.append(item)

        summary = {
            "schema": "sentinel_summary.v0",
            "ts": args.ts,
            "symbols": symbols,
            "tfs": tfs,
            "items": items,
            "meta": {"build_sha": _build_sha(repo_root), "mode": "consensus_stable_v1"},
        }

        out_path = Path(args.out)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"OK: wrote {out_path}")
        return 0

    except Exception as exc:
        print(f"FAIL-CLOSED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
