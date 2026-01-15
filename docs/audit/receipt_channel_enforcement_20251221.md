# 2025-12-21 — Receipt Channel Enforcement

- Migration ID: receipt_channel_injection_20251221
- Purpose: Enforce explicit channel routing (unknown queue disabled)
- Method: Copy-on-write migration with full backup
- Result:
  - Total receipts: 5
  - Patched: 1
  - Already compliant: 4
- Artifact:
  - Runtime: logs/migrations/
  - Versioned (repo): docs/audit/

Rationale:
Routing keys must originate from explicit metadata (meta.channel).
evidence.channel is deprecated and only permitted in controlled recovery mode.
