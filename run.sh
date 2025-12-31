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

# Use the cleaner python -m syntax which resolves path issues better
echo "🕹️  Starting Arcade Video Scanner..."
python3 -m arcade_scanner.main "$@"
