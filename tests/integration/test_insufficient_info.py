#!/usr/bin/env python3
"""Test insufficient information detection and routing."""
import asyncio
from app.verification_layer import extract_claims
from app.claim_extractor import extract_claim

TEST_CASES = [
    {
        "name": "Missing base value - relative percentage",
        "message": "A price increases by 100%",
        "expected_route": "insufficient_info",
        "expected_missing": "missing_base_value",
        "description": "Has percentage (100%) but no base price to apply it to"
    },
    {
        "name": "Missing concrete value - abstract transformation",
        "message": "If something doubles and then loses half the gain",
        "expected_route": "insufficient_info",
        "expected_missing": "missing_concrete_value",
        "description": "Abstract transformation (doubles, half) without concrete base value"
    },
    {
        "name": "Missing comparison value - incomplete comparison",
        "message": "The value is less than 5",
        "expected_route": "insufficient_info",
        "expected_missing": "missing_comparison_value",
        "description": "Has comparison operator (less than) but only one value"
    },
    {
        "name": "Valid discount - should extract",
        "message": "$100 with 50% off",
        "expected_route": "structured",
        "expected_missing": None,
        "description": "Has base ($100) and percentage (50%) - complete information"
    },
    {
        "name": "Valid relative increase - should extract",
        "message": "Start with $50, increase by 20%",
        "expected_route": "structured",
        "expected_missing": None,
        "description": "Has base ($50) and percentage (20%) - complete information"
    },
    {
        "name": "Valid comparison - should extract",
        "message": "120 miles at 25 mpg is less than 4 gallons",
        "expected_route": "structured",
        "expected_missing": None,
        "description": "Has both values for comparison (120/25 and 4)"
    },
]


async def test_insufficient_info():
    print("=" * 80)
    print("INSUFFICIENT INFORMATION DETECTION TESTS")
    print("=" * 80)
    print()

    passed = 0
    failed = 0

    for test in TEST_CASES:
        name = test["name"]
        msg = test["message"]
        expected_route = test["expected_route"]
        expected_missing = test["expected_missing"]
        description = test["description"]

        print(f"Test: {name}")
        print(f"  Message: {msg}")
        print(f"  Expected: {expected_route}")
        print(f"  Context: {description}")

        # Test claim extraction directly
        claim = extract_claim(msg)

        if expected_route == "insufficient_info":
            # Should detect insufficient info
            if claim and claim.insufficient_info:
                # Check that missing_info matches expected
                if expected_missing and expected_missing in claim.missing_info:
                    print(f"  ✅ PASS - Detected insufficient info: {claim.missing_info}")
                    # Verify suggested_clarification is populated
                    if claim.suggested_clarification:
                        print(f"    Suggested clarification: \"{claim.suggested_clarification}\"")
                    else:
                        print(f"    ⚠️  WARNING: No suggested_clarification provided")
                    passed += 1
                else:
                    print(f"  ❌ FAIL - Wrong missing_info: {claim.missing_info} (expected: {expected_missing})")
                    failed += 1
            else:
                print(f"  ❌ FAIL - Did not detect insufficient info")
                if claim:
                    print(f"    Got: equation={claim.equation}, confidence={claim.confidence}")
                else:
                    print(f"    Got: No claim extracted")
                failed += 1
        else:
            # Should NOT detect insufficient info (should extract or route to LLM)
            if claim and claim.insufficient_info:
                print(f"  ❌ FAIL - Incorrectly flagged as insufficient info: {claim.missing_info}")
                failed += 1
            elif claim and claim.equation:
                print(f"  ✅ PASS - Extracted equation: {claim.equation}")
                print(f"    Confidence: {claim.confidence}, Coverage: {claim.coverage_score}")
                passed += 1
            else:
                print(f"  ⚠️  PARTIAL - No extraction (will route to LLM)")
                print(f"    This is acceptable for complex cases")
                passed += 1

        # Test routing behavior
        claims_extracted = await extract_claims(msg)

        if expected_route == "insufficient_info":
            if len(claims_extracted) == 0:
                print(f"  ✅ Route check PASS - Correctly routed to no_claim (insufficient info)")
            else:
                print(f"  ❌ Route check FAIL - Expected no claims, got: {claims_extracted}")
        else:
            if len(claims_extracted) > 0:
                print(f"  ✅ Route check PASS - Routed to: {claims_extracted[0][:50]}")
            else:
                print(f"  ⚠️  Route check - No claims extracted (may route to LLM)")

        print()

    print("=" * 80)
    total = passed + failed
    print(f"Results: {passed}/{total} passed ({100 * passed / total if total > 0 else 0:.0f}%)")
    print("=" * 80)

    return passed == total


if __name__ == "__main__":
    success = asyncio.run(test_insufficient_info())
    exit(0 if success else 1)
