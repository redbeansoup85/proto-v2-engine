# LOCK-4 Keyring Loader (Read-Only)

This document describes the read-only keyring loader.

## Purpose
- Validate keyring path and minimal JSON shape.
- Enforce repo-external keyring storage.

## Usage

```bash
python tools/lock4_key_loader.py --keyring-path /secure/keyring.json
```

## Expected Output
- JSON summary with `ok`, `keyring_path`, `keys_count`.
- Fail-closed on invalid paths or malformed JSON.
