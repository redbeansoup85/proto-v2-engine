from __future__ import annotations

import os
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from core.judgment.models import HumanDecision, DpaOption, DpaRecord
from core.judgment.repo import InMemoryDpaRepository
from core.judgment.persistence.file_repo import FileBackedDpaRepository
from core.judgment.service import DpaService


router = APIRouter(prefix="/v1/constitutional", tags=["constitutional_debug"])


def _require_devlike() -> None:
    env = os.getenv("METAOS_ENV", "dev").lower()
    if env not in ("dev", "local"):
        raise HTTPException(status_code=404, detail="DEBUG_DISABLED")


# mirror minimal composer used in constitutional.py (keep debug isolated)
class _MinimalComposer:
    def compose(self, *, dpa_id: str, event_id: str, context: Dict[str, Any]) -> DpaRecord:
        opt = DpaOption(
            option_id="opt_approve",
            title="Approve and proceed",
            summary="Proceed to engine evaluation",
            blocked=False,
            payload={},
        )
        return DpaRecord(
            dpa_id=dpa_id,
            event_id=event_id,
            context_json=context or {},
            options_json=[opt],
        )


# storage selection consistent with v0.6
if os.getenv("METAOS_STORAGE", "memory").lower() == "file":
    _REPO = FileBackedDpaRepository(root_dir=os.getenv("METAOS_DATA_DIR", "var/metaos"))  # type: ignore
else:
    _REPO = InMemoryDpaRepository()

_SVC = DpaService(repo=_REPO, composer=_MinimalComposer())  # type: ignore[arg-type]


class SeedReq(BaseModel):
    dpa_id: str = "dpa_demo_001"
    event_id: str = "evt_demo_001"
    selected_option_id: str = "opt_approve"


@router.post("/__debug_seed")
def __debug_seed(req: SeedReq):
    _require_devlike()

    # create if missing
    try:
        _ = _SVC.get_dpa(dpa_id=req.dpa_id)
    except Exception:
        _SVC.create_dpa(event_id=req.event_id, context={"source": "constitutional_debug"}, dpa_id=req.dpa_id)

    # move to reviewing (best-effort)
    try:
        _SVC.start_review(dpa_id=req.dpa_id, reviewer="debug")
    except Exception:
        pass

    # approve -> APPROVED (best-effort)
    hd = HumanDecision(
        selected_option_id=req.selected_option_id,
        reason_codes=["DEBUG"],
        reason_note="debug seed",
        approver_name="Tester",
        approver_role="Owner",
        signature="Tester@local",
    )
    dpa = _SVC.submit_human_decision(dpa_id=req.dpa_id, decision=hd)
    return {"ok": True, "status": str(dpa.status)}
