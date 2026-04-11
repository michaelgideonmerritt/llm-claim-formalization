"""
Structured claim extractor with 3-stage pipeline.

Stage 1: Entity extraction (quantities with units)
Stage 2: Semantic normalization (operation types)
Stage 3: Equation synthesis (compile to formal math)
"""
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class Quantity:
    """A quantity with value, unit, and context."""
    value: float
    unit: str  # "dollars", "miles", "percent", "gallons", etc.
    span_text: str
    context_keywords: List[str]


@dataclass
class Operation:
    """A semantic operation to apply."""
    type: str  # "discount_percent", "relative_increase", "rate", "add", "subtract", etc.
    value: Optional[float] = None
    unit: Optional[str] = None
    applies_to: str = "current"  # "current", "base", "result"
    rate: Optional[Dict[str, Any]] = None


@dataclass
class Claim:
    """Structured claim with entities, operations, and compiled equation."""
    original_text: str
    quantities: List[Quantity]
    operations: List[Operation]
    equation: str
    confidence: float
    coverage_score: float  # 0.0-1.0: portion of quantities used in equation
    unused_quantities: List[Quantity]  # Quantities extracted but not used
    unresolved_spans: List[str]  # Text spans that look numeric but weren't extracted
    insufficient_info: bool = False  # True if missing critical information
    missing_info: Optional[str] = None  # Normalized reason code (e.g., "missing_base_value")
    suggested_clarification: Optional[str] = None  # User-friendly prompt to fix the issue


def extract_quantities(text: str) -> List[Quantity]:
    """
    Extract quantities with units and context.

    Examples:
    - "$100" → Quantity(100, "dollars", ...)
    - "25 miles per gallon" → Quantity(25, "rate_miles_per_gallon", ...)
    - "50%" → Quantity(50, "percent", ...)
    """
    quantities = []

    # Money: $X or X dollars
    for match in re.finditer(r'\$(\d+(?:\.\d+)?)', text):
        quantities.append(Quantity(
            value=float(match.group(1)),
            unit="dollars",
            span_text=match.group(0),
            context_keywords=_get_nearby_keywords(text, match.span())
        ))

    # Percentages: X%
    for match in re.finditer(r'(\d+(?:\.\d+)?)%', text):
        quantities.append(Quantity(
            value=float(match.group(1)),
            unit="percent",
            span_text=match.group(0),
            context_keywords=_get_nearby_keywords(text, match.span())
        ))

    # Rates: X miles per gallon, X per Y
    for match in re.finditer(r'(\d+(?:\.\d+)?)\s+([a-zA-Z]+)\s+per\s+([a-zA-Z]+)', text, re.I):
        numerator = match.group(2).lower()
        denominator = match.group(3).lower()

        # Normalize singular to plural to match quantity extraction
        if denominator == "gallon":
            denominator = "gallons"

        quantities.append(Quantity(
            value=float(match.group(1)),
            unit=f"rate_{numerator}_per_{denominator}",
            span_text=match.group(0),
            context_keywords=_get_nearby_keywords(text, match.span())
        ))

    # Plain numbers with units: X miles, X gallons
    # Also handle "less than X gallons", "more than X miles", etc.
    for match in re.finditer(r'(\d+(?:\.\d+)?)\s+(miles|gallons|hours|minutes|dollars|gallon)', text, re.I):
        # Skip if already captured as rate or money
        if any(q.span_text == match.group(0) for q in quantities):
            continue

        # Skip if this span overlaps with an existing quantity (e.g., "25 miles" in "25 miles per gallon")
        match_start, match_end = match.span()
        is_overlap = False
        for q in quantities:
            # Find existing quantity span in text
            try:
                q_start = text.find(q.span_text)
                q_end = q_start + len(q.span_text)
                # Check for overlap
                if not (match_end <= q_start or match_start >= q_end):
                    is_overlap = True
                    break
            except ValueError:
                continue

        if is_overlap:
            continue

        unit = match.group(2).lower()
        # Normalize "gallon" → "gallons"
        if unit == "gallon":
            unit = "gallons"

        quantities.append(Quantity(
            value=float(match.group(1)),
            unit=unit,
            span_text=match.group(0),
            context_keywords=_get_nearby_keywords(text, match.span())
        ))

    return quantities


def _get_nearby_keywords(text: str, span: tuple, window: int = 20) -> List[str]:
    """Extract keywords near the matched span."""
    start, end = span
    before = text[max(0, start - window):start].lower().split()
    after = text[end:min(len(text), end + window)].lower().split()
    return before[-3:] + after[:3]


