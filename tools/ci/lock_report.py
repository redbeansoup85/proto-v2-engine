#!/usr/bin/env python3
import re
import sys
from pathlib import Path

if len(sys.argv) != 2:
    print("usage: lock_report.py <ci_log_path>")
    sys.exit(1)

log_path = Path(sys.argv[1])
t = log_path.read_text(encoding="utf-8", errors="ignore")

def first(pattern):
    m = re.search(pattern, t, re.M)
    return m.group(1) if m else "n/a"

def block_digest(marker):
    pat = rf"\[CI\] {re.escape(marker)}.*?(?=\n\[CI\]|\Z)"
    m = re.search(pat, t, re.S)
    if not m:
        return "n/a"
    b = m.group(0)
    m2 = re.search(r'^digest1 = ([0-9a-f]{64})$', b, re.M)
    return m2.group(1) if m2 else "n/a"

print("LOCK_REPORT")
print("policy_sha256 =", first(r"^A\.policy_sha256 = ([0-9a-f]{64})$"))
print("policy_capsule_digest =", first(r"^A\.policy_capsule\.digest = ([0-9a-f]{64})$"))
print("gate_same_digest =", first(r"^same1\.digest = ([0-9a-f]{64})$"))
print("plan_digest =", first(r"^plan\.digest\.1 = ([0-9a-f]{64})$"))
print("queue_digest =", first(r"^queue\.digest\.1 = ([0-9a-f]{64})$"))

print("processed_digest =", block_digest("LOCK5 consumer+audit determinism"))
print("orch_inbox_digest =", block_digest("LOCK6 orch inbox+audit determinism"))
print("orch_decision_digest =", block_digest("LOCK7 orch decision+audit determinism"))
print("outbox_item_digest =", block_digest("LOCK8 orch outbox+audit determinism"))
