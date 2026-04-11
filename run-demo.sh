#!/bin/bash

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

echo "🚀 Starting LLM Claim Formalization Demo..."
echo ""
echo "Demo will open at: http://localhost:8000"
echo "Press Ctrl+C to stop"
echo ""

source venv/bin/activate
python -m llm_claim_formalization.demo
