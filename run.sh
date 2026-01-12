#!/bin/bash

# Ensure we are in the project directory
cd "$(dirname "$0")"

# Check if .venv exists
if [ ! -d ".venv" ]; then
    echo "❌ Error: .venv directory not found!"
    echo "Please set up the environment first:"
    echo "  python3 -m venv .venv"
    echo "  source .venv/bin/activate"
    echo "  pip install -r requirements.txt"
    exit 1
fi

# Activate virtual environment
source .venv/bin/activate

# Check for dependencies
python3 -c "import pydantic" >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "📦 Dependencies missing. Installing..."
    pip install -r requirements.txt
    if [ $? -ne 0 ]; then
         echo "❌ Failed to install dependencies."
         exit 1
    fi
fi

# Use the cleaner python -m syntax which resolves path issues better
echo "🕹️  Starting Arcade Media Scanner..."
python3 -m arcade_scanner.main "$@"
