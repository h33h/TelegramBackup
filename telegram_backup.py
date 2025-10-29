"""Telegram Backup - Backward compatibility wrapper.

This file has been refactored into a modular package structure.
The code now lives in the telegram_backup/ package.

To run the tool, you can:
1. Use this script: python telegram_backup.py
2. Use the new main.py: python main.py
3. Run as a module: python -m telegram_backup

For configuration, create a .env file based on .env.example
"""

import sys
import warnings

# Show deprecation notice
print("=" * 70)
print("NOTE: This script has been refactored into a modular package.")
print("The code is now organized in the telegram_backup/ package.")
print("You can also run: python main.py or python -m telegram_backup")
print("=" * 70)
print()

# Import and run the new modular version
from telegram_backup.__main__ import main

if __name__ == "__main__":
    main()
