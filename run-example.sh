#!/bin/bash

set -euo pipefail

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

MODEL="${LLM_CF_OLLAMA_MODEL:-lfm2.5-thinking-128k:latest}"

echo "🤖 Ensuring Ollama is ready (model: $MODEL)..."
./scripts/setup-ollama.sh --model "$MODEL"

echo ""
echo "📝 Running quickstart example..."
echo ""

source venv/bin/activate
python examples/quickstart.py
