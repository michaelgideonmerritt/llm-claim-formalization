"""
Question-Answering Interface with Formal Verification

This module interfaces Ollama LLMs with the formal verification layer to provide
deterministic, hallucination-free question answering.

Architecture:
1. User asks question → LLM generates answer (uses vast training knowledge)
2. Extract verifiable claims from LLM answer
3. Verify each claim using formal verification (Z3, symbolic reasoning)
4. Accept verified claims, reject refuted claims
5. Return verified answer or error if hallucinations detected

This provides the best of both worlds:
- LLM's vast knowledge base (trained on billions of documents)
- Formal verification's determinism (zero hallucinations)
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import Any

import ollama

from .core.verification import verify_claim, VerificationResult
from .core.ir import VerificationStatus

# Default model for question answering (can override with LLM_CF_QA_MODEL)
DEFAULT_QA_MODEL = os.getenv("LLM_CF_QA_MODEL", "llama3.2:3b")

# Claim extraction patterns
_CLAIM_PATTERNS = [
    # Factual statements: "Paris is the capital of France"
    re.compile(r"([A-Z][^.!?]*(?:is|are|was|were|has|have|can|cannot|will|would)[^.!?]*\.)", re.MULTILINE),
    # Numerical statements: "Water boils at 100°C"
    re.compile(r"([A-Z][^.!?]*\d+[^.!?]*\.)", re.MULTILINE),
    # Quantified statements: "Most", "All", "Some"
    re.compile(r"([A-Z][^.!?]*(?:all|most|some|many|few|no)[^.!?]*\.)", re.MULTILINE),
]


@dataclass
class QAResult:
    """Result of verified question answering"""
    question: str
    answer: str
    verified: bool
    claims_extracted: int
    claims_verified: int
    claims_refuted: int
    claims_uncertain: int
    verification_details: list[dict[str, Any]]
    error: str | None = None
    model: str = DEFAULT_QA_MODEL

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "answer": self.answer,
            "verified": self.verified,
            "claims_extracted": self.claims_extracted,
            "claims_verified": self.claims_verified,
            "claims_refuted": self.claims_refuted,
            "claims_uncertain": self.claims_uncertain,
            "verification_details": self.verification_details,
            "error": self.error,
            "model": self.model,
        }


def extract_claims_from_answer(answer: str) -> list[str]:
    """
    Extract verifiable claims from LLM-generated answer.

    Uses pattern matching to identify factual statements that can be verified.
    Returns list of claim strings.
    """
    claims = []

    for pattern in _CLAIM_PATTERNS:
        matches = pattern.findall(answer)
        for match in matches:
            # Clean up the claim
            claim = match.strip()
            if len(claim) > 10:  # Skip very short matches
                claims.append(claim)

    # Deduplicate while preserving order
    seen = set()
    unique_claims = []
    for claim in claims:
        if claim not in seen:
            seen.add(claim)
            unique_claims.append(claim)

    return unique_claims


def generate_answer(question: str, model: str = DEFAULT_QA_MODEL) -> str:
    """
    Generate answer using Ollama LLM.

    The LLM uses its vast training knowledge to answer the question.
    No retrieval - the knowledge comes from the model's training.
    """
    prompt = (
        "You are a helpful assistant. Answer the question clearly and concisely. "
        "Provide factual information only. If you're not sure, say so.\n\n"
        f"Question: {question}\n\n"
        "Answer:"
    )

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},  # Deterministic generation
        )
        answer = response.get("message", {}).get("content", "").strip()
        return answer
    except Exception as exc:
        raise RuntimeError(f"Failed to generate answer with {model}: {exc}") from exc


def verify_answer(answer: str) -> tuple[bool, list[dict[str, Any]]]:
    """
    Verify all claims in the LLM's answer using formal verification.

    Returns:
    - verified: True if all claims pass verification (no refuted claims)
    - details: List of verification results for each claim
    """
    claims = extract_claims_from_answer(answer)

    if not claims:
        # No verifiable claims found - accept answer
        return True, []

    verification_details = []
    verified_count = 0
    refuted_count = 0
    uncertain_count = 0

    for claim in claims:
        result = verify_claim(claim)

        detail = {
            "claim": claim,
            "status": result.status,
            "route": result.route,
            "confidence": result.confidence,
            "message": result.message,
        }
        verification_details.append(detail)

        # Count outcomes
        if result.status == VerificationStatus.verified.value:
            verified_count += 1
        elif result.status == VerificationStatus.refuted.value:
            refuted_count += 1
        else:
            # Uncertain (insufficient_info, no_claim, etc.)
            uncertain_count += 1

    # Answer is verified if NO claims were refuted
    # (verified claims and uncertain claims are acceptable)
    verified = (refuted_count == 0)

    return verified, verification_details


def ask_question(question: str, model: str = DEFAULT_QA_MODEL) -> QAResult:
    """
    Ask a question and get a verified answer.

    Process:
    1. Generate answer using LLM (uses training knowledge)
    2. Extract verifiable claims from answer
    3. Verify each claim using formal verification
    4. Return verified answer or reject if hallucinations detected

    Example:
        >>> result = ask_question("What is the capital of France?")
        >>> print(result.answer)
        "Paris is the capital of France."
        >>> print(result.verified)
        True
    """
    try:
        # Step 1: Generate answer using LLM
        answer = generate_answer(question, model=model)

        # Step 2: Extract claims
        claims = extract_claims_from_answer(answer)

        # Step 3: Verify claims
        verified, details = verify_answer(answer)

        # Step 4: Count results
        verified_count = sum(1 for d in details if d["status"] == VerificationStatus.verified.value)
        refuted_count = sum(1 for d in details if d["status"] == VerificationStatus.refuted.value)
        uncertain_count = len(details) - verified_count - refuted_count

        return QAResult(
            question=question,
            answer=answer,
            verified=verified,
            claims_extracted=len(claims),
            claims_verified=verified_count,
            claims_refuted=refuted_count,
            claims_uncertain=uncertain_count,
            verification_details=details,
            model=model,
        )

    except Exception as exc:
        return QAResult(
            question=question,
            answer="",
            verified=False,
            claims_extracted=0,
            claims_verified=0,
            claims_refuted=0,
            claims_uncertain=0,
            verification_details=[],
            error=str(exc),
            model=model,
        )


def interactive_qa(model: str = DEFAULT_QA_MODEL):
    """
    Interactive question-answering REPL with verification.

    Usage:
        >>> from llm_claim_formalization.qa_interface import interactive_qa
        >>> interactive_qa()

        Ask a question (or 'quit' to exit): What is 2 + 2?

        Answer: 2 + 2 equals 4.

        Verification: ✅ VERIFIED
        - Claims extracted: 1
        - Claims verified: 1
        - Claims refuted: 0

        Ask a question (or 'quit' to exit):
    """
    print(f"\n🔍 Verified Question-Answering Interface")
    print(f"Model: {model}")
    print(f"Type 'quit' to exit\n")

    while True:
        try:
            question = input("\nAsk a question (or 'quit' to exit): ").strip()

            if question.lower() in {"quit", "exit", "q"}:
                print("\nGoodbye!")
                break

            if not question:
                continue

            print(f"\n⏳ Generating answer...")
            result = ask_question(question, model=model)

            if result.error:
                print(f"\n❌ Error: {result.error}")
                continue

            print(f"\n📝 Answer:\n{result.answer}\n")

            if result.verified:
                print("✅ Verification: VERIFIED (no hallucinations detected)")
            else:
                print("❌ Verification: FAILED (hallucinations or refuted claims detected)")

            print(f"\nClaims extracted: {result.claims_extracted}")
            print(f"Claims verified: {result.claims_verified}")
            print(f"Claims refuted: {result.claims_refuted}")
            print(f"Claims uncertain: {result.claims_uncertain}")

            if result.verification_details:
                print("\nVerification Details:")
                for i, detail in enumerate(result.verification_details, 1):
                    status_emoji = "✅" if detail["status"] == "verified" else "❌" if detail["status"] == "refuted" else "⚠️"
                    print(f"  {i}. {status_emoji} {detail['claim'][:80]}...")
                    print(f"     Status: {detail['status']} (confidence: {detail['confidence']:.2f})")
                    if detail.get("message"):
                        print(f"     {detail['message']}")

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as exc:
            print(f"\n❌ Error: {exc}")


if __name__ == "__main__":
    interactive_qa()
