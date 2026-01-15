from __future__ import annotations

import json
import os
from typing import List, Dict, Any, Optional


class FileBackedPolicyPatchRepo:
    """
    JSONL file-backed repository for PolicyPatchProposal artifacts.

    - Each line = one immutable proposal record
    - Append-only (audit friendly)
    - Safe for v2-alpha auto-proposal stage
    """

    def __init__(self, path: str):
        self.path = path
        os.makedirs(os.path.dirname(self.path), exist_ok=True)

        if not os.path.exists(self.path):
            with open(self.path, "w", encoding="utf-8") as f:
                f.write("")

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------
    def append(self, proposal: Dict[str, Any]) -> None:
        """
        Append a proposal artifact as a JSONL line.
        Proposal must already be validated at engine level.
        """
        with open(self.path, "a", encoding="utf-8") as f:
            f.write(json.dumps(proposal, ensure_ascii=False) + "\n")

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------
    def list_recent(self, limit: int = 20) -> List[Dict[str, Any]]:
        if limit <= 0 or not os.path.exists(self.path):
            return []

        with open(self.path, "r", encoding="utf-8") as f:
            lines = f.readlines()[-limit:]

        out: List[Dict[str, Any]] = []
        for ln in lines:
            ln = ln.strip()
            if not ln:
                continue
            try:
                out.append(json.loads(ln))
            except Exception:
                continue
        return out

    def get_by_id(self, proposal_id: str) -> Optional[Dict[str, Any]]:
        """
        Linear scan (acceptable for alpha).
        Returns latest matching proposal if duplicates exist.
        """
        if not os.path.exists(self.path):
            return None

        with open(self.path, "r", encoding="utf-8") as f:
            for ln in reversed(f.readlines()):
                try:
                    item = json.loads(ln)
                except Exception:
                    continue
                if item.get("proposal_id") == proposal_id:
                    return item
        return None
