"""Media metadata extraction for deduplication and indexing."""

import os
import re


def extract_file_metadata(file_path):
    """Extract metadata from a file on disk.
    
    Args:
        file_path: Path to the file
        
    Returns:
        dict: {
            'file_name': str,
            'file_extension': str,
            'file_size': int,
            'duration': int or None,
            'width': int or None,
            'height': int or None
        }
    """
    metadata = {
        'file_name': None,
        'file_extension': None,
        'file_size': 0,
        'duration': None,
        'width': None,
        'height': None
    }
    
    if not os.path.exists(file_path):
        return metadata
    
    # Extract basic file info
    metadata['file_name'] = os.path.basename(file_path)
    metadata['file_extension'] = os.path.splitext(file_path)[1].lower()
    
    try:
        metadata['file_size'] = os.path.getsize(file_path)
    except:
        pass
    
    # Try to extract video/audio metadata using pymediainfo if available
    try:
        from pymediainfo import MediaInfo
        
        media_info = MediaInfo.parse(file_path)
        
        # Get video track info
        for track in media_info.tracks:
            if track.track_type == 'Video':
                if track.duration:
                    metadata['duration'] = int(track.duration / 1000)  # Convert ms to seconds
                if track.width:
                    metadata['width'] = track.width
                if track.height:
                    metadata['height'] = track.height
                break
            elif track.track_type == 'Audio' and not metadata['duration']:
                if track.duration:
                    metadata['duration'] = int(track.duration / 1000)
    except ImportError:
        # pymediainfo not installed - skip advanced metadata
        pass
    except Exception as e:
        # Error parsing media - skip
        pass
    
    return metadata


def extract_telegram_media_metadata(media):
    """Extract metadata from Telegram media object.
    
    Args:
        media: Telegram media object (MessageMediaPhoto or MessageMediaDocument)
        
    Returns:
        dict: {
            'file_name': str or None,
            'file_extension': str or None,
            'file_size': int,
            'duration': int or None,
            'width': int or None,
            'height': int or None
        }
    """
    metadata = {
        'file_name': None,
        'file_extension': None,
        'file_size': 0,
        'duration': None,
        'width': None,
        'height': None
    }
    
    if not media:
        return metadata
    
    try:
        # Handle MessageMediaPhoto
        if hasattr(media, 'photo') and media.photo:
            photo = media.photo
            
            # Get largest photo size
            if hasattr(photo, 'sizes') and photo.sizes:
                max_size = 0
                for size in photo.sizes:
                    if hasattr(size, 'size'):
                        max_size = max(max_size, size.size)
                    # Get dimensions from PhotoSize
                    if hasattr(size, 'w') and hasattr(size, 'h'):
                        metadata['width'] = size.w
                        metadata['height'] = size.h
                
                metadata['file_size'] = max_size
            
            metadata['file_extension'] = '.jpg'
            
        # Handle MessageMediaDocument (videos, files, audio, etc.)
        elif hasattr(media, 'document') and media.document:
            doc = media.document
            
            if hasattr(doc, 'size'):
                metadata['file_size'] = doc.size
            
            # Extract attributes
            if hasattr(doc, 'attributes') and doc.attributes:
                for attr in doc.attributes:
                    attr_type = getattr(attr, '_', None)
                    
                    # Get filename
                    if attr_type == 'DocumentAttributeFilename':
                        if hasattr(attr, 'file_name'):
                            metadata['file_name'] = attr.file_name
                            _, ext = os.path.splitext(attr.file_name)
                            if ext:
                                metadata['file_extension'] = ext.lower()
                    
                    # Get video attributes
                    elif attr_type == 'DocumentAttributeVideo':
                        if hasattr(attr, 'duration'):
                            metadata['duration'] = attr.duration
                        if hasattr(attr, 'w'):
                            metadata['width'] = attr.w
                        if hasattr(attr, 'h'):
                            metadata['height'] = attr.h
                    
                    # Get audio attributes
                    elif attr_type == 'DocumentAttributeAudio':
                        if hasattr(attr, 'duration'):
                            metadata['duration'] = attr.duration
            
            # Fallback to mime_type for extension
            if not metadata['file_extension'] and hasattr(doc, 'mime_type'):
                import mimetypes
                ext = mimetypes.guess_extension(doc.mime_type)
                if ext:
                    if ext == '.jpe':
                        ext = '.jpg'
                    metadata['file_extension'] = ext.lower()
        
    except Exception as e:
        # If extraction fails, return partial metadata
        pass
    
    return metadata


def normalize_filename_for_search(filename):
    """Normalize filename for fuzzy search.
    
    Removes extension and patterns like (1), (2), etc.
    
    Args:
        filename: Original filename
        
    Returns:
        str: Normalized base name for searching
    """
    if not filename:
        return ""
    
    # Remove extension
    base_name, _ = os.path.splitext(filename)
    
    # Remove patterns like " (1)", " (2)", etc. at the end
    base_name = re.sub(r'\s*\(\d+\)\s*$', '', base_name)
    
    # Remove extra whitespace
    base_name = base_name.strip()
    
    return base_name

