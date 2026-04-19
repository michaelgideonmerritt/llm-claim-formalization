from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from time import perf_counter
from typing import Any, Optional

from z3 import Bool, BoolSort, Const, DeclareSort, ForAll, Function, Implies, Not, Solver, unsat

from ..backends import verify_entailment_with_ollama, verify_with_ollama, verify_with_z3
from .evidence import classify_stance, load_evidence_corpus, resolve_evidence_path, retrieve_citations
from .ir import (
    ArithmeticIR,
    Citation,
    ClaimIR,
    FactualIR,
    FolIR,
    PolicyRuleIR,
    PropositionalIR,
    ReasonCode,
    Route,
    StatisticalIR,
    SubjectiveIR,
    VerificationStatus,
)


@dataclass
class AdapterResult:
    status: VerificationStatus
    reason: ReasonCode
    message: str
    confidence: float
    solver_result: Optional[dict[str, Any]] = None
    equation: Optional[str] = None
    llm_only: Optional[dict[str, Any]] = None
    comparison: Optional[dict[str, Any]] = None
    citations: list[Citation] = field(default_factory=list)
    evidence_assessment: Optional[dict[str, Any]] = None
    suggested_clarification: Optional[str] = None


def _to_llm_status(ollama_result: dict[str, Any]) -> str:
    verdict = ollama_result.get("verdict")
    if verdict == "true":
        return "VALID"
    if verdict == "false":
        return "INVALID"
    if verdict == "unknown":
        return "UNKNOWN"
    return "ERROR"


class DomainAdapter:
    route: Route

    def verify(self, ir: ClaimIR) -> AdapterResult:
        raise NotImplementedError


_DEFAULT_ADAPTERS: dict[Route, DomainAdapter] = {}
_ADAPTERS: dict[Route, DomainAdapter] = {}
_NLI_AVAILABLE = True


def _factual_stance_mode() -> str:
    mode = os.getenv("LLM_CF_FACTUAL_STANCE_MODE", "hybrid").strip().lower()
    if mode not in {"hybrid", "heuristic", "nli"}:
        return "hybrid"
    return mode


def _nli_to_stance(label: Optional[str]) -> str:
    if label == "entailment":
        return "support"
    if label == "contradiction":
        return "contradict"
    return "neutral"


def _select_stance(lexical_stance: str, nli_stance: Optional[str], mode: str) -> str:
    if mode == "heuristic":
        return lexical_stance

    if mode == "nli":
        return nli_stance or "neutral"

    # hybrid
    if nli_stance is None:
        return lexical_stance
    if nli_stance != "neutral":
        return nli_stance
    return lexical_stance


