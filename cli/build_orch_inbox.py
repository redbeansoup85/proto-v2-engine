from __future__ import annotations

import argparse
import glob
import json
import os
from typing import List, Optional

from core.C_action.orch_payload import write_inbox_payload


def main() -> None:
    ap = argparse.ArgumentParser(prog="build_orch_inbox")
    ap.add_argument("--channel", default=None)
    ap.add_argument("--limit", type=int, default=50)
    ap.add_argument("--processed-base-dir", default="logs/queues")
    ap.add_argument("--inbox-base-dir", default="logs/orchestrator/inbox")
    args = ap.parse_args()

    if args.channel:
        pattern = os.path.join(args.processed_base_dir, args.channel, "processed", "*.json")
    else:
        pattern = os.path.join(args.processed_base_dir, "*", "processed", "*.json")

    paths = sorted(glob.glob(pattern), key=os.path.getmtime)[: max(0, int(args.limit))]
    out: List[str] = []
    for p in paths:
        out.append(write_inbox_payload(p, inbox_base_dir=args.inbox_base_dir))

    print(json.dumps({"written": len(out), "inbox_paths": out}, ensure_ascii=False, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
