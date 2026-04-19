from __future__ import annotations

from dataclasses import dataclass, field
from time import perf_counter
from typing import Any, Optional

from .adapters import run_adapter
from .extraction import extract_claim
from .ir import Route, VerificationStatus
from .routing import RouteDecision, choose_route


@dataclass
class VerificationResult:
    status: str
    route: str
    claim_type: str
    reason: str
    equation: Optional[str] = None
    confidence: float = 0.0
    execution_time_ms: float = 0.0
    message: Optional[str] = None
    comparison: Optional[dict[str, Any]] = None
    llm_only: Optional[dict[str, Any]] = None
    solver_result: Optional[dict[str, Any]] = None
    citations: list[dict[str, Any]] = field(default_factory=list)
    evidence_assessment: Optional[dict[str, Any]] = None
    suggested_clarification: Optional[str] = None
    missing_info: Optional[str] = None
    detected_values: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "route": self.route,
            "claim_type": self.claim_type,
            "reason": self.reason,
            "equation": self.equation,
            "confidence": self.confidence,
            "execution_time_ms": self.execution_time_ms,
            "message": self.message,
            "comparison": self.comparison,
            "llm_only": self.llm_only,
            "solver_result": self.solver_result,
            "citations": self.citations,
            "evidence_assessment": self.evidence_assessment,
            "suggested_clarification": self.suggested_clarification,
            "missing_info": self.missing_info,
            "detected_values": self.detected_values,
        }


def _build_abstention_result(decision: RouteDecision, started_at: float) -> VerificationResult:
    if decision.route == Route.no_claim:
        status = VerificationStatus.no_claim.value
        message = "No verifiable claim detected."
    else:
        status = VerificationStatus.insufficient_info.value
        message = "Missing information prevents formal verification."

    return VerificationResult(
        status=status,
        route=decision.route.value,
        claim_type=decision.claim_type.value,
        reason=decision.reason.value,
        confidence=0.0,
        execution_time_ms=round((perf_counter() - started_at) * 1000, 2),
        message=message,
        suggested_clarification=decision.suggested_clarification,
        missing_info=decision.missing_info,
        detected_values=decision.detected_values,
    )


def verify_claim(text: str) -> VerificationResult:
    """Run routed claim verification using typed IR + domain adapters."""
    started_at = perf_counter()

    structured_claim = extract_claim(text)
    decision = choose_route(text, structured_claim)

    if decision.route in {Route.insufficient_info, Route.no_claim}:
        return _build_abstention_result(decision, started_at)

    if decision.ir is None:
        return VerificationResult(
            status=VerificationStatus.error.value,
            route=decision.route.value,
            claim_type=decision.claim_type.value,
            reason=decision.reason.value,
            confidence=0.0,
            execution_time_ms=round((perf_counter() - started_at) * 1000, 2),
            message="Routing produced no IR payload for adapter execution.",
        )

    adapter_result, _adapter_elapsed = run_adapter(decision.route, decision.ir)

    return VerificationResult(
        status=adapter_result.status.value,
        route=decision.route.value,
        claim_type=decision.claim_type.value,
        reason=adapter_result.reason.value,
        equation=adapter_result.equation,
        confidence=adapter_result.confidence,
        execution_time_ms=round((perf_counter() - started_at) * 1000, 2),
        message=adapter_result.message,
        comparison=adapter_result.comparison,
        llm_only=adapter_result.llm_only,
        solver_result=adapter_result.solver_result,
        citations=[citation.model_dump() for citation in adapter_result.citations],
        evidence_assessment=adapter_result.evidence_assessment,
        suggested_clarification=adapter_result.suggested_clarification or decision.suggested_clarification,
        missing_info=decision.missing_info,
        detected_values=decision.detected_values,
    )
