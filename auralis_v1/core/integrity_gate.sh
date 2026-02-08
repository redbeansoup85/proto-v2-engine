#!/usr/bin/env bash
set -euo pipefail

SEAL="/seal/MODEL_BLOBS_SHA256.txt"
BLOBS_DIR="/root/.ollama/models/blobs"

[ -f "$SEAL" ] || exit 1
[ -d "$BLOBS_DIR" ] || exit 1

TMP="$(mktemp)"
(cd "$BLOBS_DIR" && find . -maxdepth 1 -type f -print0 | xargs -0 sha256sum | sort) > "$TMP"

diff -q "$SEAL" "$TMP" >/dev/null || exit 1
