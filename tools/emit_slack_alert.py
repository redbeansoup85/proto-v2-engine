#!/usr/bin/env python3
import argparse
import json
import os
import sys
import urllib.request

def _fail(msg: str):
    print(f"FAIL-CLOSED: {msg}")
    sys.exit(1)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--outbox-item", required=True)
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    webhook = os.getenv("SLACK_WEBHOOK_URL")
    if not webhook and not args.dry_run:
        _fail("SLACK_WEBHOOK_URL not set")

    with open(args.outbox_item, "r", encoding="utf-8") as f:
        d = json.load(f)

    text = (
        f"[Meta-OS] {d.get('schema')}\n"
        f"- channel: {d.get('channel')}\n"
        f"- plan_id: {d.get('plan_id')}\n"
        f"- decision_ref: {d.get('decision_ref')}\n"
        f"- outbox_item_sha256: {d.get('outbox_item_sha256')}\n"
        f"- payload: {json.dumps(d.get('delivery',{}), ensure_ascii=False)}"
    )

    if args.dry_run:
        print("DRY_RUN: would POST to slack")
        print(text)
        return

    body = json.dumps({"text": text}).encode("utf-8")
    req = urllib.request.Request(
        webhook,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status < 200 or resp.status >= 300:
                _fail(f"slack non-2xx: {resp.status}")
            print("OK: slack posted")
    except Exception as e:
        _fail(f"slack post failed: {e}")

if __name__ == "__main__":
    main()
