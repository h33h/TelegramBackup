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
MAX_CONCURRENT_DOWNLOADS = int(os.getenv('MAX_CONCURRENT_DOWNLOADS', '5'))
DOWNLOAD_BATCH_SIZE = int(os.getenv('DOWNLOAD_BATCH_SIZE', '5'))
DOWNLOAD_BATCH_SIZE_BYTES = int(os.getenv('DOWNLOAD_BATCH_SIZE_BYTES', str(100 * 1024 * 1024)))  # 100MB default
MAX_RETRIES = int(os.getenv('MAX_DOWNLOAD_RETRIES', '3'))
RETRY_DELAY = float(os.getenv('RETRY_DELAY', '2.0'))  # Initial retry delay in seconds
MAX_FILE_SIZE = int(os.getenv('MAX_FILE_SIZE', str(2 * 1024 * 1024 * 1024)))  # 2GB default limit

# Backup directories
BACKUP_DIR = "backups"
MEDIA_BASE_DIR = "media"

# HTML generation settings
HTML_CHUNK_SIZE = 200  # Number of messages per JSON chunk
HTML_INITIAL_LOAD = 400  # Number of messages to load initially