def extract_operations(text: str, quantities: List[Quantity]) -> List[Operation]:
    """
    Extract semantic operations from text and quantities.

    Examples:
    - "50% discount" → Operation("discount_percent", value=0.5)
    - "increase by 100%" → Operation("relative_increase", value=1.0)
    - "spend $85" → Operation("subtract", value=85, unit="dollars")
    """
    operations = []
    text_lower = text.lower()

    # Percentage discount
    for match in re.finditer(r'(\d+(?:\.\d+)?)%\s*(off|discount)', text, re.I):
        percent = float(match.group(1))
        operations.append(Operation(
            type="discount_percent",
            value=percent / 100,
            applies_to="current"
        ))

    # Percentage increase
    for match in re.finditer(r'(increase|increases|increased)\s+by\s+(\d+(?:\.\d+)?)%', text, re.I):
        percent = float(match.group(2))
        operations.append(Operation(
            type="relative_increase",
            value=percent / 100,
            applies_to="current"
        ))

    # Percentage decrease
    for match in re.finditer(r'(decrease|decreases|decreased|drop|drops|dropped)\s+by\s+(\d+(?:\.\d+)?)%', text, re.I):
        percent = float(match.group(2))
        operations.append(Operation(
            type="relative_decrease",
            value=percent / 100,
            applies_to="current"
        ))

    # Rates (X per Y)
    for q in quantities:
        if q.unit.startswith("rate_"):
            # Parse rate unit: rate_miles_per_gallon → (miles, gallons)
            parts = q.unit.replace("rate_", "").split("_per_")
            if len(parts) == 2:
                operations.append(Operation(
                    type="rate",
                    rate={
                        "value": q.value,
                        "numerator_unit": parts[0],
                        "denominator_unit": parts[1]
                    }
                ))

    # Spending/subtracting - capture ALL dollar amounts after spending keywords
    spending_keywords = ["spend", "spent", "pay", "paid", "cost", "bill", "groceries"]
    for q in quantities:
        if q.unit == "dollars":
            # Check if this dollar amount appears AFTER a spending keyword
            text_before = text[:text.find(q.span_text)].lower()
            if any(word in text_before for word in spending_keywords):
                # Check it's not the initial balance by looking at 2 words IMMEDIATELY before
                # Example: "I have $200" → ["i", "have"] → has "have" → exclude
                # Example: "spend $85" → ["spend"] → no balance keywords → include
                words_before = text_before.strip().split()
                words_immediately_before = words_before[-2:] if len(words_before) >= 2 else words_before
                if not any(word in words_immediately_before for word in ["have", "had", "account", "balance", "start", "begin"]):
                    operations.append(Operation(
                        type="subtract",
                        value=q.value,
                        unit="dollars"
                    ))

    # Earning/adding
    earning_keywords = ["earn", "earned", "gain", "gained", "receive", "received"]
    for q in quantities:
        if q.unit == "dollars":
            text_before = text[:text.find(q.span_text)].lower()
            if any(word in text_before for word in earning_keywords):
                operations.append(Operation(
                    type="add",
                    value=q.value,
                    unit="dollars"
                ))

    return operations