class ArithmeticAdapter(DomainAdapter):
    route = Route.structured

    @staticmethod
    def _build_comparison(ollama_result: dict[str, Any], z3_result: dict[str, Any]) -> dict[str, Any]:
        llm_status = _to_llm_status(ollama_result)

        verified = z3_result.get("verified")
        if verified is True:
            verifier_status = "VALID"
        elif verified is False:
            verifier_status = "INVALID"
        else:
            verifier_status = "COMPUTED"

        if verifier_status == "COMPUTED":
            verdict = "FORMAL_COMPUTED"
            verdict_message = "Formal engine computed a value; no boolean claim was provided to prove or refute."
        elif llm_status in {"UNKNOWN", "ERROR"}:
            verdict = "LLM_UNCERTAIN"
            verdict_message = "LLM could not provide a reliable boolean verdict."
        elif llm_status == verifier_status:
            verdict = "LLM_CORRECT" if verifier_status == "VALID" else "BOTH_AGREE_INVALID"
            verdict_message = (
                "LLM reasoning matched formal verification."
                if verifier_status == "VALID"
                else "Both LLM and formal verifier concluded the claim is invalid."
            )
        elif verifier_status == "VALID" and llm_status == "INVALID":
            verdict = "LLM_OVERLY_CAUTIOUS"
            verdict_message = "Formal verification found the claim valid while the LLM rejected it."
        elif verifier_status == "INVALID" and llm_status == "VALID":
            verdict = "LLM_ERROR_CAUGHT"
            verdict_message = "Formal verification refuted a claim the LLM marked as valid."
        else:
            verdict = "LLM_MISMATCH"
            verdict_message = "LLM and formal verification disagreed."

        return {
            "llm_only": llm_status,
            "llm_plus_verifier": verifier_status,
            "agreement": llm_status == verifier_status,
            "verdict": verdict,
            "verdict_message": verdict_message,
        }

    def verify(self, ir: ClaimIR) -> AdapterResult:
        if not isinstance(ir, ArithmeticIR):
            raise TypeError("ArithmeticAdapter expected ArithmeticIR input.")
        z3_result = verify_with_z3(ir.equation)
        ollama_result = verify_with_ollama(ir.source_text)
        comparison = self._build_comparison(ollama_result, z3_result)

        verified = z3_result.get("verified")
        if verified is True:
            return AdapterResult(
                status=VerificationStatus.verified,
                reason=ReasonCode.structured_extraction if ir.route == Route.structured else ReasonCode.formal_expression,
                message="Claim verified by formal solver.",
                confidence=1.0,
                solver_result=z3_result,
                equation=z3_result.get("normalized_equation", ir.equation),
                comparison=comparison,
            )

        if verified is False:
            return AdapterResult(
                status=VerificationStatus.unverified,
                reason=ReasonCode.structured_extraction if ir.route == Route.structured else ReasonCode.formal_expression,
                message="Claim refuted by formal solver.",
                confidence=1.0,
                solver_result=z3_result,
                equation=z3_result.get("normalized_equation", ir.equation),
                comparison=comparison,
            )

        if verified is None:
            return AdapterResult(
                status=VerificationStatus.computed,
                reason=ReasonCode.formal_expression,
                message="Expression computed, but no boolean assertion was present to verify.",
                confidence=0.9,
                solver_result=z3_result,
                equation=z3_result.get("normalized_equation", ir.equation),
                comparison=comparison,
            )

        return AdapterResult(
            status=VerificationStatus.error,
            reason=ReasonCode.backend_error,
            message=z3_result.get("error", "Formal verification failed."),
            confidence=0.0,
            solver_result=z3_result,
            equation=ir.equation,
            comparison=comparison,
        )


class PropositionalAdapter(DomainAdapter):
    route = Route.propositional

    @staticmethod
    def _literal_expr(raw: str, symbol_table: dict[str, Any]) -> Any:
        token = raw.strip().lower()
        negated = token.startswith("not ")
        name = token[4:].strip() if negated else token

        if name not in symbol_table:
            symbol_table[name] = Bool(name)

        expr = symbol_table[name]
        return Not(expr) if negated else expr

    def verify(self, ir: ClaimIR) -> AdapterResult:
        if not isinstance(ir, PropositionalIR):
            raise TypeError("PropositionalAdapter expected PropositionalIR input.")
        symbols: dict[str, Any] = {}

        antecedent = self._literal_expr(ir.antecedent, symbols)
        consequent = self._literal_expr(ir.consequent, symbols)
        second_premise = self._literal_expr(ir.second_premise, symbols)
        conclusion = self._literal_expr(ir.conclusion, symbols)

        solver = Solver()
        solver.add(Implies(antecedent, consequent))
        solver.add(second_premise)
        solver.add(Not(conclusion))

        result = solver.check()
        verified = result == unsat

        solver_result = {
            "verified": verified,
            "solver": "z3",
            "result": str(result),
            "variables": sorted(symbols.keys()),
            "normalized_equation": (
                f"({ir.antecedent} -> {ir.consequent}) and {ir.second_premise} implies {ir.conclusion}"
            ),
        }

        return AdapterResult(
            status=VerificationStatus.verified if verified else VerificationStatus.unverified,
            reason=ReasonCode.propositional_pattern,
            message=(
                "Propositional claim verified by theorem proving."
                if verified
                else "Propositional claim refuted by theorem proving."
            ),
            confidence=1.0,
            solver_result=solver_result,
            equation=solver_result["normalized_equation"],
        )


