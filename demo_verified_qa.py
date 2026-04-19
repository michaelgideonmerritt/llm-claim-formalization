#!/usr/bin/env python3
"""
Demo: Verified QA with Feedback Loop

Shows the complete architecture:
1. User asks question
2. Verifier classifies question type
3. LLM generates answer
4. Verifier checks answer
5. If rejected → feedback to LLM → retry
6. Loop until verified

This demonstrates the VALUE PROPOSITION:
- LLM has vast knowledge (trained on billions of docs)
- Verifier ensures zero hallucinations
- Feedback loop self-corrects errors
- Result: Deterministic, verified answers
"""

from src.llm_claim_formalization.verified_qa import (
    ask_verified_question,
    classify_question,
)


def demo_feedback_loop():
    """
    Demo the feedback loop with a simple math question.
    """
    question = "What is 2 + 2?"

    print("="*70)
    print("🔍 Verified Question-Answering Demo")
    print("="*70)
    print(f"\n📋 Question: {question}\n")

    # Step 1: Classify question
    print("⏳ Step 1: Verifier classifies question type...")
    classification = classify_question(question)
    print(f"✅ Question type: {classification['route']}")
    print(f"   Claim type: {classification['claim_type']}")
    print(f"   Needs verification: {classification['needs_verification']}")

    # Step 2-5: LLM + Verification feedback loop
    print(f"\n⏳ Step 2-5: LLM generation + verification feedback loop...")
    print("   (This may take a moment...)\n")

    result = ask_verified_question(question, model="llama3.2:3b", max_retries=3)

    if result.error:
        print(f"❌ Error: {result.error}")
        return

    print("="*70)
    print("📊 RESULTS")
    print("="*70)

    print(f"\n✅ Final answer: {result.answer}")
    print(f"\n🔍 Verified: {'✅ YES' if result.verified else '❌ NO'}")
    print(f"📈 Total attempts: {result.attempts}")

    # Show rejection history (if any)
    if result.rejection_history:
        print(f"\n🔄 Rejection & Retry History:")
        for i, rejection in enumerate(result.rejection_history, 1):
            print(f"\n  Attempt {rejection['attempt']}:")
            print(f"    LLM Answer: {rejection['answer'][:80]}...")
            print(f"    Verification: {rejection['status']}")
            print(f"    Rejection: {rejection['rejection_reason'][:100]}...")

    # Show final verification
    print(f"\n🔬 Final Verification:")
    print(f"   Status: {result.final_verification.get('status')}")
    print(f"   Route: {result.final_verification.get('route')}")
    print(f"   Confidence: {result.final_verification.get('confidence', 0.0):.2f}")
    if result.final_verification.get('message'):
        print(f"   Message: {result.final_verification['message']}")

    print("\n" + "="*70)
    print("✅ Demo complete!")
    print("="*70)


def show_architecture():
    """Show the system architecture"""
    print("\n" + "="*70)
    print("🏗️  SYSTEM ARCHITECTURE")
    print("="*70)
    print("""
The Verified QA System combines:

1. LLM Knowledge
   - Trained on billions of documents
   - Can answer virtually any question
   - BUT: May hallucinate or make logical errors

2. Formal Verification Layer
   - Z3 theorem prover for math/logic
   - Symbolic reasoning for structured claims
   - Pattern matching for factual claims
   - 100% deterministic, zero hallucinations

3. Feedback Loop (THE KEY INNOVATION)
   ┌─────────────────────────────────────────┐
   │ User Question                           │
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ Verifier: What type of question?        │
   │ (arithmetic, logic, factual, etc.)      │
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ LLM: Generate answer                    │
   │ (using vast training knowledge)         │
   └──────────────┬──────────────────────────┘
                  ↓
   ┌─────────────────────────────────────────┐
   │ Verifier: Is answer deterministic?      │
   │ - Check logic with Z3                   │
   │ - Verify claims                         │
   │ - Detect hallucinations                 │
   └──────────────┬──────────────────────────┘
                  ↓
         ┌────────┴────────┐
         │                 │
        YES               NO
         │                 │
         ↓                 ↓
   Send to User    Send rejection reason
                   back to LLM
                          ↓
                   LLM retries with
                   corrected answer
                          ↓
                   (loop until verified
                    or max retries)

Result: Deterministic, hallucination-free answers
        with the full knowledge of the LLM
""")
    print("="*70)


if __name__ == "__main__":
    show_architecture()
    print("\n\n")
    demo_feedback_loop()
