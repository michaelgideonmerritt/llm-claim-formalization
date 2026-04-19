#!/usr/bin/env python3
"""Test claim extraction from LLM answers"""

import re

def extract_claim_from_answer(answer: str) -> str:
    """Extract verifiable claim from LLM answer"""
    claim = answer

    # Try to extract equation-like patterns
    # "2 + 2 is 4" → "2 + 2 = 4"
    claim = re.sub(r'\bis\b', '=', claim, flags=re.IGNORECASE)
    claim = re.sub(r'\bequals\b', '=', claim, flags=re.IGNORECASE)

    # Remove common sentence starters
    claim = re.sub(r'^(The answer (to|is)|The result is|It is)\s+', '', claim, flags=re.IGNORECASE)
    claim = claim.strip(' .')

    return claim

test_answers = [
    "The answer to 2 + 2 is 4.",
    "2 + 2 equals 4",
    "The result is 10",
    "It is 50",
    "100 - 50 is 50",
    "If I have $100 and spend 50%, I have $50 left.",
]

print("Testing claim extraction:\n")
for answer in test_answers:
    extracted = extract_claim_from_answer(answer)
    print(f"Original:  {answer}")
    print(f"Extracted: {extracted}")
    print()
