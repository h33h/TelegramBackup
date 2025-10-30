"""Media downloading with parallel processing."""

import asyncio
import os
import mimetypes
import shutil
import logging
import time
from functools import lru_cache
from telethon import errors
from telegram_backup.utils import get_file_hash, get_file_hash_async  # MEDIUM PRIORITY FIX
from telegram_backup.file_validator import validate_file_after_download  # HIGH PRIORITY FIX
from telegram_backup.config import MAX_RETRIES, RETRY_DELAY, MAX_FILE_SIZE
from telegram_backup.download_stats import DownloadStats

# Logger for error tracking
logger = logging.getLogger('telegram_backup.media')


def check_disk_space_for_file(media_dir, required_bytes):
    """Check if there's enough disk space for a file download.
    
    Args:
        media_dir: Directory where file will be downloaded
        required_bytes: Required space in bytes
    
    Returns:
        tuple: (has_space: bool, available_bytes: int)
    """
    try:
        stat = shutil.disk_usage(media_dir)
        available = stat.free
        # Keep 100MB safety margin per file
        safety_margin = 100 * 1024 * 1024
        has_space = available > (required_bytes + safety_margin)
        return has_space, available
    except Exception as e:
        logger.warning(f"Cannot check disk space: {e}")
        return True, 0


def is_retryable_error(exception):
    """Determine if an error is retryable.
    
    Args:
        exception: The exception that occurred
    
    Returns:
        bool: True if error is retryable
    """
    # Network errors and temporary Telegram API errors are retryable
    retryable_types = (
        errors.FloodWaitError,
        errors.SlowModeWaitError,
        errors.TimeoutError,
        ConnectionError,
        asyncio.TimeoutError,
        OSError,  # Network-related OS errors
    )
    
    return isinstance(exception, retryable_types)


def get_mime_type(media):
    """Extract MIME type from media object."""
    try:
        # For documents
        if hasattr(media, 'document') and media.document:
            doc = media.document
            if hasattr(doc, 'mime_type'):
                return doc.mime_type
        
        # For photos
        if hasattr(media, 'photo') and media.photo:
            return 'image/jpeg'
        
        # Direct access
        if hasattr(media, 'mime_type'):
            return media.mime_type
    except:
        pass
    
    return None


@lru_cache(maxsize=100)
def _get_extension_from_mime(mime_type):
    """Cached MIME type to extension conversion."""
    if not mime_type:
        return None
    ext = mimetypes.guess_extension(mime_type)
    if ext:
        # Fix common issues
        if ext == '.jpe':
            return '.jpg'
        return ext.lower()
    return None


def get_file_extension(media, media_type=None):
    """Extract file extension from media object with caching.
    
    Args:
        media: Telegram media object
        media_type: Media type string (e.g., 'MessageMediaPhoto')
    
    Returns:
        File extension with dot (e.g., '.jpg', '.mp4')
    """
    try:
        # For photos - always jpg
        if media_type == 'MessageMediaPhoto' or (hasattr(media, 'photo') and media.photo):
            return '.jpg'
        
        # For documents - try to get from attributes first
        if hasattr(media, 'document') and media.document:
            doc = media.document
            
            # Check DocumentAttributeFilename
            if hasattr(doc, 'attributes') and doc.attributes:
                for attr in doc.attributes:
                    if hasattr(attr, '_') and attr._ == 'DocumentAttributeFilename':
                        if hasattr(attr, 'file_name'):
                            _, ext = os.path.splitext(attr.file_name)
                            if ext:
                                return ext.lower()
            
            # Fallback to mime_type (cached)
            if hasattr(doc, 'mime_type'):
                ext = _get_extension_from_mime(doc.mime_type)
                if ext:
                    return ext
        
        # Try direct mime_type access (cached)
        mime_type = get_mime_type(media)
        if mime_type:
            ext = _get_extension_from_mime(mime_type)
            if ext:
                return ext
        
    except Exception as e:
        print(f"Error extracting file extension: {e}")
    
    # Default fallback
    return '.bin'


