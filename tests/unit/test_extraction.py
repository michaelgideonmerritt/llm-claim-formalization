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


def test_mph_rate_comparison_more_than() -> None:
    claim = extract_claim("A train travels 300 miles at 60 mph. Does it take more than 4 hours?")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "300.0 / 60.0 > 4.0"
    assert claim.confidence >= 0.90


def test_percent_of_construction() -> None:
    claim = extract_claim("Is it true that 15% of 200 equals 30?")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "200.0 * 0.15 == 30.0"
    assert claim.confidence >= 0.88


def test_reverse_discount_original_price() -> None:
    claim = extract_claim("A product costs $80 after a 20% discount. Was the original price $100?")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "100.0 * (1 - 0.2) == 80.0"
    assert claim.confidence >= 0.88


def test_earn_and_spend_no_double_count() -> None:
    claim = extract_claim("I earn $5000 a month and spend $6000, do I have money left?")

    assert claim is not None
    assert claim.insufficient_info is False
    # $5000 earned (base), $6000 spent: 5000 - 6000 > 0
    assert claim.equation == "5000.0 - 6000.0 > 0"
    assert claim.confidence >= 0.88


def test_budget_with_spending_keywords() -> None:
    claim = extract_claim("I have $200 and spend $85 on groceries and $120 on rent, do I have money left?")

    assert claim is not None
    assert claim.insufficient_info is False
    assert claim.equation == "200.0 - 85.0 - 120.0 > 0"
    assert claim.confidence >= 0.88
