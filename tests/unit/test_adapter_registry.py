import pytest

from llm_claim_formalization import (
    Route,
    list_registered_adapters,
    register_adapter,
    unregister_adapter,
    verify_claim,
)
from llm_claim_formalization.core.adapters import AdapterResult, DomainAdapter
from llm_claim_formalization.core.ir import ClaimIR, ReasonCode, VerificationStatus


class AlwaysPolicyVerifiedAdapter(DomainAdapter):
    route = Route.policy_rule

    def verify(self, ir: ClaimIR) -> AdapterResult:
        return AdapterResult(
            status=VerificationStatus.verified,
            reason=ReasonCode.policy_rule_claim,
            message="Custom policy adapter accepted the claim.",
            confidence=0.99,
        )


def test_register_adapter_overrides_policy_route() -> None:
    claim = "Policy requires two factor authentication for admin access"

    baseline = verify_claim(claim)
    assert baseline.status == "cannot_formally_verify"

    register_adapter(Route.policy_rule, AlwaysPolicyVerifiedAdapter(), overwrite=True)
    try:
        overridden = verify_claim(claim)
        assert overridden.status == "verified"
        registry = list_registered_adapters()
        assert registry[Route.policy_rule] == "AlwaysPolicyVerifiedAdapter"
    finally:
        unregister_adapter(Route.policy_rule)

    restored = verify_claim(claim)
    assert restored.status == "cannot_formally_verify"


def test_register_adapter_requires_overwrite_for_existing_route() -> None:
    with pytest.raises(ValueError):
        register_adapter(Route.formal, AlwaysPolicyVerifiedAdapter(), overwrite=False)
