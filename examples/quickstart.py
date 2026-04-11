from llm_claim_formalization import extract_claim

examples = [
    "$100 with 50% off is $50",
    "$100 with 50% off then 20% off",
    "120 miles at 25 mpg is less than 4 gallons",
    "A price increases by 100%",
]

for text in examples:
    print(f"\nInput: {text}")
    claim = extract_claim(text)

    if claim:
        if claim.insufficient_info:
            print(f"Status: Insufficient Info")
            print(f"Missing: {claim.missing_info}")
            print(f"Clarification: {claim.suggested_clarification}")
        else:
            print(f"Status: Extracted")
            print(f"Equation: {claim.equation}")
            print(f"Confidence: {claim.confidence:.2f}")
    else:
        print("Status: No claim detected")
