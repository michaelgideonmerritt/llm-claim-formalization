#!/usr/bin/env bash
#
# Interactive verified question-answering demo
#
# This demonstrates the core value proposition:
# - LLM provides vast knowledge (trained on billions of docs)
# - Verification layer ensures zero hallucinations
# - Result: Deterministic, verified answers
#

set -e

# Default to llama3.2:3b (fast and accurate)
MODEL="${LLM_CF_QA_MODEL:-llama3.2:3b}"

echo "🔍 Starting Verified Question-Answering Interface"
echo "Model: $MODEL"
echo ""
echo "This interface combines:"
echo "  1. LLM knowledge (vast training corpus)"
echo "  2. Formal verification (zero hallucinations)"
echo ""

# Activate virtual environment if it exists
if [ -d venv ]; then
  source venv/bin/activate
fi

# Run the interactive QA interface
python3 -m llm_claim_formalization.qa_interface
