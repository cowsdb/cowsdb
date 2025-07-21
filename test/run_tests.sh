#!/bin/bash
set -e

echo "🧪 CowsDB CI Test Suite"
echo "========================"

# Check if virtual environment exists
if [ ! -d "venv" ]; then
    echo "📦 Creating virtual environment..."
    python3 -m venv venv
fi

# Activate virtual environment
echo "🔧 Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo "📥 Installing dependencies..."
pip install -r requirements.txt

# Run tests
echo "🚀 Running test suite..."
python test/test_suite.py

echo "✅ All tests completed!" 