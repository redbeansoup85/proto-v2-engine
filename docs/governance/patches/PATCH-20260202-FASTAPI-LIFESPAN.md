# 🔒 LOCKDOC — Patch Record (FastAPI lifespan migration)

## 1) Metadata (Immutable)

```yaml
DOCUMENT_ID: LOCKDOC-PATCH-FASTAPI-LIFESPAN-v1.0
SYSTEM: Proto Meta Engine v2 / proto-v2-engine
SCOPE: Runtime lifecycle / framework deprecation hardening
STATUS: LOCKED
MUTABILITY: FORBIDDEN
TIMEZONE: Australia/Sydney
EFFECTIVE_DATE: 2026-02-02
CHANGE_TYPE: A-PATCH
RISK: low
BEHAVIOR_CHANGE: none (expected)

2) Change Summary

Replace deprecated FastAPI on_event usage with lifespan handler.

Goal: deprecation hardening without behavior change.

3) Verification

CI: proto-v2-engine-ci (main push) PASS

Local:

./scripts/lock/phase1_verify.sh : PASS

./scripts/lock/phase2_verify.sh : PASS

4) References

PR: #21

Commit: bd636de

Tag: LOCKDOC-PATCH-20260202-FASTAPI-LIFESPAN

CI Run: 21569973947
```
