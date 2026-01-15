from __future__ import annotations

import os
import json
import argparse

from core.analytics.weekly import load_scene_summaries_jsonl
from core.analytics.insight_cards import build_weekly_insight_card


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/audit/scene_summaries.jsonl")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    if not os.path.exists(args.path):
        card = build_weekly_insight_card([], days=args.days)
        print(json.dumps(card.__dict__, indent=2))
        return 0

    items = load_scene_summaries_jsonl(args.path)
    card = build_weekly_insight_card(items, days=args.days)
    print(json.dumps(card.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
