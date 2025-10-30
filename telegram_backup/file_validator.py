"""File validation utilities for downloaded media files.
"""

import os


def validate_downloaded_file(file_path, expected_size=None, media_type=None):
    """Validate a downloaded file for correctness and completeness.
    
    Checks:
    1. File exists
    2. File is not empty
    3. File size matches expected (if provided)
    4. File format matches extension (basic check)
    
    Args:
        file_path: Path to the downloaded file
        expected_size: Expected file size in bytes (optional)
        media_type: Expected media type (optional, e.g., 'MessageMediaPhoto')
    
    Returns:
        tuple: (is_valid: bool, error_message: str or None)
    """
    # Check file exists
    if not os.path.exists(file_path):
        return False, "File does not exist"
    
    # Check file is not empty
    try:
        actual_size = os.path.getsize(file_path)
    except Exception as e:
        return False, f"Cannot get file size: {e}"
    
    if actual_size == 0:
        return False, "File is empty"
    
    # Check size matches expected (with 1% tolerance for metadata differences)
    if expected_size is not None and expected_size > 0:
        tolerance = max(1024, int(expected_size * 0.01))  # 1% or 1KB minimum
        size_diff = abs(actual_size - expected_size)
        
        if size_diff > tolerance:
            return False, f"Size mismatch: expected {expected_size}, got {actual_size} (diff: {size_diff})"
    
    # Basic format validation based on extension
    _, ext = os.path.splitext(file_path)
    ext = ext.lower()
    
    if ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']:
        # Validate image file has proper magic bytes
        try:
            with open(file_path, 'rb') as f:
                header = f.read(12)
                
            if ext in ['.jpg', '.jpeg']:
                if not header.startswith(b'\xff\xd8\xff'):
                    return False, "Invalid JPEG magic bytes"
            elif ext == '.png':
                if not header.startswith(b'\x89PNG\r\n\x1a\n'):
                    return False, "Invalid PNG magic bytes"
            elif ext == '.gif':
                if not (header.startswith(b'GIF87a') or header.startswith(b'GIF89a')):
                    return False, "Invalid GIF magic bytes"
            elif ext == '.webp':
                if not (header.startswith(b'RIFF') and header[8:12] == b'WEBP'):
                    return False, "Invalid WebP magic bytes"
        except Exception as e:
            # If we can't read the file, consider it invalid
            return False, f"Cannot read file for validation: {e}"
    
    elif ext in ['.mp4', '.mov', '.avi', '.mkv', '.webm']:
        # Basic video file validation - check minimum size
        if actual_size < 1024:  # Videos should be at least 1KB
            return False, f"Video file too small: {actual_size} bytes"
    
    # File passed all validation checks
    return True, None


def validate_file_after_download(file_path, expected_size=None, media_type=None):
    """Validate file after download and log any issues.
    
    Args:
        file_path: Path to the downloaded file
        expected_size: Expected file size
        media_type: Media type
    
    Returns:
        bool: True if file is valid, False otherwise
    """
    is_valid, error = validate_downloaded_file(file_path, expected_size, media_type)
    
    if not is_valid:
        print(f"⚠️  File validation failed: {file_path}")
        print(f"   Error: {error}")
        return False
    
    return True