def synthesize_equation(text: str, quantities: List[Quantity], operations: List[Operation]) -> tuple[str, float, List[Quantity]]:
    """
    Compile operations into a formal equation.

    Returns:
        - equation string (e.g., "100 * 0.5 * 0.8")
        - confidence score (0.0 to 1.0)
        - used_quantities: List of quantities actually used in the equation
    """
    text_lower = text.lower()
    used_quantities = []

    # Handle compound percentage discounts
    discount_ops = [op for op in operations if op.type == "discount_percent"]
    if len(discount_ops) >= 2:
        # Find base value (first dollar amount)
        base_values = [q for q in quantities if q.unit == "dollars"]
        if base_values:
            base = base_values[0].value
            used_quantities.append(base_values[0])  # Track base value

            # Track percentage quantities used in discounts
            for q in quantities:
                if q.unit == "percent":
                    used_quantities.append(q)

            # Apply discounts multiplicatively
            equation_parts = [str(base)]
            for op in discount_ops:
                equation_parts.append(f"* (1 - {op.value})")

            # Check for comparison
            if "save" in text_lower and "$" in text:
                # Looking for total savings
                final_price_expr = " ".join(equation_parts)
                savings = f"{base} - ({final_price_expr})"

                # Find claimed savings
                claimed_savings = [q for q in quantities if q.unit == "dollars" and "save" in q.context_keywords]
                if claimed_savings:
                    used_quantities.append(claimed_savings[0])
                    return f"{savings} = {claimed_savings[0].value}", 0.85, used_quantities

            return " ".join(equation_parts), 0.85, used_quantities

    # Handle rate problems (mpg, etc.)
    rate_ops = [op for op in operations if op.type == "rate"]
    if rate_ops:
        rate = rate_ops[0].rate
        # Find distance (numerator unit: miles)
        distances = [q for q in quantities if q.unit == rate["numerator_unit"]]

        if distances:
            distance = distances[0].value
            used_quantities.append(distances[0])  # Track distance quantity

            # Track the rate quantity (e.g., "25 miles per gallon")
            rate_quantity = [q for q in quantities if q.unit.startswith("rate_")]
            if rate_quantity:
                used_quantities.append(rate_quantity[0])

            # Find comparison value - look for gallons mentioned with comparison words
            comparison_val = None
            for q in quantities:
                if q.unit == rate["denominator_unit"]:
                    comparison_val = q.value
                    used_quantities.append(q)  # Track comparison quantity
                    break

            # Determine comparison operator
            if "less than" in text_lower or "fewer than" in text_lower or "under" in text_lower:
                if comparison_val:
                    return f"{distance} / {rate['value']} < {comparison_val}", 0.90, used_quantities
            elif "more than" in text_lower or "greater than" in text_lower or "over" in text_lower:
                if comparison_val:
                    return f"{distance} / {rate['value']} > {comparison_val}", 0.90, used_quantities
            else:
                # Just calculate the result
                return f"{distance} / {rate['value']}", 0.75, used_quantities

    # Handle simple budget arithmetic
    subtract_ops = [op for op in operations if op.type == "subtract"]
    if subtract_ops and any(q.unit == "dollars" for q in quantities):
        # Find base amount (first dollar amount with no spending keyword before it)
        base_values = []
        for q in quantities:
            if q.unit == "dollars":
                text_before_amount = text[:text.find(q.span_text)].lower()
                # Base value has no spending keywords before it
                if not any(word in text_before_amount.split() for word in ["spend", "spent", "pay", "paid", "cost", "bill"]):
                    base_values.append(q)

        if base_values:
            base = base_values[0].value
            used_quantities.append(base_values[0])  # Track base value

            # Track spending amounts
            for q in quantities:
                if q.unit == "dollars" and q != base_values[0]:
                    # This is likely a spending amount
                    used_quantities.append(q)

            equation_parts = [str(base)]
            for op in subtract_ops:
                equation_parts.append(f"- {op.value}")

            # Check for comparison
            if any(word in text_lower for word in ["have money left", "still have", "remaining"]):
                return " ".join(equation_parts) + " > 0", 0.90, used_quantities
            elif any(word in text_lower for word in ["broke", "no money", "overdraft"]):
                return " ".join(equation_parts) + " < 0", 0.90, used_quantities

            return " ".join(equation_parts), 0.80, used_quantities

    # Fallback: low confidence
    return "", 0.0, []


def _find_unresolved_numeric_spans(text: str, quantities: List[Quantity]) -> List[str]:
    """
    Find numeric patterns in text that weren't extracted as quantities.

    This helps detect:
    - Numbers without units that might be significant
    - Numbers in unusual formats that extraction missed
    - Numeric references that should have been captured
    """
    unresolved = []

    # Find all numeric patterns
    numeric_patterns = re.finditer(r'\b\d+(?:\.\d+)?\b', text)

    # Track which spans are already covered by extracted quantities
    covered_spans = set()
    for q in quantities:
        # Find the position of this quantity's span_text in the original text
        try:
            start_pos = text.find(q.span_text)
            if start_pos != -1:
                # Mark all character positions as covered
                for i in range(start_pos, start_pos + len(q.span_text)):
                    covered_spans.add(i)
        except ValueError:
            continue

    # Check each numeric pattern
    for match in numeric_patterns:
        span_start, span_end = match.span()
        # Is this span covered by an extracted quantity?
        is_covered = any(pos in covered_spans for pos in range(span_start, span_end))

        if not is_covered:
            # This numeric span wasn't extracted
            span_text = match.group(0)

            # Filter out likely non-significant numbers
            # (e.g., dates, times, years, small ordinals)
            try:
                val = float(span_text)
                # Skip very small numbers (likely ordinals like "2nd")
                # Skip likely years (1900-2100)
                if val < 1 or (1900 <= val <= 2100):
                    continue
            except ValueError:
                continue

            # Get surrounding context (10 chars before and after)
            context_start = max(0, span_start - 10)
            context_end = min(len(text), span_end + 10)
            context = text[context_start:context_end]

            unresolved.append(f"{span_text} ({context.strip()})")

    return unresolved


