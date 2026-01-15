from __future__ import annotations

from dataclasses import asdict
from typing import Optional

from infra.storage.policy_patch_repo import FileBackedPolicyPatchRepo
from infra.storage.auto_proposal_receipt_repo import FileBackedAutoProposalReceiptRepo
from infra.storage.approval_queue_repo import FileBackedApprovalQueue

# contracts는 네 실제 경로로 import
from core.learning.contracts import PolicyPatchProposal, AutoProposalReceipt


class ProposalRepoAdapter:
    def __init__(self, repo: FileBackedPolicyPatchRepo):
        self.repo = repo

    def save_proposal(self, proposal: PolicyPatchProposal) -> None:
        self.repo.append(asdict(proposal))


class ReceiptRepoAdapter:
    def __init__(self, repo: FileBackedAutoProposalReceiptRepo):
        self.repo = repo

    def append_receipt(self, receipt: AutoProposalReceipt) -> None:
        self.repo.append(asdict(receipt))


class ApprovalSinkAdapter:
    def __init__(self, queue: FileBackedApprovalQueue):
        self.queue = queue

    def enqueue_for_review(self, proposal: PolicyPatchProposal) -> str:
        # proposal dict로 저장
        return self.queue.enqueue(asdict(proposal))
