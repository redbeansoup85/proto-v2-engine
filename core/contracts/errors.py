from __future__ import annotations


class ContractViolationError(PermissionError):
    """Fail-closed: contract invalid or constraints violated."""
    pass


class ContractExpiredError(ContractViolationError):
    pass


class ContractMalformedError(ContractViolationError):
    pass


class ContractForbiddenActionError(ContractViolationError):
    pass


class ContractConstraintError(ContractViolationError):
    pass
