from __future__ import annotations

import argparse
import json
from typing import Any, Dict

from core.C_action.queue_consumer import consume_pending


def main() -> None:
    ap = argparse.ArgumentParser(prog="consume_queue")
    ap.add_argument("--channel", default=None)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--base-dir", default="logs/queues")
    args = ap.parse_args()

    out = consume_pending(channel=args.channel, limit=args.limit, base_dir=args.base_dir)
    print(json.dumps({"consumed": len(out), "processed_paths": out}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
