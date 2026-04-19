from llm_claim_formalization import extract_claim


def test_single_discount_with_claimed_result_extracts_equation() -> None:
    claim = extract_claim("$100 with 50% off is $50")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "100.0* (1 - 0.5) == 50.0"
    assert claim.confidence >= 0.85


def test_compound_discount_without_claimed_result_extracts_expression() -> None:
    claim = extract_claim("$100 with 50% off then 20% off")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "100.0* (1 - 0.5)* (1 - 0.2)"


def test_rate_comparison_extracts_boolean_equation() -> None:
    claim = extract_claim("120 miles at 25 miles per gallon is less than 4 gallons")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "120.0 / 25.0 < 4.0"


def test_missing_base_value_flags_insufficient_info() -> None:
    claim = extract_claim("A price increases by 100%")

    assert claim is not None
    assert claim.insufficient_info is True
    assert claim.missing_info == "missing_base_value"
    assert claim.suggested_clarification is not None


def test_non_verifiable_text_returns_none() -> None:
    claim = extract_claim("Please help me understand this concept")

    assert claim is None
