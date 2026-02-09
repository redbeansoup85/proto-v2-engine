# LOCK-4 Replay Store

This store provides a single-writer, append-only replay guard.

## Contract
- Stored under `var/security/` only.
- Fingerprint collisions are rejected (fail-closed).
- Crash after write is safe (append-only).

## Usage

```bash
python tools/lock4_replay_store.py \
  --path var/security/replay_store.jsonl \
  --fingerprint <64-hex>
```

## Notes
- This tool does not alter execution semantics.
- Integration with runtime is intentionally deferred.
