from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .hasher import compute_chain_hash
from .validator import validate_core_event_fail_closed


def walk_and_verify_chain(
    events: List[Dict[str, Any]],
    *,
    strict_contiguous: bool = True,
    verify_chain_hash_if_present: bool = True,
) -> List[Tuple[int, bool, str]]:
    if not events:
        return [(0, False, "empty chain")]

    results: List[Tuple[int, bool, str]] = []
    seen_snapshot: Optional[str] = None
    expected_seq = 1
    prev_event_id: Optional[str] = None
    prev_chain_hash: Optional[str] = None

    for i, ev in enumerate(events):
        ok, msg = validate_core_event_fail_closed(ev)
        if not ok:
            results.append((i, False, msg))
            continue

        env = ev["event_envelope"]
        chain = env["chain"]
        integ = env["integrity"]

        snapshot = chain["chain_snapshot_id"]
        if seen_snapshot is None:
            seen_snapshot = snapshot
        elif snapshot != seen_snapshot:
            results.append((i, False, f"chain_snapshot_id changed: {seen_snapshot} -> {snapshot}"))
            continue

        seq = chain["sequence_no"]
        if strict_contiguous and seq != expected_seq:
            results.append((i, False, f"sequence_no non-contiguous: expected {expected_seq}, got {seq}"))
        expected_seq += 1

        if i == 0:
            if chain.get("prev_event_id") is not None:
                results.append((i, False, "genesis prev_event_id must be null"))
        else:
            if chain.get("prev_event_id") != prev_event_id:
                results.append((i, False, f"prev_event_id mismatch: expected {prev_event_id}, got {chain.get('prev_event_id')}"))

        if verify_chain_hash_if_present and "chain_hash" in integ:
            computed = compute_chain_hash(
                prev_chain_hash=prev_chain_hash,
                event_id=env["event_id"],
                payload_hash=integ["payload_hash"],
                schema_hash=integ["schema_hash"],
            )
            if integ["chain_hash"] != computed:
                results.append((i, False, f"chain_hash mismatch (computed {computed})"))

        prev_event_id = env["event_id"]
        prev_chain_hash = integ.get("chain_hash") if "chain_hash" in integ else prev_chain_hash

        results.append((i, True, "ok"))

    return results
