# Verification Factory — Terminology

This document defines canonical terms used throughout the system.
Terms are normative.

---

## Status Terms

- **PASS**  
  Automated verification succeeded.

- **PROPOSED**  
  Eligible for human decision. No authority granted.

- **APPROVED**  
  Explicit human authorization recorded.

- **READY_FOR_PR**  
  Applied and re-verified in isolation.

---

## Structural Terms

- **Verification Factory**  
  Automated system that verifies but never applies changes.

- **Evidence Bundle**  
  Immutable collection of artifacts proving a state transition.

- **Approval Ledger**  
  Append-only record of human decisions.

- **No-Touch Zones**  
  Paths that AI-generated patches may never modify.

- **Fail-Closed**  
  Missing or invalid data halts progress.

- **Isolation**  
  All execution occurs in detached worktrees or equivalent.

---

## Non-Terms (Explicitly Excluded)

- Autonomous deployment
- Implicit approval
- Trust-based verification
- Best-effort safety

---

End of document.