def generate_media_filename(file_id, media, media_type=None, media_dir=''):
    """Generate deterministic filename based on file_id.
    
    Args:
        file_id: Telegram file ID (unique identifier)
        media: Telegram media object
        media_type: Media type string
        media_dir: Directory to save the file
    
    Returns:
        Full path to the file
    """
    if not file_id:
        return None
    
    extension = get_file_extension(media, media_type)
    filename = f"{file_id}{extension}"
    
    if media_dir:
        return os.path.join(media_dir, filename)
    
    return filename


async def download_media_batch(client, messages_batch, media_dir, semaphore, progress=None, stats=None):
    """Download media files in parallel with concurrency control.
    
    Improved version with:
    - Retry logic with exponential backoff
    - Disk space validation before download
    - File size limits
    - Better error handling and logging
    - Download statistics tracking
    
    Args:
        client: Telegram client
        messages_batch: List of tuples (message, message_id)
        media_dir: Directory path to save media files
        semaphore: asyncio.Semaphore for concurrency control
        progress: DownloadProgress instance for tracking (optional)
        stats: DownloadStats instance for statistics (optional)
        
    Returns:
        dict: {message_id: (media_file, media_hash, mime_type)}
    """
    results = {}
    
    # Create stats if not provided
    if stats is None:
        stats = DownloadStats()
    
    async def download_single_with_retry(message, msg_id):
        """Download a single file with retry logic."""
        retry_count = 0
        last_error = None
        required_retry = False
        
        while retry_count <= MAX_RETRIES:
            try:
                result = await download_single(message, msg_id)
                
                # Track retry statistics
                if required_retry:
                    stats.record_file_with_retry()
                
                return result
            except Exception as e:
                last_error = e
                error_type = type(e).__name__
                
                # Check if error is retryable
                if not is_retryable_error(e) or retry_count >= MAX_RETRIES:
                    # Non-retryable error or max retries reached
                    logger.error(f"Failed to download file {msg_id} after {retry_count} retries: {e}")
                    stats.record_failure(str(msg_id), error_type)
                    if progress:
                        progress.complete_file_download(msg_id)
                    results[msg_id] = (None, None, None)
                    return
                
                # Calculate exponential backoff delay
                retry_count += 1
                required_retry = True
                stats.record_retry()
                delay = RETRY_DELAY * (2 ** (retry_count - 1))
                
                # Handle FloodWaitError specially
                if isinstance(e, errors.FloodWaitError):
                    delay = e.seconds
                    logger.warning(f"FloodWaitError for file {msg_id}, waiting {delay}s")
                elif isinstance(e, errors.SlowModeWaitError):
                    delay = e.seconds
                    logger.warning(f"SlowModeWaitError for file {msg_id}, waiting {delay}s")
                else:
                    logger.warning(f"Retry {retry_count}/{MAX_RETRIES} for file {msg_id} after {delay}s: {e}")
                
                await asyncio.sleep(delay)
        
        # All retries failed
        logger.error(f"Download failed for file {msg_id} after all retries: {last_error}")
        error_type = type(last_error).__name__ if last_error else "Unknown"
        stats.record_failure(str(msg_id), error_type)
        if progress:
            progress.complete_file_download(msg_id)
        results[msg_id] = (None, None, None)
    
    async def download_single(message, msg_id):
        """Download a single file (internal function)."""
        download_start_time = time.time()
        media_file = None
        
        try:
            async with semaphore:
                os.makedirs(media_dir, exist_ok=True)
                
                # Get file info
                file_size = 0
                filename = f"message_{msg_id}"
                
                if hasattr(message, 'file') and message.file:
                    filename = message.file.name or filename
                    file_size = message.file.size or 0
                elif hasattr(message, 'media'):
                    # Try to get size from media
                    if hasattr(message.media, 'document'):
                        file_size = getattr(message.media.document, 'size', 0)
                        # Try to get filename from attributes
                        if hasattr(message.media.document, 'attributes'):
                            for attr in message.media.document.attributes:
                                if hasattr(attr, '_') and attr._ == 'DocumentAttributeFilename':
                                    if hasattr(attr, 'file_name'):
                                        filename = attr.file_name
                    elif hasattr(message.media, 'photo'):
                        # For photos, get size from largest photo size
                        if hasattr(message.media.photo, 'sizes'):
                            for size in message.media.photo.sizes:
                                if hasattr(size, 'size'):
                                    file_size = max(file_size, size.size)
                        filename = f"photo_{msg_id}.jpg"
                
                # Check file size limit
                if file_size > MAX_FILE_SIZE:
                    logger.warning(f"File {filename} ({file_size / (1024**3):.2f} GB) exceeds max size limit ({MAX_FILE_SIZE / (1024**3):.2f} GB), skipping")
                    if progress:
                        progress.complete_file_download(msg_id)
                    results[msg_id] = (None, None, None)
                    return
                
                # Check disk space before download
                if file_size > 0:
                    has_space, available = check_disk_space_for_file(media_dir, file_size)
                    if not has_space:
                        logger.error(f"Insufficient disk space for {filename} ({file_size / (1024**2):.2f} MB required, {available / (1024**2):.2f} MB available)")
                        if progress:
                            progress.complete_file_download(msg_id)
                        results[msg_id] = (None, None, None)
                        return
                
                # Start tracking download in progress
                if progress:
                    progress.start_file_download(msg_id, filename, file_size)
                
                # Define progress callback
                def progress_callback(current, total):
                    """Callback for download progress updates."""
                    if progress:
                        progress.update_file_progress(msg_id, current)
                
                # Download with progress tracking
                media_file = await message.download_media(
                    file=f"{media_dir}/",
                    progress_callback=progress_callback if progress else None
                )
                
                if media_file:
                    # HIGH PRIORITY FIX: Validate downloaded file
                    if not validate_file_after_download(media_file, file_size):
                        # File validation failed - try to delete corrupted file
                        logger.warning(f"File validation failed for {media_file}")
                        try:
                            if os.path.exists(media_file):
                                os.remove(media_file)
                        except Exception as e:
                            logger.error(f"Failed to delete corrupted file {media_file}: {e}")
                        
                        stats.record_failure(str(msg_id), "FileValidationError")
                        if progress:
                            progress.complete_file_download(msg_id)
                        results[msg_id] = (None, None, None)
                        return
                    
                    # MEDIUM PRIORITY FIX: Use async hashing to not block event loop
                    hash_start = time.time()
                    media_hash = await get_file_hash_async(media_file)
                    hash_time = time.time() - hash_start
                    
                    mime_type = get_mime_type(message.media) if message.media else None
                    actual_size = os.path.getsize(media_file) if os.path.exists(media_file) else 0
                    
                    # Record successful download with timing
                    download_time = time.time() - download_start_time - hash_time
                    stats.record_success(actual_size, download_time)
                    
                    # Complete download tracking
                    if progress:
                        progress.complete_file_download(msg_id)
                        progress.file_downloaded(actual_size, os.path.basename(media_file))
                    
                    results[msg_id] = (media_file, media_hash, mime_type)
                else:
                    logger.warning(f"Download returned None for message {msg_id}")
                    stats.record_failure(str(msg_id), "DownloadReturnedNone")
                    if progress:
                        progress.complete_file_download(msg_id)
                    results[msg_id] = (None, None, None)
        
        except asyncio.CancelledError:
            # Download was cancelled - cleanup partial file
            logger.info(f"Download cancelled for message {msg_id}")
            if media_file and os.path.exists(media_file):
                try:
                    os.remove(media_file)
                    logger.debug(f"Cleaned up partial download: {media_file}")
                except Exception as e:
                    logger.warning(f"Failed to cleanup partial file {media_file}: {e}")
            
            if progress:
                progress.complete_file_download(msg_id)
            results[msg_id] = (None, None, None)
            raise  # Re-raise to propagate cancellation
    
    # Create tasks for all downloads with retry logic
    tasks = [asyncio.create_task(download_single_with_retry(msg, msg_id)) for msg, msg_id in messages_batch]
    
    # Wait for all downloads to complete with proper cancellation handling
    if tasks:
        try:
            await asyncio.gather(*tasks, return_exceptions=True)
        except asyncio.CancelledError:
            # Cancel all pending tasks
            logger.warning("Download batch cancelled, cleaning up...")
            for task in tasks:
                if not task.done():
                    task.cancel()
            
            # Wait for tasks to actually cancel
            await asyncio.gather(*tasks, return_exceptions=True)
            raise
    
    return results

