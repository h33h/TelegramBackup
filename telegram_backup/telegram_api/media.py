"""Media downloading with parallel processing."""

import asyncio
import os
import mimetypes
from functools import lru_cache
from telegram_backup.utils import get_file_hash, get_file_hash_async  # MEDIUM PRIORITY FIX
from telegram_backup.file_validator import validate_file_after_download  # HIGH PRIORITY FIX


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


async def download_media_batch(client, messages_batch, media_dir, semaphore, progress=None):
    """Download media files in parallel with concurrency control.
    
    Args:
        client: Telegram client
        messages_batch: List of tuples (message, message_id)
        media_dir: Directory path to save media files
        semaphore: asyncio.Semaphore for concurrency control
        progress: DownloadProgress instance for tracking (optional)
        
    Returns:
        dict: {message_id: (media_file, media_hash, mime_type)}
    """
    results = {}
    
    async def download_single(message, msg_id):
        async with semaphore:
            try:
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
                        try:
                            if os.path.exists(media_file):
                                os.remove(media_file)
                        except:
                            pass
                        
                        if progress:
                            progress.complete_file_download(msg_id)
                        results[msg_id] = (None, None, None)
                        return
                    
                    # MEDIUM PRIORITY FIX: Use async hashing to not block event loop
                    media_hash = await get_file_hash_async(media_file)
                    mime_type = get_mime_type(message.media) if message.media else None
                    actual_size = os.path.getsize(media_file) if os.path.exists(media_file) else 0
                    
                    # Complete download tracking
                    if progress:
                        progress.complete_file_download(msg_id)
                        progress.file_downloaded(actual_size, os.path.basename(media_file))
                    
                    results[msg_id] = (media_file, media_hash, mime_type)
                else:
                    if progress:
                        progress.complete_file_download(msg_id)
                    results[msg_id] = (None, None, None)
            except Exception as e:
                if progress:
                    progress.complete_file_download(msg_id)
                results[msg_id] = (None, None, None)
    
    # Create tasks for all downloads
    tasks = [download_single(msg, msg_id) for msg, msg_id in messages_batch]
    
    # Wait for all downloads to complete
    if tasks:
        await asyncio.gather(*tasks, return_exceptions=True)
    
    return results

