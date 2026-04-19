import pytest

import llm_claim_formalization.core.adapters as adapters_module
from llm_claim_formalization import verify_claim


@pytest.fixture(autouse=True)
def _default_to_heuristic_stance(monkeypatch) -> None:
    monkeypatch.setenv("LLM_CF_FACTUAL_STANCE_MODE", "heuristic")
    monkeypatch.setattr(adapters_module, "_NLI_AVAILABLE", True)


def test_propositional_route_and_status() -> None:
    result = verify_claim("If server is up then api responds. server is up. therefore api responds")
    assert result.route == "propositional"
    assert result.status == "verified"


def test_fol_route_and_status() -> None:
    result = verify_claim("All humans are mortal. socrates is humans. therefore socrates is mortal")
    assert result.route == "fol"
    assert result.status == "verified"


def test_statistical_route_with_missing_parameters_abstains() -> None:
    result = verify_claim("The result is statistically significant with p=0.02")
    assert result.route == "statistical"
    assert result.status == "cannot_formally_verify"
    assert result.suggested_clarification is not None


def test_policy_rule_route_abstains() -> None:
    result = verify_claim("Policy requires two factor authentication for admin access")
    assert result.route == "policy_rule"
    assert result.status == "cannot_formally_verify"


def test_factual_route_returns_citations() -> None:
    result = verify_claim("Paris is the capital of France")
    assert result.route == "factual"
    assert result.status == "evidence_backed"
    assert len(result.citations) >= 1
    assert result.citations[0]["stance"] in {"support", "neutral", "contradict"}


def test_factual_route_detects_contradicted_claims() -> None:
    result = verify_claim("Smoking does not increase risk of heart disease")
    assert result.route == "factual"
    assert result.status == "unverified"
    assert result.reason == "conflicting_evidence"
    assert result.evidence_assessment is not None


def test_subjective_route_abstains() -> None:
    result = verify_claim("This restaurant is the best in town")
    assert result.route == "subjective"
    assert result.status == "cannot_formally_verify"


def test_factual_route_hybrid_mode_uses_nli_when_available(monkeypatch) -> None:
    monkeypatch.setenv("LLM_CF_FACTUAL_STANCE_MODE", "hybrid")
    monkeypatch.setattr(adapters_module, "_NLI_AVAILABLE", True)

    def fake_nli(_claim: str, _evidence: str, _model: str | None = None) -> dict:
        return {"label": "contradiction", "confidence": 0.92, "model": "mock", "raw_response": "contradiction"}

    monkeypatch.setattr(adapters_module, "verify_entailment_with_ollama", fake_nli)
    result = verify_claim("Smoking increases risk of heart disease")

    assert result.route == "factual"
    assert result.status == "unverified"
    assert result.reason == "conflicting_evidence"
    assert result.evidence_assessment is not None
    assert result.evidence_assessment["nli_success"] >= 1
