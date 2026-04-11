#!/bin/bash

if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Please run ./install.sh first."
    exit 1
fi

echo "📝 Running quickstart example..."
echo ""

source venv/bin/activate
python examples/quickstart.py
