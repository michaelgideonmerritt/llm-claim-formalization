from __future__ import annotations

import llm_claim_formalization.demo.server as server_module
from llm_claim_formalization.core.verification import VerificationResult
from llm_claim_formalization.demo.server import VerifyRequest, verify


async def test_demo_verify_endpoint_returns_pipeline_payload(monkeypatch) -> None:
    expected = VerificationResult(
        status="verified",
        route="formal",
        claim_type="arithmetic",
        reason="formal_expression",
        equation="2 + 2 == 4",
        confidence=1.0,
        execution_time_ms=1.23,
        message="Claim verified by formal solver.",
    )

    monkeypatch.setattr(server_module, "verify_claim", lambda _claim: expected)

    payload = await verify(VerifyRequest(claim="2 + 2 == 4"))

    assert payload["status"] == "verified"
    assert payload["route"] == "formal"
    assert payload["equation"] == "2 + 2 == 4"
