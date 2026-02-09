# LOCK-4 Operations Runbook (Runtime)

This document describes how to operate LOCK-4 runtime enforcement safely.

## Goals
- Default to `warn` unless explicitly promoted.
- Fail-fast in `enforce` mode when preflight fails.
- Never embed private keys in the repo.

## Environment

### Runtime mode resolution
- If `LOCK4_SIG_MODE` is unset: `warn`
- If `LOCK4_SIG_MODE=enforce` and `LOCK4_PROMOTE_ENFORCE` is not set/truthy: `warn`
- If `LOCK4_SIG_MODE=enforce` and `LOCK4_PROMOTE_ENFORCE=1|true|yes|y|on`: `enforce`

### Required variables (runtime verifier)
- `LOCK4_SIG_MODE`
- `LOCK4_PROMOTE_ENFORCE`
- `LOCK4_KEYRING_PATH`
- `LOCK4_REPLAY_DB_PATH`
- `LOCK4_CLOCK_SKEW_SECONDS` (optional, default 300)

### Writer variables (producer)
- `LOCK4_ACTOR_ID`
- `LOCK4_KEY_ID`
- `LOCK4_SIGNING_KEY_PATH`

## Preflight

Run preflight before enabling enforce:

```bash
python tools/lock4_preflight.py --mode enforce --verifier
```

- In enforce: preflight failure is fatal.
- In warn: preflight failure logs a warning but continues.

## Promote procedure
1) Run in warn and observe zero signature failures.
2) Set `LOCK4_SIG_MODE=enforce` and `LOCK4_PROMOTE_ENFORCE=1`.
3) Ensure preflight passes and runtime starts cleanly.

## Rollback
- Set `LOCK4_SIG_MODE=warn` or unset `LOCK4_PROMOTE_ENFORCE`.

## Troubleshooting
- Missing fields: ensure writer attaches `actor_id`, `key_id`, `signed_at`, `nonce`, `sig`.
- Keyring mismatch: verify `key_id` exists and actor matches.
- Replay detected: check replay DB persistence and uniqueness of nonces.