class FolAdapter(DomainAdapter):
    route = Route.fol

    @staticmethod
    def _normalize_term(value: str) -> str:
        return re.sub(r"[^a-z0-9_]", "", value.lower())

    def verify(self, ir: ClaimIR) -> AdapterResult:
        if not isinstance(ir, FolIR):
            raise TypeError("FolAdapter expected FolIR input.")
        universe = DeclareSort("U")
        x = Const("x", universe)

        subject_fn = Function(self._normalize_term(ir.universal_subject) or "subject", universe, BoolSort())
        predicate_fn = Function(self._normalize_term(ir.universal_predicate) or "predicate", universe, BoolSort())

        individual_const = Const(self._normalize_term(ir.individual) or "individual", universe)

        individual_subject_fn = Function(
            self._normalize_term(ir.individual_subject) or "individual_subject",
            universe,
            BoolSort(),
        )
        conclusion_predicate_fn = Function(
            self._normalize_term(ir.conclusion_predicate) or "conclusion_predicate",
            universe,
            BoolSort(),
        )

        premise1 = ForAll([x], Implies(subject_fn(x), predicate_fn(x)))
        premise2 = individual_subject_fn(individual_const)
        conclusion = conclusion_predicate_fn(individual_const)

        # If premise2 refers to same class as universal subject, tie symbols.
        if self._normalize_term(ir.individual_subject) == self._normalize_term(ir.universal_subject):
            premise2 = subject_fn(individual_const)

        if self._normalize_term(ir.conclusion_predicate) == self._normalize_term(ir.universal_predicate):
            conclusion = predicate_fn(individual_const)

        solver = Solver()
        solver.add(premise1)
        solver.add(premise2)
        solver.add(Not(conclusion))

        result = solver.check()
        verified = result == unsat

        solver_result = {
            "verified": verified,
            "solver": "z3",
            "result": str(result),
            "normalized_equation": (
                f"forall x: {ir.universal_subject}(x)->{ir.universal_predicate}(x), "
                f"{ir.individual_subject}({ir.individual}) |- {ir.conclusion_predicate}({ir.individual})"
            ),
        }

        return AdapterResult(
            status=VerificationStatus.verified if verified else VerificationStatus.unverified,
            reason=ReasonCode.fol_pattern,
            message=(
                "FOL claim verified by theorem proving."
                if verified
                else "FOL claim refuted by theorem proving."
            ),
            confidence=1.0,
            solver_result=solver_result,
            equation=solver_result["normalized_equation"],
        )


class StatisticalAdapter(DomainAdapter):
    route = Route.statistical

    def verify(self, ir: ClaimIR) -> AdapterResult:
        if not isinstance(ir, StatisticalIR):
            raise TypeError("StatisticalAdapter expected StatisticalIR input.")
        if ir.p_value is None or ir.alpha is None:
            return AdapterResult(
                status=VerificationStatus.cannot_formally_verify,
                reason=ReasonCode.unsupported_statistical_formalization,
                message="Statistical claim detected, but required parameters are missing for formal verification.",
                confidence=0.0,
                suggested_clarification="Provide both p-value and alpha threshold (e.g., p=0.03 and alpha=0.05).",
            )

        equation = f"{ir.p_value} < {ir.alpha}"
        z3_result = verify_with_z3(equation)
        verified = z3_result.get("verified")

        if verified is True:
            return AdapterResult(
                status=VerificationStatus.verified,
                reason=ReasonCode.statistical_claim,
                message="Statistical significance claim verified (p-value is below alpha).",
                confidence=1.0,
                equation=equation,
                solver_result=z3_result,
            )

        return AdapterResult(
            status=VerificationStatus.unverified,
            reason=ReasonCode.statistical_claim,
            message="Statistical significance claim refuted (p-value is not below alpha).",
            confidence=1.0,
            equation=equation,
            solver_result=z3_result,
        )


