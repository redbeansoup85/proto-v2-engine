# 2025-12-21 — Receipt Channel Enforcement Migration

## Migration ID
receipt_channel_injection_20251221

## Purpose
Enforce explicit channel routing policy.
- Single Source of Truth: receipt.meta.channel
- unknown queue permanently disabled
- evidence.channel forbidden by default (recovery mode only)

## Method
Copy-on-write migration with full pre-migration backup.

## Results
- Total receipts: 5
- Patched: 1
- Already compliant: 4

## Runtime Audit Artifacts (gitignored)
- logs/migrations/receipt_channel_injection_20251221_*.json
- logs/migrations/backups/receipt_channel_injection_20251221/

## Policy Declaration
- Routing keys MUST originate from receipt.meta.channel
- receipt.channel allowed only for legacy compatibility (deprecated)
- evidence.channel is FORBIDDEN unless METAOS_LEGACY_EVIDENCE_CHANNEL_OK=1
