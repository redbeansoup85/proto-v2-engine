# infra/api/routes/policy_patches.py
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from infra.api.deps import (
    get_policy_patch_repo,
    get_auto_proposal_receipt_repo,
    get_approval_queue,
)

router = APIRouter(
    prefix="/v1/learning/policy_patches",
    tags=["learning", "policy-patches"],
)

# -----------------------------------------------------------------------------
# Proposals (PolicyPatchProposal artifacts)
# -----------------------------------------------------------------------------


@router.get("/latest")
def list_latest(limit: int = 20, repo=Depends(get_policy_patch_repo)) -> dict:
    """
    Read-only endpoint.

    Returns latest policy patch proposals (auto or human).
    Items are append-only JSONL artifacts.
    """
    items = repo.list_recent(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/{proposal_id}")
def get_by_id(proposal_id: str, repo=Depends(get_policy_patch_repo)) -> dict:
    """
    Fetch a single policy patch proposal artifact by ID.
    """
    item = repo.get_by_id(proposal_id)
    if not item:
        raise HTTPException(status_code=404, detail="proposal not found")
    return item


# -----------------------------------------------------------------------------
# Auto-Proposal Receipts (DoD: every auto-proposal attempt must be receipted)
# -----------------------------------------------------------------------------


@router.get("/auto_receipts/latest")
def list_auto_receipts_latest(limit: int = 50, repo=Depends(get_auto_proposal_receipt_repo)) -> dict:
    """
    Read-only endpoint.

    Returns latest auto-proposal receipts (queued/skipped).
    This is the primary v2-alpha audit hook for self-proposed patches.
    """
    items = repo.list_recent(limit=limit)
    return {"count": len(items), "items": items}


# -----------------------------------------------------------------------------
# Approvals Queue (alpha visibility)
# -----------------------------------------------------------------------------


@router.get("/approvals/latest")
def list_approvals_latest(limit: int = 50, queue=Depends(get_approval_queue)) -> dict:
    """
    Read-only endpoint.

    Returns latest approval-queue items (PENDING reviews).
    Implementation depends on FileBackedApprovalQueue.list_recent() support.
    If list_recent is not available yet, implement it similarly to other repos.
    """
    if not hasattr(queue, "list_recent"):
        raise HTTPException(status_code=501, detail="approval queue listing not implemented")
    items = queue.list_recent(limit=limit)
    return {"count": len(items), "items": items}


@router.get("/approvals/{approval_id}")
def get_approval_by_id(approval_id: str, queue=Depends(get_approval_queue)) -> dict:
    """
    Fetch a single approval queue item.
    Requires FileBackedApprovalQueue.get_by_id() support.
    """
    if not hasattr(queue, "get_by_id"):
        raise HTTPException(status_code=501, detail="approval queue get_by_id not implemented")

    item = queue.get_by_id(approval_id)
    if not item:
        raise HTTPException(status_code=404, detail="approval not found")
    return item
