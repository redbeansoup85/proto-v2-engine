# Audit Event Schema (JSONL)

## Purpose
This schema defines the minimal, immutable audit contract
for ExecutionEnvelope-governed runtime decisions.

Each line represents exactly one event.

---

## Required Fields (Immutable)

| field | type | description |
|------|------|-------------|
| event | string | mint \| enforce \| deny |
| outcome | string | allow \| deny |
| approval_id | string | external approval identifier |
| envelope_id | string | execution envelope identifier |
| authority_id | string | authority / policy source |
| issued_at | string (ISO-8601) | envelope issued timestamp |
| expires_at | string (ISO-8601) | envelope expiry timestamp |
| recorded_at | string (ISO-8601) | audit write time |

---

## Optional Fields

| field | type | description |
|------|------|-------------|
| reason_codes | array[string] | denial or warning reasons |
| request_id | string | inbound request correlation |
| route | string | API route |
| actor | string | human / system actor |
| error | string | audit sink error (if any) |

---

## Invariants

1. Missing required field = schema violation
2. Audit failure must not change execution outcome
3. deny events must always include outcome=deny
4. Schema changes require governance review