class PolicyRuleAdapter(DomainAdapter):
    route = Route.policy_rule

    def verify(self, ir: ClaimIR) -> AdapterResult:
        if not isinstance(ir, PolicyRuleIR):
            raise TypeError("PolicyRuleAdapter expected PolicyRuleIR input.")
        return AdapterResult(
            status=VerificationStatus.cannot_formally_verify,
            reason=ReasonCode.unsupported_policy_formalization,
            message="Policy/rule claim detected but no policy logic specification was provided for theorem proving.",
            confidence=0.0,
            suggested_clarification=(
                "Provide machine-readable policy rules (e.g., DSL/JSON) and a concrete scenario to evaluate."
            ),
        )


class FactualAdapter(DomainAdapter):
    route = Route.factual

    def verify(self, ir: ClaimIR) -> AdapterResult:
        global _NLI_AVAILABLE
        if not isinstance(ir, FactualIR):
            raise TypeError("FactualAdapter expected FactualIR input.")
        evidence_path = resolve_evidence_path()
        if evidence_path is None:
            return AdapterResult(
                status=VerificationStatus.cannot_formally_verify,
                reason=ReasonCode.missing_evidence_source,
                message="Factual claim detected, but no evidence corpus is configured.",
                confidence=0.0,
                suggested_clarification=(
                    "Set LLM_CF_EVIDENCE_PATH to a JSONL corpus with id/title/text/url fields."
                ),
            )

        try:
            corpus = load_evidence_corpus(Path(evidence_path))
        except Exception as exc:
            return AdapterResult(
                status=VerificationStatus.error,
                reason=ReasonCode.schema_validation_error,
                message=f"Failed to load evidence corpus: {exc}",
                confidence=0.0,
            )

        citations = retrieve_citations(ir.proposition, corpus)
        if not citations:
            return AdapterResult(
                status=VerificationStatus.cannot_formally_verify,
                reason=ReasonCode.insufficient_evidence,
                message="No sufficiently relevant evidence was retrieved for this factual claim.",
                confidence=0.0,
                suggested_clarification="Provide supporting sources or a richer evidence corpus.",
            )

        support_count = 0
        contradiction_count = 0
        neutral_count = 0
        weighted_support = 0.0
        weighted_contradiction = 0.0
        nli_attempted = 0
        nli_success = 0
        nli_errors = 0
        mode = _factual_stance_mode()

        classified_citations: list[Citation] = []
        for citation in citations:
            lexical_stance = classify_stance(ir.proposition, citation.snippet)
            nli_stance: Optional[str] = None

            if mode in {"hybrid", "nli"} and _NLI_AVAILABLE:
                nli_attempted += 1
                nli_result = verify_entailment_with_ollama(ir.proposition, citation.snippet)
                if nli_result.get("error"):
                    nli_errors += 1
                    # Disable repeated failing live calls when Ollama/NLI is unavailable.
                    _NLI_AVAILABLE = False
                else:
                    nli_success += 1
                    nli_stance = _nli_to_stance(nli_result.get("label"))

            stance = _select_stance(lexical_stance, nli_stance, mode)
            classified = citation.model_copy(update={"stance": stance})
            classified_citations.append(classified)

            if stance == "support":
                support_count += 1
                weighted_support += citation.score
            elif stance == "contradict":
                contradiction_count += 1
                weighted_contradiction += citation.score
            else:
                neutral_count += 1

        total = max(1, len(classified_citations))
        evidence_assessment = {
            "support_count": support_count,
            "contradiction_count": contradiction_count,
            "neutral_count": neutral_count,
            "support_ratio": round(support_count / total, 3),
            "contradiction_ratio": round(contradiction_count / total, 3),
            "stance_mode": mode,
            "nli_attempted": nli_attempted,
            "nli_success": nli_success,
            "nli_errors": nli_errors,
        }

        if support_count > 0 and contradiction_count == 0:
            confidence = weighted_support / max(1, support_count)
            return AdapterResult(
                status=VerificationStatus.evidence_backed,
                reason=ReasonCode.factual_claim,
                message="Retrieved supporting evidence snippets for factual review.",
                confidence=round(confidence, 3),
                citations=classified_citations,
                evidence_assessment=evidence_assessment,
            )

        if contradiction_count > 0 and support_count == 0:
            confidence = weighted_contradiction / max(1, contradiction_count)
            return AdapterResult(
                status=VerificationStatus.unverified,
                reason=ReasonCode.conflicting_evidence,
                message="Retrieved evidence contradicts the factual claim.",
                confidence=round(confidence, 3),
                citations=classified_citations,
                evidence_assessment=evidence_assessment,
            )

        if support_count > 0 and contradiction_count > 0:
            return AdapterResult(
                status=VerificationStatus.cannot_formally_verify,
                reason=ReasonCode.conflicting_evidence,
                message="Retrieved evidence is mixed: both support and contradiction were found.",
                confidence=0.0,
                citations=classified_citations,
                evidence_assessment=evidence_assessment,
                suggested_clarification="Narrow the claim scope or provide higher-quality authoritative sources.",
            )

        return AdapterResult(
            status=VerificationStatus.cannot_formally_verify,
            reason=ReasonCode.insufficient_evidence,
            message="Only weakly related evidence was retrieved for this factual claim.",
            confidence=0.0,
            citations=classified_citations,
            evidence_assessment=evidence_assessment,
            suggested_clarification="Provide sources that directly state or refute the claim.",
        )


