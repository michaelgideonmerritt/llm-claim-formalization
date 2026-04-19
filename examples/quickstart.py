from llm_claim_formalization import verify_claim

examples = [
    "$100 with 50% off then 20% off is $40",
    "$100 with 50% off then 20% off is $60",
    "120 miles at 25 miles per gallon is less than 4 gallons",
    "A price increases by 100%",
    "Smoking increases risk of heart disease",
]

for text in examples:
    print(f"\nInput: {text}")
    result = verify_claim(text)
    print(f"Status: {result.status}")
    print(f"Route: {result.route}")
    if result.equation:
        print(f"Equation: {result.equation}")
    if result.message:
        print(f"Message: {result.message}")
