from __future__ import annotations

import os
import re
from typing import Any

# Bridge common env naming used by local tooling to the official Ollama Python client env key.
if "OLLAMA_HOST" not in os.environ and os.getenv("OLLAMA_API_BASE"):
    os.environ["OLLAMA_HOST"] = os.environ["OLLAMA_API_BASE"]

import ollama

DEFAULT_MODEL = os.getenv("LLM_CF_OLLAMA_MODEL", "lfm2.5-thinking-128k:latest")
_VERDICT_PATTERN = re.compile(r"\b(true|false|unknown)\b", flags=re.IGNORECASE)
_ENTAILMENT_PATTERN = re.compile(r"\b(entailment|contradiction|neutral)\b", flags=re.IGNORECASE)


def _parse_verdict(raw_response: str) -> str:
    """
    Parse a strict tri-state verdict from model output.

    Returns one of: "true", "false", "unknown".
    """
    match = _VERDICT_PATTERN.search(raw_response.strip())
    if not match:
        return "unknown"
    return match.group(1).lower()


def _parse_entailment_label(raw_response: str) -> str:
    """
    Parse strict NLI label from model output.

    Returns one of: "entailment", "contradiction", "neutral".
    """
    match = _ENTAILMENT_PATTERN.search(raw_response.strip())
    if not match:
        return "neutral"
    return match.group(1).lower()


def _parse_confidence(raw_response: str) -> float | None:
    match = re.search(r"(?:confidence|score)\s*[:=]\s*(0(?:\.\d+)?|1(?:\.0+)?)", raw_response, flags=re.I)
    if not match:
        return None
    try:
        return float(match.group(1))
    except ValueError:
        return None


def verify_with_ollama(claim: str, model: str = DEFAULT_MODEL) -> dict[str, Any]:
    """
    Verify a claim with a local Ollama model.

    Returns a tri-state verdict:
    - true: model believes claim is true
    - false: model believes claim is false
    - unknown: model cannot determine from provided claim text
    """
    prompt = (
        "You are a strict claim verifier. "
        "Given only the claim text, output exactly one token: true, false, or unknown.\n\n"
        f"Claim: {claim}\n\n"
        "Verdict:"
    )

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
    except Exception as exc:
        return {
            "verified": None,
            "verdict": "error",
            "model": model,
            "raw_response": "",
            "error": str(exc),
        }

    raw_response = response.get("message", {}).get("content", "").strip()
    verdict = _parse_verdict(raw_response)

    if verdict == "true":
        verified: bool | None = True
    elif verdict == "false":
        verified = False
    else:
        verified = None

    return {
        "verified": verified,
        "verdict": verdict,
        "model": model,
        "raw_response": raw_response,
    }


def verify_entailment_with_ollama(
    claim: str,
    evidence: str,
    model: str = DEFAULT_MODEL,
) -> dict[str, Any]:
    """
    Classify whether evidence entails, contradicts, or is neutral to a claim.

    Returns:
    - label: entailment | contradiction | neutral
    - confidence: optional score in [0, 1] if model provided one
    """
    prompt = (
        "You are a strict textual entailment classifier.\n"
        "Given CLAIM and EVIDENCE, output exactly one label token: entailment, contradiction, or neutral.\n"
        "Optionally include confidence as 'confidence=<0..1>'.\n\n"
        f"CLAIM: {claim}\n"
        f"EVIDENCE: {evidence}\n\n"
        "Label:"
    )

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},
        )
    except Exception as exc:
        return {
            "label": "neutral",
            "confidence": None,
            "model": model,
            "raw_response": "",
            "error": str(exc),
        }

    raw_response = response.get("message", {}).get("content", "").strip()
    label = _parse_entailment_label(raw_response)
    confidence = _parse_confidence(raw_response)
    return {
        "label": label,
        "confidence": confidence,
        "model": model,
        "raw_response": raw_response,
    }
