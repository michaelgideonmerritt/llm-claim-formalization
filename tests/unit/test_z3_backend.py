from pathlib import Path

from llm_claim_formalization.backends import verify_with_z3


def test_verify_true_boolean_claim() -> None:
    result = verify_with_z3("100 * (1 - 0.5) * (1 - 0.2) == 40")

    assert result["verified"] is True
    assert result["result"] == "unsat"


def test_verify_false_boolean_claim() -> None:
    result = verify_with_z3("100 * (1 - 0.5) * (1 - 0.2) == 50")

    assert result["verified"] is False
    assert result["result"] == "sat"


def test_compute_non_boolean_expression() -> None:
    result = verify_with_z3("100 * (1 - 0.5) * (1 - 0.2)")

    assert result["verified"] is None
    assert result["result"] == "computed"
    assert result["value_numeric"] == 40


def test_rejects_code_execution_payload() -> None:
    marker_path = Path("/tmp/llm_claim_formalization_z3_poc.txt")
    if marker_path.exists():
        marker_path.unlink()

    payload = "(__import__('pathlib').Path('/tmp/llm_claim_formalization_z3_poc.txt').write_text('owned'), True)[1]"
    result = verify_with_z3(payload)

    assert result["verified"] is False
    assert "Unsupported" in result["error"] or "Invalid" in result["error"]
    assert marker_path.exists() is False
