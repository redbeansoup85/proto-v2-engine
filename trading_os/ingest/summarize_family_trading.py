from __future__ import annotations

import json
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Tuple, Optional


INBOX = Path("vault/inbox/family_trading/trading_outcomes.jsonl")
OUT_DIR = Path("vault/learning/family_trading")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def iso_z(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def read_jsonl(path: Path) -> List[Dict[str, Any]]:
    if not path.exists():
        return []
    out: List[Dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if isinstance(obj, dict):
                out.append(obj)
        except Exception:
            # ignore malformed lines; no inference
            continue
    return out


def median(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    mid = n // 2
    if n % 2 == 1:
        return float(s[mid])
    return float((s[mid - 1] + s[mid]) / 2.0)


def safe_float(x: Any) -> Optional[float]:
    try:
        if x is None or x == "":
            return None
        return float(x)
    except Exception:
        return None


def safe_int(x: Any) -> Optional[int]:
    try:
        if x is None or x == "":
            return None
        return int(float(x))
    except Exception:
        return None


def summarize(rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    # group by (asset, timeframe, scene_label)
    groups: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = defaultdict(list)

    for r in rows:
        asset = str(r.get("asset") or "UNKNOWN").upper()
        tf = str(r.get("timeframe") or "n/a")
        env = r.get("environment") or {}
        scene = str((env.get("scene_label") if isinstance(env, dict) else None) or "n/a")
        groups[(asset, tf, scene)].append(r)

    out_rows: List[Dict[str, Any]] = []

    for (asset, tf, scene), items in sorted(groups.items(), key=lambda x: (x[0][0], x[0][1], x[0][2])):
        pos = neg = flat = unk = 0
        mae_vals: List[float] = []
        mfe_vals: List[float] = []
        hold_vals: List[int] = []

        for it in items:
            oc = it.get("outcome") or {}
            if not isinstance(oc, dict):
                oc = {}

            rc = str(oc.get("result_class") or "unknown").lower()
            if rc == "positive":
                pos += 1
            elif rc == "negative":
                neg += 1
            elif rc == "flat":
                flat += 1
            else:
                unk += 1

            mae = safe_float(oc.get("max_adverse_excursion_pct"))
            mfe = safe_float(oc.get("max_favorable_excursion_pct"))
            hm = safe_int(oc.get("holding_minutes"))

            if mae is not None:
                mae_vals.append(mae)
            if mfe is not None:
                mfe_vals.append(mfe)
            if hm is not None:
                hold_vals.append(hm)

        total = len(items)
        win_rate = (pos / total) if total else None

        out_rows.append({
            "asset": asset,
            "timeframe": tf,
            "scene_label": scene,
            "n": total,
            "results": {"positive": pos, "negative": neg, "flat": flat, "unknown": unk},
            "win_rate": win_rate,  # purely descriptive; NOT a recommendation
            "mae": {"median_pct": median(mae_vals), "count": len(mae_vals)},
            "mfe": {"median_pct": median(mfe_vals), "count": len(mfe_vals)},
            "holding_minutes": {"median": median([float(x) for x in hold_vals]) if hold_vals else None, "count": len(hold_vals)},
        })

    return {
        "schema": "family_trading_summary.v1",
        "generated_at": iso_z(datetime.now(timezone.utc)),
        "source_file": str(INBOX),
        "total_records": len(rows),
        "by_group": out_rows,
        "notes": "Descriptive summary only. No directional guidance or execution instructions.",
    }


def main() -> int:
    rows = read_jsonl(INBOX)
    summary = summarize(rows)

    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_path = OUT_DIR / f"summary__{stamp}.json"
    out_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")

    print(f"inbox_records={len(rows)}")
    print(f"written={out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
