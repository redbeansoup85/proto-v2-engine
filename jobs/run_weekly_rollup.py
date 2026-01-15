from __future__ import annotations

import os
import json
import argparse

from core.analytics.weekly import load_scene_summaries_jsonl, rollup_weekly


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--path", default="data/audit/scene_summaries.jsonl")
    ap.add_argument("--days", type=int, default=7)
    args = ap.parse_args()

    if not os.path.exists(args.path):
        print(json.dumps({"ok": False, "error": "file not found", "path": args.path}, indent=2))
        return 1

    items = load_scene_summaries_jsonl(args.path)
    rollup = rollup_weekly(items, days=args.days)
    print(json.dumps(rollup.__dict__, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
