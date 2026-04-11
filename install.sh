#!/bin/bash

set -e

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

echo "⬇️  Installing dependencies..."
pip install --upgrade pip -q
pip install -e ".[demo]"

echo ""
echo "✅ Installation complete!"
echo ""
echo "Next steps:"
echo "  1. Make sure Ollama is installed: https://ollama.ai"
echo "  2. Pull the LFM 2.5 model: ollama pull lfm2.5-thinking-128k"
echo "  3. Run the demo: ./run-demo.sh"
echo "  4. Or try the example: ./run-example.sh"
echo ""
