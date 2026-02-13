from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def send_to_stdout(outbox_item_path: str) -> None:
    """
    Deterministic console sender.
    Reads an outbox delivery JSON and prints a canonical JSON string to stdout.
    """
    p = Path(outbox_item_path)
    obj: Any = json.loads(p.read_text(encoding="utf-8"))

    # Canonicalize: stable key ordering + no extra whitespace, newline-terminated.
    s = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    print(s)
