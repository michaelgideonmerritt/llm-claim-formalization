"""
Verified Question-Answering with LLM Feedback Loop

Architecture:
1. User asks question
2. Verifier: What type of question is this? (routing)
3. LLM: Generate answer using vast training knowledge
4. Verifier: Is this deterministic and logical?
   - YES → Send to user
   - NO → Send back to LLM with rejection reason
5. LLM: Fix and retry
6. Loop until verified or max retries reached

This creates a self-correcting system:
- LLM provides knowledge
- Verifier ensures correctness
- Feedback loop eliminates hallucinations
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import ollama

from .core.verification import verify_claim
from .core.routing import choose_route
from .core.extraction import extract_claim
from .core.ir import VerificationStatus, Route

# Configuration
DEFAULT_MODEL = os.getenv("LLM_CF_QA_MODEL", "llama3.2:3b")
MAX_RETRIES = int(os.getenv("LLM_CF_MAX_RETRIES", "3"))


@dataclass
class VerifiedAnswer:
    """Result of verified question-answering with feedback loop"""
    question: str
    answer: str
    verified: bool
    attempts: int
    question_type: str  # Route assigned by verifier
    rejection_history: list[dict[str, Any]]
    final_verification: dict[str, Any]
    error: str | None = None


def classify_question(question: str) -> dict[str, Any]:
    """
    Step 1: Verifier classifies the question type.

    This determines what kind of answer is expected and how to verify it.

    Returns:
        - route: arithmetic, logic, factual, etc.
        - claim_type: formal, structured, factual, etc.
        - needs_verification: whether formal verification applies
    """
    # Extract structured claim if possible
    structured = extract_claim(question)

    # Route the question
    decision = choose_route(question, structured)

    return {
        "route": decision.route.value,
        "claim_type": decision.claim_type.value,
        "reason": decision.reason.value,
        "needs_verification": decision.route not in {Route.no_claim, Route.insufficient_info},
        "suggested_clarification": decision.suggested_clarification,
    }


def generate_llm_answer(
    question: str,
    rejection_feedback: str | None = None,
    model: str = DEFAULT_MODEL,
) -> str:
    """
    Step 2: LLM generates answer.

    If this is a retry (rejection_feedback provided), the LLM is told
    why its previous answer was rejected and asked to fix it.

    Args:
        question: Original user question
        rejection_feedback: Why previous answer was rejected (if retry)
        model: Ollama model to use

    Returns:
        LLM-generated answer
    """
    if rejection_feedback:
        # Retry with feedback
        prompt = (
            "You are a helpful assistant. Your previous answer was rejected by the verification system.\n\n"
            f"Original question: {question}\n\n"
            f"Rejection reason: {rejection_feedback}\n\n"
            "Please provide a corrected answer that addresses the verification failure. "
            "Be precise, factual, and avoid speculation.\n\n"
            "Corrected answer:"
        )
    else:
        # First attempt
        prompt = (
            "You are a helpful assistant. Answer the question clearly, concisely, and factually. "
            "Provide specific facts and numbers when relevant. Avoid speculation.\n\n"
            f"Question: {question}\n\n"
            "Answer:"
        )

    try:
        response = ollama.chat(
            model=model,
            messages=[{"role": "user", "content": prompt}],
            options={"temperature": 0.0},  # Deterministic
        )
        return response.get("message", {}).get("content", "").strip()
    except Exception as exc:
        raise RuntimeError(f"LLM generation failed: {exc}") from exc


def verify_llm_answer(answer: str, question_type: str) -> dict[str, Any]:
    """
    Step 3: Verifier checks if answer is deterministic and logical.

    Uses formal verification to check claims in the answer.

    Returns:
        - verified: True if answer passes verification
        - status: verified/refuted/insufficient_info/etc.
        - rejection_reason: Why answer was rejected (if verified=False)
        - details: Full verification result
    """
    import re

    # Extract verifiable claim from answer
    # For math: extract "2 + 2 = 4" or "2 + 2 is 4" from natural language
    claim = answer

    # Pattern 1: "The answer to X is Y" → "X = Y"
    match = re.search(r'(?:answer|result)\s+(?:to|is)\s+(.+?)\s+(?:is|equals)\s+(.+?)[\s.]', claim, re.IGNORECASE)
    if match:
        claim = f"{match.group(1).strip()} = {match.group(2).strip()}"
    else:
        # Pattern 2: Simple "X is Y" or "X equals Y"
        # But only if X contains math operators
        match = re.search(r'([\d\s+\-*/().]+)\s+(?:is|equals)\s+([\d\s+\-*/().]+)', claim, re.IGNORECASE)
        if match:
            claim = f"{match.group(1).strip()} = {match.group(2).strip()}"
        else:
            # Fallback: just substitute is/equals with =
            claim = re.sub(r'\bis\b', '=', claim, flags=re.IGNORECASE)
            claim = re.sub(r'\bequals\b', '=', claim, flags=re.IGNORECASE)
            # Remove sentence starters only if what's left looks like math
            cleaned = re.sub(r'^(The answer (to|is)|The result is|It is)\s+', '', claim, flags=re.IGNORECASE)
            if re.search(r'[\d+\-*/=]', cleaned):  # Contains numbers or operators
                claim = cleaned

    claim = claim.strip(' .')

    # Verify the extracted claim
    result = verify_claim(claim)

    verified = (result.status == VerificationStatus.verified.value)

    # Build rejection reason if not verified
    rejection_reason = None
    if not verified:
        if result.status == VerificationStatus.unverified.value:
            rejection_reason = (
                f"Your answer was logically refuted or unverified. "
                f"Status: {result.status}. "
                f"Message: {result.message}. "
                f"The claim does not hold under formal verification. "
                f"Please provide a factually correct answer."
            )
        elif result.status == VerificationStatus.insufficient_info.value:
            rejection_reason = (
                f"Your answer lacks sufficient information for verification. "
                f"Message: {result.message}. "
                f"Please provide more specific, verifiable facts."
            )
        elif result.status == VerificationStatus.no_claim.value:
            rejection_reason = (
                f"Your answer does not contain a verifiable claim. "
                f"Please provide a specific, factual answer."
            )
        else:
            rejection_reason = (
                f"Verification failed with status: {result.status}. "
                f"Message: {result.message or 'Unknown error'}."
            )

    return {
        "verified": verified,
        "status": result.status,
        "route": result.route,
        "confidence": result.confidence,
        "message": result.message,
        "rejection_reason": rejection_reason,
        "full_result": result.to_dict(),
    }


def ask_verified_question(
    question: str,
    model: str = DEFAULT_MODEL,
    max_retries: int = MAX_RETRIES,
) -> VerifiedAnswer:
    """
    Main entry point: Ask a question with verification feedback loop.

    Process:
    1. Classify question type (verifier routing)
    2. LLM generates answer
    3. Verify answer
    4. If verified → return to user
    5. If not verified → feedback to LLM, retry
    6. Loop until verified or max retries

    Args:
        question: User's question
        model: Ollama model to use
        max_retries: Maximum retry attempts

    Returns:
        VerifiedAnswer with final result

    Example:
        >>> result = ask_verified_question("What is 2 + 2?")
        >>> print(result.answer)
        "2 + 2 = 4"
        >>> print(result.verified)
        True
    """
    try:
        # Step 1: Classify question
        classification = classify_question(question)
        question_type = classification["route"]

        # Track rejection history
        rejection_history = []

        # Feedback loop
        answer = None
        verification = None
        feedback = None

        for attempt in range(max_retries):
            # Step 2: LLM generates answer (with feedback if retry)
            answer = generate_llm_answer(question, rejection_feedback=feedback, model=model)

            # Step 3: Verify answer
            verification = verify_llm_answer(answer, question_type)

            # Step 4: Check if verified
            if verification["verified"]:
                # SUCCESS - send to user
                return VerifiedAnswer(
                    question=question,
                    answer=answer,
                    verified=True,
                    attempts=attempt + 1,
                    question_type=question_type,
                    rejection_history=rejection_history,
                    final_verification=verification,
                )

            # Step 5: Not verified - prepare feedback for retry
            rejection_history.append({
                "attempt": attempt + 1,
                "answer": answer,
                "status": verification["status"],
                "rejection_reason": verification["rejection_reason"],
            })

            feedback = verification["rejection_reason"]

        # Max retries reached - return unverified answer
        return VerifiedAnswer(
            question=question,
            answer=answer,
            verified=False,
            attempts=max_retries,
            question_type=question_type,
            rejection_history=rejection_history,
            final_verification=verification,
            error=f"Failed to generate verified answer after {max_retries} attempts",
        )

    except Exception as exc:
        return VerifiedAnswer(
            question=question,
            answer="",
            verified=False,
            attempts=0,
            question_type="unknown",
            rejection_history=[],
            final_verification={},
            error=str(exc),
        )


def interactive_verified_qa(model: str = DEFAULT_MODEL):
    """
    Interactive REPL for verified question-answering.

    Shows the feedback loop in action:
    - LLM answers
    - Verifier checks
    - Rejection feedback
    - LLM retries
    """
    print("\n" + "="*70)
    print("🔍 Verified Question-Answering with Feedback Loop")
    print("="*70)
    print(f"\nModel: {model}")
    print(f"Max retries: {MAX_RETRIES}")
    print("\nArchitecture:")
    print("  1. Verifier classifies question type")
    print("  2. LLM generates answer")
    print("  3. Verifier checks answer")
    print("  4. If failed → feedback to LLM → retry")
    print("  5. Loop until verified or max retries")
    print("\nType 'quit' to exit\n")

    while True:
        try:
            question = input("\n❓ Ask a question: ").strip()

            if question.lower() in {"quit", "exit", "q"}:
                print("\nGoodbye!")
                break

            if not question:
                continue

            print(f"\n{'='*70}")
            result = ask_verified_question(question, model=model)

            if result.error:
                print(f"❌ Error: {result.error}")
                continue

            # Show attempts
            print(f"\n📊 Attempts: {result.attempts}")
            print(f"📋 Question type: {result.question_type}")

            # Show rejection history
            if result.rejection_history:
                print(f"\n🔄 Rejection History:")
                for rejection in result.rejection_history:
                    print(f"\n  Attempt {rejection['attempt']}:")
                    print(f"    Answer: {rejection['answer'][:100]}...")
                    print(f"    Status: {rejection['status']}")
                    print(f"    Reason: {rejection['rejection_reason']}")

            # Show final answer
            print(f"\n{'='*70}")
            if result.verified:
                print("✅ VERIFIED ANSWER:")
            else:
                print("❌ UNVERIFIED ANSWER (max retries reached):")
            print(f"\n{result.answer}")

            # Show verification details
            print(f"\n🔬 Verification:")
            print(f"  Status: {result.final_verification.get('status', 'unknown')}")
            print(f"  Route: {result.final_verification.get('route', 'unknown')}")
            print(f"  Confidence: {result.final_verification.get('confidence', 0.0):.2f}")
            if result.final_verification.get('message'):
                print(f"  Message: {result.final_verification['message']}")

            print("="*70)

        except KeyboardInterrupt:
            print("\n\nGoodbye!")
            break
        except Exception as exc:
            print(f"\n❌ Error: {exc}")


if __name__ == "__main__":
    interactive_verified_qa()
