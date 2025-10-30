"""Configuration management for Telegram Backup."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API credentials
# HIGH PRIORITY FIX: Removed hardcoded default values for security
# Users MUST provide these via .env file
API_ID_STR = os.getenv('TELEGRAM_API_ID')
API_HASH = os.getenv('TELEGRAM_API_HASH')

if not API_ID_STR or not API_HASH:
    raise ValueError(
        "TELEGRAM_API_ID and TELEGRAM_API_HASH must be set in .env file.\n"
        "Get your credentials from https://my.telegram.org/apps"
    )

try:
    API_ID = int(API_ID_STR)
except ValueError:
    raise ValueError("TELEGRAM_API_ID must be a valid integer")

# Download settings
MAX_CONCURRENT_DOWNLOADS = 5
DOWNLOAD_BATCH_SIZE = 5

# Backup directories
BACKUP_DIR = "backups"
MEDIA_BASE_DIR = "media"

# HTML generation settings
HTML_CHUNK_SIZE = 200  # Number of messages per JSON chunk
HTML_INITIAL_LOAD = 400  # Number of messages to load initially

