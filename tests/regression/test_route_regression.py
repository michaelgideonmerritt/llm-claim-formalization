from __future__ import annotations

import llm_claim_formalization.core.adapters as adapters_module
from llm_claim_formalization import verify_claim


def _fake_ollama_result(claim: str) -> dict:
    lower = claim.lower()
    if "moon is made of cheese" in lower:
        return {"verified": False, "verdict": "false", "model": "mock", "raw_response": "false"}
    if "smoking increases risk" in lower:
        return {"verified": True, "verdict": "true", "model": "mock", "raw_response": "true"}
    return {"verified": True, "verdict": "true", "model": "mock", "raw_response": "true"}


def test_route_regression(monkeypatch) -> None:
    monkeypatch.setattr(adapters_module, "verify_with_ollama", _fake_ollama_result)

    cases = [
        ("$100 with 50% off then 20% off is $40", "structured", "verified"),
        ("$100 with 50% off then 20% off is $60", "structured", "unverified"),
        ("2 + 2 == 4", "formal", "verified"),
        ("A price increases by 100%", "insufficient_info", "insufficient_info"),
        ("Smoking increases risk of heart disease", "factual", "evidence_backed"),
        ("The meeting is at 2:30 PM", "no_claim", "no_claim"),
    ]

    for text, expected_route, expected_status in cases:
        result = verify_claim(text)
        assert result.route == expected_route, text
        assert result.status == expected_status, text
