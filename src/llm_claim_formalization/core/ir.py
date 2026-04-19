from __future__ import annotations

from enum import Enum
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ClaimType(str, Enum):
    arithmetic = "arithmetic"
    propositional = "propositional"
    fol = "fol"
    statistical = "statistical"
    policy_rule = "policy_rule"
    factual = "factual"
    subjective = "subjective"
    unknown = "unknown"


class Route(str, Enum):
    structured = "structured"
    formal = "formal"
    propositional = "propositional"
    fol = "fol"
    statistical = "statistical"
    policy_rule = "policy_rule"
    factual = "factual"
    subjective = "subjective"
    insufficient_info = "insufficient_info"
    no_claim = "no_claim"


class VerificationStatus(str, Enum):
    verified = "verified"
    unverified = "unverified"
    computed = "computed"
    evidence_backed = "evidence_backed"
    llm_only = "llm_only"
    insufficient_info = "insufficient_info"
    no_claim = "no_claim"
    cannot_formally_verify = "cannot_formally_verify"
    error = "error"


class ReasonCode(str, Enum):
    empty_input = "empty_input"
    no_verifiable_claim = "no_verifiable_claim"
    non_verification_text = "non_verification_text"
    structured_extraction = "structured_extraction"
    formal_expression = "formal_expression"
    propositional_pattern = "propositional_pattern"
    fol_pattern = "fol_pattern"
    statistical_claim = "statistical_claim"
    policy_rule_claim = "policy_rule_claim"
    factual_claim = "factual_claim"
    subjective_claim = "subjective_claim"
    missing_information = "missing_information"
    missing_evidence_source = "missing_evidence_source"
    insufficient_evidence = "insufficient_evidence"
    conflicting_evidence = "conflicting_evidence"
    unsupported_policy_formalization = "unsupported_policy_formalization"
    unsupported_subjective_claim = "unsupported_subjective_claim"
    unsupported_statistical_formalization = "unsupported_statistical_formalization"
    unsupported_logical_structure = "unsupported_logical_structure"
    schema_validation_error = "schema_validation_error"
    backend_error = "backend_error"


class Citation(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    source_id: str = Field(min_length=1)
    title: str = Field(min_length=1)
    snippet: str = Field(min_length=1)
    score: float = Field(ge=0.0, le=1.0)
    stance: Literal["support", "contradict", "neutral"] = "neutral"
    url: Optional[str] = None


class BaseIR(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    route: Route
    claim_type: ClaimType
    source_text: str = Field(min_length=1, max_length=10000)


class ArithmeticIR(BaseIR):
    route: Literal[Route.structured, Route.formal]
    claim_type: Literal[ClaimType.arithmetic]
    equation: str = Field(min_length=1, max_length=2000)
    is_boolean: bool
    extraction_confidence: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class PropositionalIR(BaseIR):
    route: Literal[Route.propositional]
    claim_type: Literal[ClaimType.propositional]
    antecedent: str = Field(min_length=1, max_length=128)
    consequent: str = Field(min_length=1, max_length=128)
    second_premise: str = Field(min_length=1, max_length=128)
    conclusion: str = Field(min_length=1, max_length=128)


class FolIR(BaseIR):
    route: Literal[Route.fol]
    claim_type: Literal[ClaimType.fol]
    universal_subject: str = Field(min_length=1, max_length=128)
    universal_predicate: str = Field(min_length=1, max_length=128)
    individual: str = Field(min_length=1, max_length=128)
    individual_subject: str = Field(min_length=1, max_length=128)
    conclusion_predicate: str = Field(min_length=1, max_length=128)


class StatisticalIR(BaseIR):
    route: Literal[Route.statistical]
    claim_type: Literal[ClaimType.statistical]
    statement: str = Field(min_length=1, max_length=2000)
    p_value: Optional[float] = Field(default=None, ge=0.0, le=1.0)
    alpha: Optional[float] = Field(default=None, ge=0.0, le=1.0)


class PolicyRuleIR(BaseIR):
    route: Literal[Route.policy_rule]
    claim_type: Literal[ClaimType.policy_rule]
    statement: str = Field(min_length=1, max_length=2000)


class FactualIR(BaseIR):
    route: Literal[Route.factual]
    claim_type: Literal[ClaimType.factual]
    proposition: str = Field(min_length=1, max_length=2000)


class SubjectiveIR(BaseIR):
    route: Literal[Route.subjective]
    claim_type: Literal[ClaimType.subjective]
    opinion: str = Field(min_length=1, max_length=2000)


ClaimIR = ArithmeticIR | PropositionalIR | FolIR | StatisticalIR | PolicyRuleIR | FactualIR | SubjectiveIR
