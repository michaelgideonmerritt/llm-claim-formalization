#!/usr/bin/env python3
"""
Test the verified QA interface with example questions.

This demonstrates:
1. LLM generates answer from training knowledge
2. Verification layer checks for hallucinations
3. System returns verified answer or rejects if refuted
"""

from src.llm_claim_formalization.qa_interface import ask_question


def test_qa_examples():
    """Test with various question types"""

    test_questions = [
        # Factual question (should verify)
        "What is the capital of France?",

        # Math question (should verify with Z3)
        "What is 2 + 2?",

        # Scientific fact (should verify if LLM answers correctly)
        "At what temperature does water boil at sea level?",
    ]

    print("🔍 Testing Verified Question-Answering Interface\n")

    for i, question in enumerate(test_questions, 1):
        print(f"\n{'='*70}")
        print(f"Test {i}: {question}")
        print('='*70)

        result = ask_question(question, model="llama3.2:3b")

        if result.error:
            print(f"\n❌ Error: {result.error}")
            continue

        print(f"\n📝 LLM Answer:\n{result.answer}\n")

        if result.verified:
            print("✅ Verification: VERIFIED")
        else:
            print("❌ Verification: FAILED (hallucinations detected)")

        print(f"\nStatistics:")
        print(f"  Claims extracted: {result.claims_extracted}")
        print(f"  Claims verified: {result.claims_verified}")
        print(f"  Claims refuted: {result.claims_refuted}")
        print(f"  Claims uncertain: {result.claims_uncertain}")

        if result.verification_details:
            print(f"\nVerification Details:")
            for j, detail in enumerate(result.verification_details, 1):
                status = detail['status']
                emoji = "✅" if status == "verified" else "❌" if status == "refuted" else "⚠️"
                print(f"  {j}. {emoji} [{status}] {detail['claim']}")
                print(f"     Route: {detail['route']}, Confidence: {detail['confidence']:.2f}")
                if detail.get('message'):
                    print(f"     Message: {detail['message']}")

    print(f"\n{'='*70}")
    print("✅ Testing complete!")
    print('='*70)


if __name__ == "__main__":
    test_qa_examples()
