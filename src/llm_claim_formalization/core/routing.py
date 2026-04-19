from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from pydantic import ValidationError

from .extraction import Claim
from .ir import (
    ArithmeticIR,
    ClaimIR,
    ClaimType,
    FactualIR,
    FolIR,
    PolicyRuleIR,
    PropositionalIR,
    ReasonCode,
    Route,
    StatisticalIR,
    SubjectiveIR,
)


@dataclass
class RouteDecision:
    route: Route
    claim_type: ClaimType
    reason: ReasonCode
    ir: Optional[ClaimIR] = None
    missing_info: Optional[str] = None
    suggested_clarification: Optional[str] = None
    detected_values: list[str] = field(default_factory=list)


_FORMAL_ALLOWED = re.compile(r"^[A-Za-z0-9_+\-*/().<>=!&|\s]+$")
_FORMAL_OPERATOR = re.compile(r"(<=|>=|==|!=|=|<|>|\+|\-|\*|/)")
_LOGIC_WORDS = re.compile(r"\b(if|then|therefore|implies|forall|exists|assume|given|not)\b", re.I)
_CLAIM_WORDS = re.compile(
    r"\b(is|are|was|were|causes?|reduces?|increases?|decreases?|requires?|must|should|"
    r"can|cannot|true|false|valid|invalid)\b",
    re.I,
)
_SUBJECTIVE_WORDS = re.compile(
    r"\b(best|better|worse|worst|awesome|terrible|amazing|awful|excellent|bad|good|superior)\b",
    re.I,
)
_POLICY_WORDS = re.compile(
    r"\b(policy|law|regulation|compliance|required|must|shall|prohibited|forbidden|contract|clause)\b",
    re.I,
)
_FACTUAL_WORDS = re.compile(
    r"\b(study|trial|evidence|data|research|observed|reported|according to|risk|causes?|"
    r"increases?|decreases?|located|capital|population)\b",
    re.I,
)
_STATISTICAL_WORDS = re.compile(
    r"\b(p-value|p value|statistically significant|significant|confidence interval|alpha|beta)\b",
    re.I,
)
_PROPOSITIONAL_PATTERN = re.compile(
    r"if\s+(?P<antecedent>[^.;!?]+?)\s*(?:,)?\s*then\s+(?P<consequent>[^.;!?]+?)"
    r"[.;!?]\s*(?P<second_premise>[^.;!?]+?)[.;!?]\s*(?:therefore|thus|so)\s+"
    r"(?P<conclusion>[^.;!?]+)",
    re.I,
)
_FOL_PATTERN = re.compile(
    r"all\s+(?P<universal_subject>\w+)\s+are\s+(?P<universal_predicate>\w+)"
    r"[.;!?]\s*(?P<individual>\w+)\s+is\s+(?P<individual_subject>\w+)"
    r"[.;!?]\s*(?:therefore|thus|so)\s+(?P<conclusion_individual>\w+)\s+is\s+"
    r"(?P<conclusion_predicate>\w+)",
    re.I,
)
_P_VALUE_PATTERN = re.compile(r"\bp\s*(?:=|<|<=)\s*(0(?:\.\d+)?|1(?:\.0+)?)\b", re.I)
_ALPHA_PATTERN = re.compile(r"\b(?:alpha|α)\s*(?:=|<|<=)\s*(0(?:\.\d+)?|1(?:\.0+)?)\b", re.I)


def _is_schedule_or_metadata_text(text: str) -> bool:
    lower = text.lower()

    if re.search(r"\b\d{1,2}:\d{2}\s*(am|pm)?\b", lower) and any(
        word in lower for word in ["meeting", "appointment", "calendar", "event", "schedule", "reminder"]
    ):
        return True

    if any(phrase in lower for phrase in ["what time", "set a reminder", "when is the meeting"]):
        return True

    return False


