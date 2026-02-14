# Domain Modules (Meta OS v3.x)

## Core vs Domain

Core (immutable baseline layer):
- Audit Chain
- Gate Engine
- Policy
- Deterministic Capsule

Domain Modules (expandable layer):
- Sentinel (trading domain)
- Auralis (safety domain)
- Future domains

## Sentinel (v3.2 status)

Current implementation lives under:
- tools/
- scripts/

This is temporary.

Planned structure (future PR, not in this change):

domains/
    sentinel/
        adapters/
        signals/
        emit/
        cli/

Important:
- Domain modules MUST emit domain_event.v1
- Core must remain domain-agnostic
- No direct modification of core audit/gate for domain logic
