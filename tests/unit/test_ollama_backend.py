from typing import Any

from llm_claim_formalization.backends import ollama_backend


def _mock_response(content: str) -> dict[str, Any]:
    return {"message": {"content": content}}


def test_parses_true_verdict(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        return _mock_response("true")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_with_ollama("2 + 2 = 4")

    assert result["verdict"] == "true"
    assert result["verified"] is True


def test_parses_false_verdict_with_extra_text(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        return _mock_response("false\nReasoning omitted")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_with_ollama("2 + 2 = 5")

    assert result["verdict"] == "false"
    assert result["verified"] is False


def test_unknown_when_no_valid_token(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        return _mock_response("maybe")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_with_ollama("ambiguous claim")

    assert result["verdict"] == "unknown"
    assert result["verified"] is None


def test_returns_error_on_ollama_failure(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("ollama down")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_with_ollama("x")

    assert result["verdict"] == "error"
    assert result["verified"] is None
    assert "ollama down" in result["error"]


def test_entailment_parser_reads_label_and_confidence(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        return _mock_response("entailment\nconfidence=0.88")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_entailment_with_ollama("claim", "evidence")

    assert result["label"] == "entailment"
    assert result["confidence"] == 0.88


def test_entailment_defaults_to_neutral_when_missing_label(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        return _mock_response("maybe")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_entailment_with_ollama("claim", "evidence")

    assert result["label"] == "neutral"
    assert result["confidence"] is None


def test_entailment_returns_error_on_ollama_failure(monkeypatch) -> None:
    def fake_chat(*args, **kwargs):  # noqa: ANN002, ANN003
        raise RuntimeError("ollama down")

    monkeypatch.setattr(ollama_backend.ollama, "chat", fake_chat)
    result = ollama_backend.verify_entailment_with_ollama("claim", "evidence")

    assert result["label"] == "neutral"
    assert "ollama down" in result["error"]
