# Operational Pack — Learning→Policy Governance

**Version:** 1.0  
**Status:** LOCKED  
**Binding Level:** L3 (Constitution-Bound Operational Pack)  
**Depends on:**
- Constitution (L4), Section AQ — Approval Queue
- Operational Canon — Learning → Policy Cycle v1.0

---

## Part 1 — Proposal Schema (v1.0)

### 1. Purpose

This schema defines the minimum required structure for any proposal emitted by Learning OS (or Human Operator) that may enter the Approval Queue.

Approval Queue evaluates structure, baselines, and conflicts. It does not assess policy quality.

---

### 2. Proposal Envelope (JSON)

```json
{
  "proposal_id": "uuid",
  "proposal_type": "policy_patch",
  "source": {
    "kind": "learning|human|external",
    "name": "string",
    "run_id": "string",
    "created_at": "iso8601"
  },
  "scope": {
    "domain": "string",
    "subsystem": "string",
    "severity": "low|medium|high",
    "blast_radius": "local|service|system|external"
  },
  "preconditions": {
    "constitution": {
      "required_sections": ["AQ"],
      "constitution_hash": "string"
    },
    "observation_window": {
      "mode": "time|events",
      "t_window": "string",
      "n_events": 0
    },
    "sample": {
      "n_min": 0,
      "n_observed": 0
    },
    "stability": {
      "k_confirmations": 0,
      "epsilon": 0.0,
      "summary": "string"
    }
  },
  "baseline": {
    "policy_snapshot_id": "string",
    "policy_hash": "string"
  },
  "patch": {
    "format": "jsonpatch|mergepatch|custom",
    "content": []
  },
  "explain": {
    "current_policy_summary": "string",
    "proposed_policy_summary": "string",
    "rationale": "string",
    "expected_impact": "string",
    "rollback_scope": "string",
    "risks": ["string"],
    "assumptions": ["string"],
    "evidence_refs": ["string"]
  },
  "rate_limit": {
    "period": "string",
    "limit_x": 0,
    "cooldown": "string",
    "rest_required": false
  },
  "human_gate": {
    "required": false,
    "reasons": ["string"]
  }
}
### 3. Field Rules (Normative)

- `proposal_id` must be globally unique.
- `source.kind` ∈ {learning, human, external}.
- `scope.blast_radius` must be conservative.
- `preconditions` must be present and internally consistent.
- `baseline.policy_hash` must match policy state at proposal time.
- `patch.content` must be deterministic and serializable.
- All `explain.*` fields are mandatory.
- `human_gate.required` must be true when any Human Gate condition triggers.

---

## Part 2 — Human Approval Gate Checklist (v1.0)

If any item below is **YES**:

- `human_gate.required = true`
- proposal must not be auto-approved.

### A. Blast Radius Expansion

- local → service / system / external
- domain or applicability expansion

### B. Rollback Cost Increase

Rollback requires:

- data migration
- multi-service coordination
- downtime
- irreversible consequences

### C. External / Real-World Effect

- affects users, customers, or real-world operations
- outputs could be treated as instructions

### D. Safety / Compliance / Reputation

- safety risk
- legal exposure
- reputational damage
- privacy risk

### E. Governance-Sensitive Change

- evaluation order
- logging semantics
- rate-limit semantics
- responsibility boundaries

---

### Operator Decision Record (Required)

When Human Gate triggers, operator must record:

- decision: approve | reject | defer
- rationale (1–3 bullets)
- risk acceptance (if approved)
- rollback confirmation (if approved)

---

## Part 3 — Canon Index (v1.0)

| Layer | Artifact | Status | Purpose | Change Control |
| --- | --- | --- | --- | --- |
| L4 | Constitution — Section AQ | LOCKED | Fix responsibility & evaluation order | Constitutional amendment only |
| L3 | Operational Canon — Learning→Policy Cycle v1.0 | LOCKED | Proposal eligibility & rate limits | Canon revision |
| L3 | Operational Pack — Learning→Policy Governance v1.0 | LOCKED | Schema + human gate + index | Pack revision |

---

## Lock Statement

**LOCKED — Operational Pack v1.0**

