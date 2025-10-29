"""Main entry point for Telegram Backup."""

import asyncio
import warnings
from bs4 import MarkupResemblesLocatorWarning

from telegram_backup.cli import run_cli

# Suppress BeautifulSoup warnings
warnings.filterwarnings("ignore", category=MarkupResemblesLocatorWarning)


def main():
    """Main entry point."""
    asyncio.run(run_cli())


if __name__ == "__main__":
    main()

