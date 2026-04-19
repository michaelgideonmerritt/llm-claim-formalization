#!/usr/bin/env bash
#
# Verified Question-Answering with Feedback Loop
#
# This is THE vision:
# 1. User asks question
# 2. Verifier: What type of question?
# 3. LLM: Generate answer
# 4. Verifier: Is this deterministic and logical?
#    - YES → Send to user
#    - NO → Send back to LLM with rejection reason
# 5. LLM: Fix and retry
# 6. Loop until verified
#

set -e

MODEL="${LLM_CF_QA_MODEL:-llama3.2:3b}"
MAX_RETRIES="${LLM_CF_MAX_RETRIES:-3}"

echo "🔍 Verified Question-Answering with Feedback Loop"
echo ""
echo "Configuration:"
echo "  Model: $MODEL"
echo "  Max retries: $MAX_RETRIES"
echo ""

# Activate venv if exists
if [ -d venv ]; then
  source venv/bin/activate
fi

# Run interactive QA
python3 -m llm_claim_formalization.verified_qa
