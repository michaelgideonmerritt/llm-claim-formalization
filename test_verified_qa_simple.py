#!/usr/bin/env python3
"""
Simple test to debug verified QA
"""

from src.llm_claim_formalization.verified_qa import (
    classify_question,
    generate_llm_answer,
    verify_llm_answer,
)

question = "What is 2 + 2?"

print("Step 1: Classify question")
classification = classify_question(question)
print(f"Route: {classification['route']}")
print(f"Claim type: {classification['claim_type']}\n")

print("Step 2: Generate LLM answer")
try:
    answer = generate_llm_answer(question, model="llama3.2:3b")
    print(f"LLM answer: {answer}\n")
except Exception as e:
    print(f"ERROR generating answer: {e}\n")
    exit(1)

print("Step 3: Verify answer")
verification = verify_llm_answer(answer, classification['route'])
print(f"Verified: {verification['verified']}")
print(f"Status: {verification['status']}")
print(f"Confidence: {verification['confidence']}")
print(f"Message: {verification['message']}")
if not verification['verified']:
    print(f"\nRejection reason:\n{verification['rejection_reason']}")

print(f"\nFull result:")
import json
print(json.dumps(verification['full_result'], indent=2))
