#!/bin/bash

set -euo pipefail

echo "🔧 LLM Claim Formalization - Installation Script"
echo ""

PYTHON_CMD=""
if command -v python3 &> /dev/null; then
    PYTHON_CMD="python3"
elif command -v python &> /dev/null; then
    PYTHON_CMD="python"
else
    echo "❌ Error: Python 3.10+ is required but not found."
    echo "   Please install Python from https://python.org"
    exit 1
fi

echo "✓ Found Python: $PYTHON_CMD"
PYTHON_VERSION=$($PYTHON_CMD --version 2>&1 | awk '{print $2}')
echo "  Version: $PYTHON_VERSION"
echo ""

if [ -d "venv" ]; then
    echo "⚠️  Virtual environment already exists. Removing..."
    rm -rf venv
fi

echo "📦 Creating virtual environment..."
$PYTHON_CMD -m venv venv

echo "🔌 Activating virtual environment..."
source venv/bin/activate

echo "⬇️  Installing Python dependencies..."
pip install --upgrade pip -q
pip install -e ".[demo,dev]"

MODEL="${LLM_CF_OLLAMA_MODEL:-lfm2.5-thinking-128k:latest}"

echo ""
echo "🤖 Verifying Ollama and model setup ($MODEL)..."
./scripts/setup-ollama.sh --install --model "$MODEL"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Run the demo: ./run-demo.sh"
echo "  2. Or run quickstart: ./run-example.sh"
echo "  3. Change model anytime: LLM_CF_OLLAMA_MODEL=llama3.2:3b ./run-demo.sh"
echo ""