def _detect_insufficient_info(text: str, quantities: List[Quantity], operations: List[Operation]) -> tuple[bool, Optional[str], Optional[str]]:
    """
    Detect if the claim has insufficient information to solve.

    Returns:
        - is_insufficient: True if missing critical information
        - missing_description: Normalized reason code (e.g., "missing_base_value")
        - suggested_clarification: User-friendly prompt to fix the issue
    """
    # Mapping of reason codes to user-friendly clarification prompts
    CLARIFICATION_PROMPTS = {
        "missing_base_value": "What is the original value or price?",
        "missing_concrete_value": "What specific number should we apply this change to?",
        "missing_comparison_value": "What are you comparing this against?"
    }

    text_lower = text.lower()

    # Case 1: Relative percentage operations without base value
    # "A price increases by 100%" - we have the percentage but not the base price
    has_relative_percent = any(op.type in ["relative_increase", "relative_decrease"] for op in operations)
    has_discount_percent = any(op.type == "discount_percent" for op in operations)

    if has_relative_percent or has_discount_percent:
        # Check if we have a base value (dollar amount, numeric quantity)
        has_base = any(q.unit in ["dollars", "miles", "gallons", "hours"] for q in quantities)

        if not has_base:
            # Only percentages, no base value
            reason_code = "missing_base_value"
            return True, reason_code, CLARIFICATION_PROMPTS[reason_code]

    # Case 2: Operations without sufficient operands
    # "If something doubles" - abstract transformation without concrete value
    abstract_transformations = ["double", "triple", "halve", "twice"]
    if any(word in text_lower for word in abstract_transformations):
        # Check if we have any concrete numeric values
        has_concrete = len(quantities) > 0 and any(
            q.unit != "percent" for q in quantities
        )
        if not has_concrete:
            reason_code = "missing_concrete_value"
            return True, reason_code, CLARIFICATION_PROMPTS[reason_code]

    # Case 3: Only one quantity when operation requires two
    # "less than 5" without the value being compared
    comparison_words = ["less than", "more than", "greater than", "fewer than"]
    has_comparison = any(word in text_lower for word in comparison_words)

    if has_comparison and len(quantities) == 1:
        # Single quantity with comparison operator - missing the thing being compared
        reason_code = "missing_comparison_value"
        return True, reason_code, CLARIFICATION_PROMPTS[reason_code]

    return False, None, None


def extract_claim(text: str) -> Optional[Claim]:
    """
    Extract structured claim from natural language.

    Returns None if no verifiable claim detected.
    Returns Claim with insufficient_info=True if missing critical information.
    """
    # Stage 1: Entity extraction
    quantities = extract_quantities(text)

    # Check for insufficient info even with minimal quantities
    # This catches cases like "increase by 100%" with only percentages
    if quantities:
        operations = extract_operations(text, quantities)

        # Detect insufficient information BEFORE requiring 2+ quantities
        is_insufficient, missing_description, suggested_clarification = _detect_insufficient_info(text, quantities, operations)

        if is_insufficient:
            # Return special claim indicating insufficient info
            return Claim(
                original_text=text,
                quantities=quantities,
                operations=operations,
                equation="",  # No equation possible
                confidence=0.0,
                coverage_score=0.0,
                unused_quantities=quantities,  # All unused since no equation
                unresolved_spans=[],
                insufficient_info=True,
                missing_info=missing_description,
                suggested_clarification=suggested_clarification
            )

    if not quantities or len(quantities) < 2:
        return None

    # Stage 2: Semantic normalization
    operations = extract_operations(text, quantities)

    if not operations:
        return None

    # Stage 3: Equation synthesis
    equation, confidence, used_quantities = synthesize_equation(text, quantities, operations)

    if not equation or confidence < 0.5:
        return None

    # Calculate coverage score: what portion of quantities were used?
    coverage_score = len(used_quantities) / len(quantities) if quantities else 0.0

    # Find unused quantities
    unused = [q for q in quantities if q not in used_quantities]

    # Detect unresolved numeric spans (potential missed extractions)
    unresolved_spans = _find_unresolved_numeric_spans(text, quantities)

    return Claim(
        original_text=text,
        quantities=quantities,
        operations=operations,
        equation=equation,
        confidence=confidence,
        coverage_score=coverage_score,
        unused_quantities=unused,
        unresolved_spans=unresolved_spans,
        insufficient_info=False,
        missing_info=None
    )
