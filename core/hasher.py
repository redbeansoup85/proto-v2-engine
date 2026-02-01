from __future__ import annotations

import hashlib
from typing import Any, Dict, Optional

from .canonical_json import canonical_json


US = "\x1F"  # Unit Separator


def _sha256_bytes(b: bytes) -> str:
    return "sha256:" + hashlib.sha256(b).hexdigest()


def compute_payload_hash(payload: Dict[str, Any]) -> str:
    """
    payload_hash = sha256(UTF-8(canonical_json(payload)))
    """
    return _sha256_bytes(canonical_json(payload))


def artifact_refs_fingerprint(artifact_refs: Dict[str, Optional[str]]) -> str:
    """
    Deterministic fingerprint from LOCKED artifact_refs keys (fixed order).
    Represent null as empty string. Include key names to avoid ambiguity.
    """
    order = ["execution_card_id", "parent_card_id", "policy_id", "run_id", "approval_id"]
    parts = []
    for k in order:
        v = artifact_refs.get(k)
        parts.append(f"{k}={'' if v is None else v}")
    return US.join(parts)


def compute_event_id(
    *,
    event_type: str,
    system_id: str,
    domain: str,
    asset_or_subject_id: str,
    chain_snapshot_id: str,
    sequence_no: int,
    artifact_refs: Dict[str, Optional[str]],
    payload_hash: str,
) -> str:
    """
    Deterministic event_id (Option A): occurred_at excluded.
    Inputs (US-separated):
      event_type | system_id | domain | asset_or_subject_id | chain_snapshot_id | sequence_no | artifact_refs_fingerprint | payload_hash
    """
    fp = artifact_refs_fingerprint(artifact_refs)
    raw = US.join(
        [
            event_type,
            system_id,
            domain,
            asset_or_subject_id,
            chain_snapshot_id,
            str(sequence_no),
            fp,
            payload_hash,
        ]
    ).encode("utf-8")
    return _sha256_bytes(raw)


def compute_chain_hash(
    *,
    prev_chain_hash: Optional[str],
    event_id: str,
    payload_hash: str,
    schema_hash: str,
) -> str:
    """
    chain_hash = sha256(prev_chain_hash | event_id | payload_hash | schema_hash) using US separator.
    If prev_chain_hash is None, omit it.
    """
    parts = [event_id, payload_hash, schema_hash] if prev_chain_hash is None else [prev_chain_hash, event_id, payload_hash, schema_hash]
    return _sha256_bytes(US.join(parts).encode("utf-8"))
