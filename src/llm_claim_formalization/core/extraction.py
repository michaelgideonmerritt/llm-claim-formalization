"""
Structured claim extractor with a lightweight 3-stage pipeline.

Stage 1: Entity extraction (quantities with units)
Stage 2: Semantic normalization (operation types)
Stage 3: Equation synthesis (compile to formal math)
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Optional


@dataclass
class Quantity:
    """A quantity with value, unit, and context."""

    value: float
    unit: str
    span_text: str
    context_keywords: list[str]


@dataclass
class Operation:
    """A semantic operation to apply."""

    type: str
    value: Optional[float] = None
    unit: Optional[str] = None
    applies_to: str = "current"
    rate: Optional[dict[str, Any]] = None


@dataclass
class Claim:
    """Structured claim with entities, operations, and compiled equation."""

    original_text: str
    quantities: list[Quantity]
    operations: list[Operation]
    equation: str
    confidence: float
    coverage_score: float
    unused_quantities: list[Quantity]
    unresolved_spans: list[str]
    insufficient_info: bool = False
    missing_info: Optional[str] = None
    suggested_clarification: Optional[str] = None


def extract_quantities(text: str) -> list[Quantity]:
    """Extract numeric quantities with units from natural language text."""
    quantities: list[Quantity] = []

    # Money: $X
    for match in re.finditer(r"\$(\d+(?:\.\d+)?)", text):
        quantities.append(
            Quantity(
                value=float(match.group(1)),
                unit="dollars",
                span_text=match.group(0),
                context_keywords=_get_nearby_keywords(text, match.span()),
            )
        )

    # Percentages: X%
    for match in re.finditer(r"(\d+(?:\.\d+)?)%", text):
        quantities.append(
            Quantity(
                value=float(match.group(1)),
                unit="percent",
                span_text=match.group(0),
                context_keywords=_get_nearby_keywords(text, match.span()),
            )
        )

    # Rates: X miles per gallon, X per Y
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s+([a-zA-Z]+)\s+per\s+([a-zA-Z]+)", text, re.I):
        numerator = match.group(2).lower()
        denominator = _normalize_unit(match.group(3).lower())
        quantities.append(
            Quantity(
                value=float(match.group(1)),
                unit=f"rate_{numerator}_per_{denominator}",
                span_text=match.group(0),
                context_keywords=_get_nearby_keywords(text, match.span()),
            )
        )

    unit_pattern = (
        r"miles|mile|gallons|gallon|hours|hour|minutes|minute|"
        r"seconds|second|days|day|years|year|dollars|dollar|"
        r"ms|users|requests|errors|items|units"
    )
    for match in re.finditer(rf"(\d+(?:\.\d+)?)\s+({unit_pattern})\b", text, re.I):
        span_text = match.group(0)
        if any(existing.span_text == span_text for existing in quantities):
            continue

        unit = _normalize_unit(match.group(2).lower())
        quantities.append(
            Quantity(
                value=float(match.group(1)),
                unit=unit,
                span_text=span_text,
                context_keywords=_get_nearby_keywords(text, match.span()),
            )
        )

    return quantities


def extract_operations(text: str, quantities: list[Quantity]) -> list[Operation]:
    """Extract operation semantics from text and quantities."""
    operations: list[Operation] = []

    for match in re.finditer(r"(\d+(?:\.\d+)?)%\s*(off|discount)", text, re.I):
        operations.append(Operation(type="discount_percent", value=float(match.group(1)) / 100))

    for match in re.finditer(
        r"(increase|increases|increased|up|rose|grew|higher)\s+(?:by\s+)?(\d+(?:\.\d+)?)%", text, re.I
    ):
        operations.append(Operation(type="relative_increase", value=float(match.group(2)) / 100))

    for match in re.finditer(
        r"(decrease|decreases|decreased|down|drop|drops|dropped|fell|lower)\s+(?:by\s+)?(\d+(?:\.\d+)?)%",
        text,
        re.I,
    ):
        operations.append(Operation(type="relative_decrease", value=float(match.group(2)) / 100))

    for quantity in quantities:
        if quantity.unit.startswith("rate_"):
            parts = quantity.unit.replace("rate_", "").split("_per_")
            if len(parts) == 2:
                operations.append(
                    Operation(
                        type="rate",
                        rate={
                            "value": quantity.value,
                            "numerator_unit": parts[0],
                            "denominator_unit": parts[1],
                        },
                    )
                )

    spending_keywords = ["spend", "spent", "pay", "paid", "cost", "bill", "bought", "purchase"]
    earning_keywords = ["earn", "earned", "gain", "gained", "receive", "received", "deposit", "deposited"]

    for quantity in quantities:
        if quantity.unit != "dollars":
            continue

        before = text[: max(0, text.find(quantity.span_text))].lower()
        immediate_words = before.strip().split()[-3:]

        if any(keyword in before for keyword in spending_keywords) and not any(
            word in immediate_words for word in ["have", "had", "start", "began", "begin", "balance", "with"]
        ):
            operations.append(Operation(type="subtract", value=quantity.value, unit="dollars"))
            continue

        if any(keyword in before for keyword in earning_keywords):
            operations.append(Operation(type="add", value=quantity.value, unit="dollars"))

    return operations


def synthesize_equation(
    text: str, quantities: list[Quantity], operations: list[Operation]
) -> tuple[str, float, list[Quantity]]:
    """Compile quantities and operations into an equation or expression."""
    text_lower = text.lower()
    used_quantities: list[Quantity] = []

    # Rate problems first.
    rate_ops = [operation for operation in operations if operation.type == "rate" and operation.rate]
    if rate_ops:
        rate = rate_ops[0].rate
        if rate is not None:
            distances = [quantity for quantity in quantities if quantity.unit == rate["numerator_unit"]]
            rate_quantities = [quantity for quantity in quantities if quantity.unit.startswith("rate_")]
            comparisons = [quantity for quantity in quantities if quantity.unit == rate["denominator_unit"]]

            if distances:
                distance = distances[0]
                used_quantities.append(distance)
                if rate_quantities:
                    used_quantities.append(rate_quantities[0])

                expr = f"{distance.value} / {rate['value']}"
                if comparisons and any(word in text_lower for word in ["less than", "fewer than", "under"]):
                    used_quantities.append(comparisons[0])
                    return f"{expr} < {comparisons[0].value}", 0.92, used_quantities

                if comparisons and any(word in text_lower for word in ["more than", "greater than", "over", "above"]):
                    used_quantities.append(comparisons[0])
                    return f"{expr} > {comparisons[0].value}", 0.92, used_quantities

                return expr, 0.78, used_quantities

    # Budget arithmetic: base +/- transactions.
    subtract_ops = [operation for operation in operations if operation.type == "subtract" and operation.value is not None]
    add_ops = [operation for operation in operations if operation.type == "add" and operation.value is not None]
    if (subtract_ops or add_ops) and any(quantity.unit == "dollars" for quantity in quantities):
        base_quantities = _find_base_money_quantities(text, quantities)
        if base_quantities:
            base = base_quantities[0]
            used_quantities.append(base)

            parts = [str(base.value)]
            for operation in add_ops:
                parts.append(f"+ {operation.value}")
            for operation in subtract_ops:
                parts.append(f"- {operation.value}")

            for quantity in quantities:
                if quantity.unit == "dollars" and quantity != base:
                    used_quantities.append(quantity)

            expr = " ".join(parts)

            if any(word in text_lower for word in ["still have", "money left", "remaining", "left over"]):
                return f"{expr} > 0", 0.90, used_quantities

            if any(word in text_lower for word in ["broke", "overdraft", "below zero", "negative"]):
                return f"{expr} < 0", 0.90, used_quantities

            claimed = _find_claimed_value_for_unit(text, quantities, "dollars", skip=base)
            if claimed:
                used_quantities.append(claimed)
                return f"{expr} == {claimed.value}", 0.88, used_quantities

            return expr, 0.82, used_quantities

    # Percentage transformations (discount/increase/decrease).
    percent_ops = [
        operation
        for operation in operations
        if operation.type in {"discount_percent", "relative_increase", "relative_decrease"} and operation.value is not None
    ]
    if percent_ops:
        percent_base = _select_percentage_base(quantities)
        if percent_base:
            used_quantities.append(percent_base)

            factors: list[str] = []
            for operation in percent_ops:
                if operation.type in {"discount_percent", "relative_decrease"}:
                    factors.append(f"* (1 - {operation.value})")
                else:
                    factors.append(f"* (1 + {operation.value})")

            for quantity in quantities:
                if quantity.unit == "percent":
                    used_quantities.append(quantity)

            expr = f"{percent_base.value}{''.join(factors)}"
            claimed = _find_claimed_value_for_unit(text, quantities, percent_base.unit, skip=percent_base)
            if claimed:
                used_quantities.append(claimed)
                return f"{expr} == {claimed.value}", 0.90, used_quantities

            return expr, 0.84, used_quantities

    return "", 0.0, []


def extract_claim(text: str) -> Optional[Claim]:
    """
    Extract structured claim from natural language.

    Returns None if no verifiable structured claim is detected.
    """
    quantities = extract_quantities(text)

    if quantities:
        operations = extract_operations(text, quantities)
        is_insufficient, missing_info, suggested = _detect_insufficient_info(text, quantities, operations)
        if is_insufficient:
            return Claim(
                original_text=text,
                quantities=quantities,
                operations=operations,
                equation="",
                confidence=0.0,
                coverage_score=0.0,
                unused_quantities=quantities,
                unresolved_spans=[],
                insufficient_info=True,
                missing_info=missing_info,
                suggested_clarification=suggested,
            )

    if not quantities or len(quantities) < 2:
        return None

    operations = extract_operations(text, quantities)
    if not operations:
        return None

    equation, confidence, used_quantities = synthesize_equation(text, quantities, operations)
    if not equation or confidence < 0.5:
        return None

    coverage_score = len(used_quantities) / len(quantities) if quantities else 0.0
    unused_quantities = [quantity for quantity in quantities if quantity not in used_quantities]
    unresolved_spans = _find_unresolved_numeric_spans(text, quantities)

    return Claim(
        original_text=text,
        quantities=quantities,
        operations=operations,
        equation=equation,
        confidence=confidence,
        coverage_score=coverage_score,
        unused_quantities=unused_quantities,
        unresolved_spans=unresolved_spans,
        insufficient_info=False,
        missing_info=None,
        suggested_clarification=None,
    )


def _normalize_unit(unit: str) -> str:
    singular_map = {
        "mile": "miles",
        "gallon": "gallons",
        "hour": "hours",
        "minute": "minutes",
        "second": "seconds",
        "day": "days",
        "year": "years",
        "dollar": "dollars",
    }
    return singular_map.get(unit, unit)


def _get_nearby_keywords(text: str, span: tuple[int, int], window: int = 24) -> list[str]:
    start, end = span
    before = text[max(0, start - window) : start].lower().split()
    after = text[end : min(len(text), end + window)].lower().split()
    return before[-3:] + after[:3]


def _find_base_money_quantities(text: str, quantities: list[Quantity]) -> list[Quantity]:
    bases: list[Quantity] = []
    for quantity in quantities:
        if quantity.unit != "dollars":
            continue

        before = text[: max(0, text.find(quantity.span_text))].lower()
        if any(keyword in before.split() for keyword in ["spend", "spent", "pay", "paid", "cost", "bill", "bought"]):
            continue
        bases.append(quantity)

    return bases


def _select_percentage_base(quantities: list[Quantity]) -> Optional[Quantity]:
    non_percent_quantities = [quantity for quantity in quantities if quantity.unit != "percent" and not quantity.unit.startswith("rate_")]
    if non_percent_quantities:
        return non_percent_quantities[0]

    dollar_quantities = [quantity for quantity in quantities if quantity.unit == "dollars"]
    return dollar_quantities[0] if dollar_quantities else None


def _find_claimed_value_for_unit(
    text: str,
    quantities: list[Quantity],
    unit: str,
    skip: Optional[Quantity] = None,
) -> Optional[Quantity]:
    candidates = [quantity for quantity in quantities if quantity.unit == unit and quantity != skip]
    if not candidates:
        return None

    cue_pattern = re.compile(
        r"(?:is|equals?|=|to|at|was|were|final(?:\s+price|\s+amount)?|remaining|left)\s*\$?(\d+(?:\.\d+)?)",
        re.I,
    )
    cue_matches = [float(match.group(1)) for match in cue_pattern.finditer(text)]
    if cue_matches:
        for value in reversed(cue_matches):
            for candidate in reversed(candidates):
                if abs(candidate.value - value) < 1e-9:
                    return candidate

    # Fallback: likely final value is last quantity of the same unit.
    return candidates[-1]


def _find_unresolved_numeric_spans(text: str, quantities: list[Quantity]) -> list[str]:
    unresolved: list[str] = []
    covered_spans: set[int] = set()

    for quantity in quantities:
        start = text.find(quantity.span_text)
        if start == -1:
            continue
        for position in range(start, start + len(quantity.span_text)):
            covered_spans.add(position)

    for match in re.finditer(r"\b\d+(?:\.\d+)?\b", text):
        start, end = match.span()
        if any(position in covered_spans for position in range(start, end)):
            continue

        raw_value = match.group(0)
        try:
            numeric_value = float(raw_value)
        except ValueError:
            continue

        if numeric_value < 1 or (1900 <= numeric_value <= 2100):
            continue

        context_start = max(0, start - 10)
        context_end = min(len(text), end + 10)
        context = text[context_start:context_end].strip()
        unresolved.append(f"{raw_value} ({context})")

    return unresolved


def _detect_insufficient_info(
    text: str,
    quantities: list[Quantity],
    operations: list[Operation],
) -> tuple[bool, Optional[str], Optional[str]]:
    clarification_prompts = {
        "missing_base_value": "What is the original value or price?",
        "missing_concrete_value": "What specific number should we apply this change to?",
        "missing_comparison_value": "What are you comparing this against?",
    }

    text_lower = text.lower()

    has_relative_percent = any(operation.type in {"relative_increase", "relative_decrease", "discount_percent"} for operation in operations)
    if has_relative_percent:
        has_base = any(
            quantity.unit in {"dollars", "miles", "gallons", "hours", "minutes", "days", "years"}
            for quantity in quantities
        )
        if not has_base:
            return True, "missing_base_value", clarification_prompts["missing_base_value"]

    if any(word in text_lower for word in ["double", "doubles", "triple", "halve", "twice"]):
        has_concrete = any(quantity.unit != "percent" for quantity in quantities)
        if not has_concrete:
            return True, "missing_concrete_value", clarification_prompts["missing_concrete_value"]

    comparison_words = ["less than", "more than", "greater than", "fewer than", "under", "over"]
    if any(word in text_lower for word in comparison_words) and len(quantities) == 1:
        return True, "missing_comparison_value", clarification_prompts["missing_comparison_value"]

    return False, None, None
