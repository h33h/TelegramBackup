"""Utility functions for Telegram Backup."""

import re
import hashlib
import os
import asyncio
from concurrent.futures import ThreadPoolExecutor

# MEDIUM PRIORITY FIX: Thread pool for async file hashing
_hash_thread_pool = ThreadPoolExecutor(max_workers=3, thread_name_prefix="hash_worker")


def get_url_from_forwarded(forwarded):
    """Extract URL from forwarded message information."""
    if forwarded is None:
        return None
    match = re.search(r"channel_id=(\d+).*channel_post=(\d+)", forwarded)
    if match:
        channel_id, channel_post = match.groups()
        return f"https://t.me/c/{channel_id}/{channel_post}"
    return None


def sanitize_filename(filename):
    """Remove invalid characters from filename."""
    return re.sub(r'[^\w\-_\. ]', '_', filename)


def get_backup_dir(entity_id, entity_name):
    """Get the backup directory path for a specific entity.
    
    Args:
        entity_id: Entity ID
        entity_name: Entity name
        
    Returns:
        Path to the entity's backup directory
    """
    from telegram_backup.config import BACKUP_DIR
    import os
    
    sanitized_name = sanitize_filename(f"{entity_id}_{entity_name}")
    return os.path.join(BACKUP_DIR, sanitized_name)


def get_file_hash(file_path, algorithm='sha256'):
    """Calculate hash of a file (synchronous version).
    
    LOW PRIORITY FIX: Changed default from MD5 to SHA-256 for better security.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('md5' or 'sha256', default: 'sha256')
    
    Returns:
        str: Hash hex digest or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
    
    if algorithm == 'md5':
        hasher = hashlib.md5()
    elif algorithm == 'sha256':
        hasher = hashlib.sha256()
    else:
        raise ValueError(f"Unsupported hash algorithm: {algorithm}")
    
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()


async def get_file_hash_async(file_path, algorithm='sha256'):
    """Calculate hash of a file asynchronously.
    
    MEDIUM PRIORITY FIX: Non-blocking file hashing using thread pool.
    LOW PRIORITY FIX: SHA-256 by default instead of MD5.
    
    Args:
        file_path: Path to the file
        algorithm: Hash algorithm ('md5' or 'sha256', default: 'sha256')
        
    Returns:
        str: Hash hex digest or None if file doesn't exist
    """
    if not os.path.exists(file_path):
        return None
    
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(_hash_thread_pool, get_file_hash, file_path, algorithm)


def extract_user_id(from_id_str):
    """Extract user ID from from_id string."""
    if not from_id_str:
        return None
    
    match = re.search(r"user_id=(\d+)", from_id_str)
    if match:
        return match.group(1)
    
    match = re.search(r"channel_id=(\d+)", from_id_str)
    if match:
        return match.group(1)
    
    match = re.search(r"chat_id=(\d+)", from_id_str)
    if match:
        return match.group(1)
    
    if from_id_str.isdigit():
        return from_id_str
    
    return None


def extract_file_identifiers(media):
    """Extract Telegram file identifiers from media objects.
    
    Returns tuple: (file_id, access_hash, file_size)
    Note: file_id is the unique identifier, access_hash is for API access
    """
    if not media:
        return None, None, None
    
    try:
        # Handle MessageMediaPhoto
        if hasattr(media, 'photo') and media.photo:
            photo = media.photo
            if hasattr(photo, 'id'):
                file_id = str(photo.id)
                access_hash = str(getattr(photo, 'access_hash', ''))
                # Get largest photo size
                file_size = 0
                if hasattr(photo, 'sizes') and photo.sizes:
                    for size in photo.sizes:
                        if hasattr(size, 'size'):
                            file_size = max(file_size, size.size)
                return file_id, access_hash, file_size
        
        # Handle MessageMediaDocument (videos, files, audio, etc.)
        if hasattr(media, 'document') and media.document:
            doc = media.document
            if hasattr(doc, 'id'):
                file_id = str(doc.id)
                access_hash = str(getattr(doc, 'access_hash', ''))
                file_size = getattr(doc, 'size', 0)
                return file_id, access_hash, file_size
        
        # Handle direct document/photo objects
        if hasattr(media, 'id'):
            file_id = str(media.id)
            access_hash = str(getattr(media, 'access_hash', ''))
            file_size = getattr(media, 'size', 0)
            return file_id, access_hash, file_size
            
    except Exception as e:
        print(f"Error extracting file identifiers: {e}")
    
    return None, None, None


def get_emoji_string(reaction):
    """Convert reaction object to emoji string."""
    try:
        if hasattr(reaction, 'emoticon'):
            return reaction.emoticon
        elif hasattr(reaction, 'document_id'):
            return f"CustomEmoji:{reaction.document_id}"
        elif hasattr(reaction, 'emoji'):
            return reaction.emoji
        elif hasattr(reaction, 'reaction'):
            if isinstance(reaction.reaction, str):
                return reaction.reaction
            return get_emoji_string(reaction.reaction)
        elif isinstance(reaction, str):
            return reaction
        else:
            return str(reaction)
    except Exception as e:
        print(f"Error processing reaction: {e}")
        return "Unknown"

