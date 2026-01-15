## Meta OS v1.0 — Constitutional Boundary (Locked)

### Scope
Meta OS v1.0 is a judgment-support system.
It does not execute actions. It produces artifacts only.

### Gate-1: Responsibility Acceptance
- A human actor must explicitly ACCEPT responsibility.
- Output is an accountability artifact only.
- No execution occurs at this gate.

### Gate-2: Execution Authorization
- Applies to execution-class channels:
  `trading`, `ops_exec`, `automation`, `live`
- Requires a valid ExecutionAuthorizationRequest.
- Invariants:
  - auto_action MUST be false
  - responsibility.decision MUST be ACCEPT
  - judgment_ref MUST match the source receipt path
- Absence or invalidity hard-fails plan construction.

### Execution Boundary (Hard)
- Meta OS never executes.
- Queue consumption produces artifacts only.
- Processed records must show:
  - action_executed = false
  - delivery_status.mode = ARTIFACT_ONLY

### Routing Boundary
- Unknown queue is disabled.
- channel is mandatory and must be explicit.

### Evidence of Compliance
Compliance is proven by runtime artifacts under:
- logs/queues/*/processed/
- logs/outbox/execution_requests/

### Out of Scope (v1.0)
- Executors
- Auto-forwarding to external systems
- Autonomous action loops

This boundary is locked for v1.0.
All further automation is deferred to v2.0.
