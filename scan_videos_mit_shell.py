#!/usr/bin/env python3
"""
Arcade Video Scanner 4.0 (Legacy Wrapper)
This script now serves as an entry point for the modular arcade_scanner package.
"""
import sys
import os

# Add the current directory to sys.path to ensure arcade_scanner is found
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.append(current_dir)

try:
    from arcade_scanner.main import run_scanner
except ImportError as e:
    # Fallback: maybe we are running from elsewhere, let's try to find it
    print(f"Error: Could not import arcade_scanner. {e}")
    sys.exit(1)

if __name__ == "__main__":
    run_scanner(sys.argv[1:])