class SubjectiveAdapter(DomainAdapter):
    route = Route.subjective

    def verify(self, ir: ClaimIR) -> AdapterResult:
        if not isinstance(ir, SubjectiveIR):
            raise TypeError("SubjectiveAdapter expected SubjectiveIR input.")
        return AdapterResult(
            status=VerificationStatus.cannot_formally_verify,
            reason=ReasonCode.unsupported_subjective_claim,
            message="Subjective claim detected; theorem proving cannot establish objective truth for this statement.",
            confidence=0.0,
            suggested_clarification="Provide measurable criteria or convert to an objective, testable claim.",
        )


class LlmFallbackAdapter(DomainAdapter):
    route = Route.subjective

    def verify(self, ir: ClaimIR) -> AdapterResult:
        llm_result = verify_with_ollama(ir.source_text)
        llm_status = _to_llm_status(llm_result)
        return AdapterResult(
            status=VerificationStatus.llm_only,
            reason=ReasonCode.unsupported_logical_structure,
            message="No formal backend matched this claim structure; returning probabilistic LLM reasoning.",
            confidence=0.35 if llm_status in {"VALID", "INVALID"} else 0.0,
            llm_only={
                "status": llm_status,
                "verdict": llm_result.get("verdict"),
                "raw_response": llm_result.get("raw_response"),
                "model": llm_result.get("model"),
                "error": llm_result.get("error"),
            },
        )


_DEFAULT_ADAPTERS = {
    Route.structured: ArithmeticAdapter(),
    Route.formal: ArithmeticAdapter(),
    Route.propositional: PropositionalAdapter(),
    Route.fol: FolAdapter(),
    Route.statistical: StatisticalAdapter(),
    Route.policy_rule: PolicyRuleAdapter(),
    Route.factual: FactualAdapter(),
    Route.subjective: SubjectiveAdapter(),
}
_ADAPTERS = dict(_DEFAULT_ADAPTERS)


def get_adapter(route: Route) -> DomainAdapter:
    return _ADAPTERS.get(route, LlmFallbackAdapter())


def register_adapter(route: Route, adapter: DomainAdapter, overwrite: bool = False) -> None:
    if route in _ADAPTERS and not overwrite:
        raise ValueError(f"Adapter already registered for route '{route.value}'. Use overwrite=True to replace.")
    _ADAPTERS[route] = adapter


def unregister_adapter(route: Route) -> None:
    if route in _DEFAULT_ADAPTERS:
        _ADAPTERS[route] = _DEFAULT_ADAPTERS[route]
        return
    _ADAPTERS.pop(route, None)


def list_registered_adapters() -> dict[Route, str]:
    return {route: adapter.__class__.__name__ for route, adapter in _ADAPTERS.items()}


def run_adapter(route: Route, ir: ClaimIR) -> tuple[AdapterResult, float]:
    adapter = get_adapter(route)
    started = perf_counter()
    result = adapter.verify(ir)
    elapsed_ms = round((perf_counter() - started) * 1000, 2)
    return result, elapsed_ms
