class GovernanceError(Exception):
    """Base error for governance contract violations."""


class ProposalInvalid(GovernanceError):
    """Proposal failed schema/contract validation."""


class CanonViolation(GovernanceError):
    """Proposal violates Canon eligibility rules (pre-queue)."""


class HumanGateViolation(GovernanceError):
    """Proposal requires human gate but is marked otherwise."""
