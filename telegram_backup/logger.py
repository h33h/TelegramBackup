"""Logging configuration for Telegram Backup.

MEDIUM PRIORITY FIX: Proper logging framework instead of print() statements.
"""

import logging
import sys
from pathlib import Path


def setup_logging(log_level=logging.INFO, log_file=None):
    """Setup logging configuration.
    
    Args:
        log_level: Logging level (default: INFO)
        log_file: Optional log file path
    """
    # Create formatter
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    
    # Setup root logger
    root_logger = logging.getLogger('telegram_backup')
    root_logger.setLevel(log_level)
    
    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(log_level)
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File handler (optional)
    if log_file:
        log_path = Path(log_file)
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)  # Always log DEBUG to file
        file_handler.setFormatter(formatter)
        root_logger.addHandler(file_handler)
    
    return root_logger


def get_logger(name):
    """Get a logger for a specific module.
    
    Args:
        name: Logger name (usually __name__)
        
    Returns:
        logging.Logger instance
    """
    return logging.getLogger(f'telegram_backup.{name}')


# Default logger for quick access
logger = get_logger('main')

