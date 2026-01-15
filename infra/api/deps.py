from __future__ import annotations

from pathlib import Path
from typing import Dict, Optional, TYPE_CHECKING, Any

# NOTE:
# Do NOT import core/orchestrator/router.py at module import time.
# Keep imports inside getter functions to avoid hard coupling for routes that
# do not need orchestrator/policy engine (e.g., policy patch APIs).

REPO_ROOT = Path(__file__).resolve().parents[2]
AUDIT_DIR = (REPO_ROOT / "data" / "audit").as_posix()
SCENE_DIR = (REPO_ROOT / "data" / "scene").as_posix()

# runtime state per scene_id (operational only)
_SCENE_STATE: Dict[str, Any] = {}

# singletons (lazy)
_POLICY = None
_ORCH = None
_L2 = None
_SCENES = None

_l3_learning_repo = None
_policy_patch_repo = None
_auto_proposal_receipt_repo = None
_approval_queue = None


# ----------------------------
# Core runtime (v0.3/v1 line)
# ----------------------------
def get_policy():
    global _POLICY
    if _POLICY is None:
        from core.policy.engine import PolicyEngine
        _POLICY = PolicyEngine()
    return _POLICY


def get_orchestrator():
    global _ORCH
    if _ORCH is None:
        # This import may fail if contracts drifted.
        # We keep it lazy so routes that don't need it still work.
        from core.orchestrator.router import Orchestrator
        _ORCH = Orchestrator()
    return _ORCH


def get_l2():
    global _L2
    if _L2 is None:
        from infra.storage.l2_audit_repo import FileBackedL2AuditRepo
        _L2 = FileBackedL2AuditRepo(base_dir=AUDIT_DIR)
    return _L2


def get_scene_repo():
    global _SCENES
    if _SCENES is None:
        from infra.storage.scene_repo import FileBackedSceneRepo
        _SCENES = FileBackedSceneRepo(base_dir=SCENE_DIR)
    return _SCENES


def get_scene_state_map() -> Dict[str, Any]:
    return _SCENE_STATE


# ----------------------------
# L3 Learning (B-2)
# ----------------------------
def get_l3_learning():
    global _l3_learning_repo
    if _l3_learning_repo is None:
        from infra.storage.l3_learning_repo import FileBackedL3LearningRepo
        _l3_learning_repo = FileBackedL3LearningRepo(
            path=str(REPO_ROOT / "data" / "learning" / "l3_samples.jsonl")
        )
    return _l3_learning_repo


# ----------------------------
# Policy Patch Proposals (B-2 / v2-alpha)
# ----------------------------
def get_policy_patch_repo():
    global _policy_patch_repo
    if _policy_patch_repo is None:
        from infra.storage.policy_patch_repo import FileBackedPolicyPatchRepo
        _policy_patch_repo = FileBackedPolicyPatchRepo(
            path=str(REPO_ROOT / "data" / "learning" / "policy_patch_proposals.jsonl")
        )
    return _policy_patch_repo


# ----------------------------
# v2-alpha: Auto-Proposal receipts (DoD)
# ----------------------------
def get_auto_proposal_receipt_repo():
    global _auto_proposal_receipt_repo
    if _auto_proposal_receipt_repo is None:
        from infra.storage.auto_proposal_receipt_repo import FileBackedAutoProposalReceiptRepo
        _auto_proposal_receipt_repo = FileBackedAutoProposalReceiptRepo(
            path=str(REPO_ROOT / "data" / "learning" / "auto_proposal_receipts.jsonl")
        )
    return _auto_proposal_receipt_repo


# ----------------------------
# v2-alpha: Approval queue (alpha visibility)
# ----------------------------
def get_approval_queue():
    global _approval_queue
    if _approval_queue is None:
        from infra.storage.approval_queue_repo import FileBackedApprovalQueue
        _approval_queue = FileBackedApprovalQueue(
            path=str(REPO_ROOT / "logs" / "approvals" / "approvals.jsonl")
        )
    return _approval_queue
