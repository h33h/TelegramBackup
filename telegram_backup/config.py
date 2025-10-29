"""Configuration management for Telegram Backup."""

import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Telegram API credentials
API_ID = int(os.getenv('TELEGRAM_API_ID', '25266913'))
API_HASH = os.getenv('TELEGRAM_API_HASH', 'ecb219964d870430249c46d20b01ea2d')

# Download settings
MAX_CONCURRENT_DOWNLOADS = 5
DOWNLOAD_BATCH_SIZE = 5

# Backup directories
BACKUP_DIR = "backups"
MEDIA_BASE_DIR = "media"

# HTML generation settings
HTML_CHUNK_SIZE = 200  # Number of messages per JSON chunk
HTML_INITIAL_LOAD = 400  # Number of messages to load initially

