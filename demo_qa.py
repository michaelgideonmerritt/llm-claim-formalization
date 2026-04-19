#!/usr/bin/env python3
"""
Quick demo of verified QA interface.

Shows how the system combines:
1. LLM's vast knowledge (from training)
2. Formal verification (zero hallucinations)
"""

import sys
from src.llm_claim_formalization.qa_interface import ask_question, generate_answer, extract_claims_from_answer

def demo():
    """Run a single example"""
    question = "What is 2 + 2?"

    print("🔍 Verified Question-Answering Demo")
    print("="*70)
    print(f"\n📋 Question: {question}\n")

    # Step 1: Generate answer from LLM
    print("⏳ Step 1: Generating answer from LLM...")
    try:
        answer = generate_answer(question, model="llama3.2:3b")
        print(f"✅ LLM Answer: {answer}\n")
    except Exception as e:
        print(f"❌ Failed to generate answer: {e}")
        sys.exit(1)

    # Step 2: Extract claims
    print("⏳ Step 2: Extracting verifiable claims...")
    claims = extract_claims_from_answer(answer)
    print(f"✅ Found {len(claims)} claims:")
    for i, claim in enumerate(claims, 1):
        print(f"   {i}. {claim}")
    print()

    # Step 3: Verify
    print("⏳ Step 3: Running formal verification on claims...")
    result = ask_question(question, model="llama3.2:3b")

    if result.error:
        print(f"❌ Error: {result.error}")
        sys.exit(1)

    print(f"\n{'='*70}")
    print("📊 RESULTS")
    print('='*70)

    print(f"\n✅ Answer: {result.answer}")
    print(f"\n🔍 Verification Status: {'✅ VERIFIED' if result.verified else '❌ FAILED'}")
    print(f"\n📈 Statistics:")
    print(f"   Claims extracted: {result.claims_extracted}")
    print(f"   Claims verified: {result.claims_verified}")
    print(f"   Claims refuted: {result.claims_refuted}")
    print(f"   Claims uncertain: {result.claims_uncertain}")

    if result.verification_details:
        print(f"\n🔬 Verification Details:")
        for i, detail in enumerate(result.verification_details, 1):
            status = detail['status']
            emoji = "✅" if status == "verified" else "❌" if status == "refuted" else "⚠️"
            print(f"\n   Claim {i}: {detail['claim']}")
            print(f"   {emoji} Status: {status}")
            print(f"   Route: {detail['route']}")
            print(f"   Confidence: {detail['confidence']:.2f}")
            if detail.get('message'):
                print(f"   Message: {detail['message']}")

    print(f"\n{'='*70}")
    print("✅ Demo complete!")
    print('='*70)

if __name__ == "__main__":
    demo()
