from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional
from uuid import uuid4

from .composer import DpaComposer
from .errors import conflict, unprocessable, PolicyError
from .models import DpaRecord, HumanDecision
from .repo import DpaRepository
from .transitions import abort as _abort
from .transitions import apply as _apply
from .transitions import start_review as _start_review
from .transitions import submit_human_decision as _submit_human_decision


@dataclass
class DpaService:
    """
    Core use-case orchestrator.

    Adapter (A) provides:
      - repository (DB-backed)
      - composer (domain-specific DPA builder)

    This service guarantees:
      - status machine enforcement
      - error codes/HTTP mapping stability via PolicyError
      - no dependency on FastAPI/SQLAlchemy
    """

    repo: DpaRepository
    composer: DpaComposer

    def create_dpa(
        self,
        *,
        event_id: str,
        context: Dict[str, Any],
        dpa_id: Optional[str] = None,
    ) -> DpaRecord:
        """
        Creates a new DPA in DPA_CREATED state.

        Note:
          - event existence check is adapter responsibility (A),
            unless your repo implements it indirectly.
        """
        new_id = dpa_id or f"dpa_{uuid4().hex}"
        dpa = self.composer.compose(dpa_id=new_id, event_id=event_id, context=context)
        return self.repo.create(dpa)

    def get_dpa(self, *, dpa_id: str) -> DpaRecord:
        dpa = self.repo.get(dpa_id)
        if not dpa:
            raise conflict("DPA_NOT_FOUND", "DPA not found.", {"dpa_id": dpa_id})
        return dpa

    def start_review(self, *, dpa_id: str, reviewer: str) -> DpaRecord:
        dpa = self.get_dpa(dpa_id=dpa_id)
        dpa = _start_review(dpa, reviewer=reviewer)
        return self.repo.save(dpa)

    def submit_human_decision(self, *, dpa_id: str, decision: HumanDecision) -> DpaRecord:
        dpa = self.get_dpa(dpa_id=dpa_id)
        dpa = _submit_human_decision(dpa, decision)
        return self.repo.save(dpa)

    def apply(self, *, dpa_id: str, selected_option_id: str | None = None, context: dict | None = None, **_: object) -> DpaRecord:
        dpa = self.get_dpa(dpa_id=dpa_id)
        dpa = _apply(dpa)
        return self.repo.save(dpa)

    def abort(self, *, dpa_id: str, reason: Optional[str] = None) -> DpaRecord:
        dpa = self.get_dpa(dpa_id=dpa_id)
        dpa = _abort(dpa, reason=reason)
        return self.repo.save(dpa)

    def assert_policy_error(self, e: Exception) -> PolicyError:
        """
        Adapter convenience: ensure thrown exception is a PolicyError.
        Allows adapter to map uniformly to HTTPException.
        """
        if isinstance(e, PolicyError):
            return e
        raise unprocessable("UNEXPECTED_ERROR", "Unexpected error type in DPA service.", {"type": type(e).__name__})
