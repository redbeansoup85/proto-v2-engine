# Verification Factory — Threat Model

This document maps common AI-assisted development threats
to structural mitigations in the Verification Factory.

---

## Threat → Mitigation Matrix

| Threat | Description | Mitigation |
|------|------------|-----------|
| Prompt Injection via Code | Malicious code attempts to exfiltrate data or alter behavior | Air-gapped execution, no network access, isolated worktrees |
| Test Poisoning | AI modifies tests to force PASS | No-touch zones; tests mounted read-only |
| Path Traversal | Patch targets unintended files | Strict diff path normalization + denylist |
| Resource Exhaustion | Infinite loops, memory abuse | Wall-clock timeouts, resource limits |
| Non-repudiation Failure | Cannot prove who approved what | Append-only approval ledger + hash linkage |
| Evidence Tampering | Artifacts modified post-hoc | Content-addressed bundles + schema validation |
| Authority Escalation | AI triggers apply/merge | Explicit human approval gate, no auto-exec |
| Silent Drift | Changes merged without context | PR package + merge gate enforcement |

---

## Design Assumption

Threats are assumed to be:
- Accidental **or**
- Adversarial **or**
- Emergent from probabilistic behavior

The system does not distinguish intent—only structure.

---

## Out-of-Scope

- Runtime application security
- Production deployment controls
- Model training or prompt safety

---

End of document.