def looks_like_formal_expression(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if not _FORMAL_ALLOWED.fullmatch(stripped):
        return False

    if not _FORMAL_OPERATOR.search(stripped):
        return False

    if _LOGIC_WORDS.search(stripped):
        return False

    return True


def _looks_like_claim_statement(text: str) -> bool:
    stripped = text.strip()
    if not stripped:
        return False

    if _CLAIM_WORDS.search(stripped):
        return True

    if re.search(r"\d", stripped):
        return True

    return False


def _looks_boolean_equation(equation: str) -> bool:
    return any(op in equation for op in ["==", "!=", "<", ">", "<=", ">="])


def _parse_float(match: Optional[re.Match[str]]) -> Optional[float]:
    if match is None:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def _build_ir_or_validation_failure(
    route: Route,
    claim_type: ClaimType,
    reason: ReasonCode,
    ir_builder: Callable[[], ClaimIR],
) -> RouteDecision:
    try:
        ir = ir_builder()
    except ValidationError:
        return RouteDecision(
            route=Route.insufficient_info,
            claim_type=claim_type,
            reason=ReasonCode.schema_validation_error,
            missing_info="schema_validation_error",
            suggested_clarification="Rephrase the claim with explicit variables and predicates.",
        )

    return RouteDecision(route=route, claim_type=claim_type, reason=reason, ir=ir)


def _parse_propositional_ir(text: str) -> Optional[PropositionalIR]:
    match = _PROPOSITIONAL_PATTERN.search(text.strip())
    if not match:
        return None

    return PropositionalIR(
        route=Route.propositional,
        claim_type=ClaimType.propositional,
        source_text=text,
        antecedent=match.group("antecedent").strip(),
        consequent=match.group("consequent").strip(),
        second_premise=match.group("second_premise").strip(),
        conclusion=match.group("conclusion").strip(),
    )


def _parse_fol_ir(text: str) -> Optional[FolIR]:
    match = _FOL_PATTERN.search(text.strip())
    if not match:
        return None

    individual = match.group("individual").strip()
    conclusion_individual = match.group("conclusion_individual").strip()
    if individual.lower() != conclusion_individual.lower():
        return None

    return FolIR(
        route=Route.fol,
        claim_type=ClaimType.fol,
        source_text=text,
        universal_subject=match.group("universal_subject").strip(),
        universal_predicate=match.group("universal_predicate").strip(),
        individual=individual,
        individual_subject=match.group("individual_subject").strip(),
        conclusion_predicate=match.group("conclusion_predicate").strip(),
    )


def classify_claim_type(text: str) -> ClaimType:
    stripped = text.strip()
    if not stripped:
        return ClaimType.unknown

    if _parse_fol_ir(stripped) is not None:
        return ClaimType.fol

    if _parse_propositional_ir(stripped) is not None:
        return ClaimType.propositional

    if _STATISTICAL_WORDS.search(stripped) or _P_VALUE_PATTERN.search(stripped):
        return ClaimType.statistical

    if _POLICY_WORDS.search(stripped):
        return ClaimType.policy_rule

    if _SUBJECTIVE_WORDS.search(stripped):
        return ClaimType.subjective

    if looks_like_formal_expression(stripped) or re.search(r"\$|\d+(?:\.\d+)?%|\d", stripped):
        return ClaimType.arithmetic

    if _FACTUAL_WORDS.search(stripped) or _looks_like_claim_statement(stripped):
        return ClaimType.factual

    return ClaimType.unknown


def choose_route(text: str, structured_claim: Optional[Claim]) -> RouteDecision:
    stripped = text.strip()
    if not stripped:
        return RouteDecision(route=Route.no_claim, claim_type=ClaimType.unknown, reason=ReasonCode.empty_input)

    if _is_schedule_or_metadata_text(stripped):
        return RouteDecision(
            route=Route.no_claim,
            claim_type=classify_claim_type(stripped),
            reason=ReasonCode.non_verification_text,
        )

    if structured_claim is not None:
        if structured_claim.insufficient_info:
            return RouteDecision(
                route=Route.insufficient_info,
                claim_type=ClaimType.arithmetic,
                reason=ReasonCode.missing_information,
                missing_info=structured_claim.missing_info,
                suggested_clarification=structured_claim.suggested_clarification,
                detected_values=[quantity.span_text for quantity in structured_claim.quantities],
            )

        return _build_ir_or_validation_failure(
            route=Route.structured,
            claim_type=ClaimType.arithmetic,
            reason=ReasonCode.structured_extraction,
            ir_builder=lambda: ArithmeticIR(
                route=Route.structured,
                claim_type=ClaimType.arithmetic,
                source_text=stripped,
                equation=structured_claim.equation,
                is_boolean=_looks_boolean_equation(structured_claim.equation),
                extraction_confidence=structured_claim.confidence,
            ),
        )

    fol_ir = _parse_fol_ir(stripped)
    if fol_ir is not None:
        return RouteDecision(route=Route.fol, claim_type=ClaimType.fol, reason=ReasonCode.fol_pattern, ir=fol_ir)

    propositional_ir = _parse_propositional_ir(stripped)
    if propositional_ir is not None:
        return RouteDecision(
            route=Route.propositional,
            claim_type=ClaimType.propositional,
            reason=ReasonCode.propositional_pattern,
            ir=propositional_ir,
        )

    if _STATISTICAL_WORDS.search(stripped) or _P_VALUE_PATTERN.search(stripped):
        p_value = _parse_float(_P_VALUE_PATTERN.search(stripped))
        alpha = _parse_float(_ALPHA_PATTERN.search(stripped))
        return _build_ir_or_validation_failure(
            route=Route.statistical,
            claim_type=ClaimType.statistical,
            reason=ReasonCode.statistical_claim,
            ir_builder=lambda: StatisticalIR(
                route=Route.statistical,
                claim_type=ClaimType.statistical,
                source_text=stripped,
                statement=stripped,
                p_value=p_value,
                alpha=alpha,
            ),
        )

    if _POLICY_WORDS.search(stripped):
        return _build_ir_or_validation_failure(
            route=Route.policy_rule,
            claim_type=ClaimType.policy_rule,
            reason=ReasonCode.policy_rule_claim,
            ir_builder=lambda: PolicyRuleIR(
                route=Route.policy_rule,
                claim_type=ClaimType.policy_rule,
                source_text=stripped,
                statement=stripped,
            ),
        )

    if _SUBJECTIVE_WORDS.search(stripped) and _looks_like_claim_statement(stripped):
        return _build_ir_or_validation_failure(
            route=Route.subjective,
            claim_type=ClaimType.subjective,
            reason=ReasonCode.subjective_claim,
            ir_builder=lambda: SubjectiveIR(
                route=Route.subjective,
                claim_type=ClaimType.subjective,
                source_text=stripped,
                opinion=stripped,
            ),
        )

    if looks_like_formal_expression(stripped):
        return _build_ir_or_validation_failure(
            route=Route.formal,
            claim_type=ClaimType.arithmetic,
            reason=ReasonCode.formal_expression,
            ir_builder=lambda: ArithmeticIR(
                route=Route.formal,
                claim_type=ClaimType.arithmetic,
                source_text=stripped,
                equation=stripped,
                is_boolean=_looks_boolean_equation(stripped),
                extraction_confidence=None,
            ),
        )

    if _FACTUAL_WORDS.search(stripped) or _looks_like_claim_statement(stripped):
        return _build_ir_or_validation_failure(
            route=Route.factual,
            claim_type=ClaimType.factual,
            reason=ReasonCode.factual_claim,
            ir_builder=lambda: FactualIR(
                route=Route.factual,
                claim_type=ClaimType.factual,
                source_text=stripped,
                proposition=stripped,
            ),
        )

    return RouteDecision(
        route=Route.no_claim,
        claim_type=ClaimType.unknown,
        reason=ReasonCode.no_verifiable_claim,
    )
