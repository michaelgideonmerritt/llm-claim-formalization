from llm_claim_formalization import extract_claim, verify_claim


def test_extract_claim_insufficient_info_for_missing_base() -> None:
    claim = extract_claim("A price increases by 100%")

    assert claim is not None
    assert claim.insufficient_info is True
    assert claim.missing_info == "missing_base_value"
    assert claim.suggested_clarification == "What is the original value or price?"


def test_verify_claim_routes_to_insufficient_info() -> None:
    result = verify_claim("A price increases by 100%")

    assert result.status == "insufficient_info"
    assert result.route == "insufficient_info"
    assert result.missing_info == "missing_base_value"
    assert result.suggested_clarification is not None


def test_verify_claim_routes_to_no_claim_for_non_claim_text() -> None:
    result = verify_claim("Please help me understand this concept")

    assert result.status == "no_claim"
    assert result.route == "no_claim"
