"""Media file management - indexing, deduplication, and migration."""

import os
import datetime
import unicodedata
import threading
import asyncio
import logging
from pathlib import Path
from functools import lru_cache
from concurrent.futures import ThreadPoolExecutor
from telegram_backup.utils import get_file_hash
from telegram_backup.metadata import normalize_filename_for_search

# HIGH PRIORITY FIX: Thread lock for deduplication operations
# Prevents race conditions when multiple threads try to deduplicate the same file
_deduplication_lock = threading.Lock()

# Async lock for async deduplication operations
_async_deduplication_lock = asyncio.Lock()

# MEDIUM PRIORITY FIX: Logger for error tracking
logger = logging.getLogger('telegram_backup.media_manager')


def make_relative_path(file_path, base_dir):
    """Convert absolute path to relative path from base_dir.
    
    Args:
        file_path: Absolute or relative file path
        base_dir: Base directory (entity backup directory)
    
    Returns:
        Relative path from base_dir (e.g. "media/file.mp4")
    """
    if not file_path:
        return None
    
    try:
        # Convert to Path objects for proper path manipulation
        file_path_obj = Path(file_path).resolve()
        base_dir_obj = Path(base_dir).resolve()
        
        # Get relative path
        rel_path = file_path_obj.relative_to(base_dir_obj)
        return str(rel_path)
    except (ValueError, TypeError):
        # If file_path is not under base_dir, return as is
        return file_path


# LRU cache for frequently accessed file lookups
@lru_cache(maxsize=1000)
def _cached_file_lookup(file_id):
    """Cache wrapper for file_id lookups. Returns cache key only."""
    return file_id


# Thread pool for parallel hash calculation
_hash_executor = ThreadPoolExecutor(max_workers=3)


def normalize_path(path):
    """Normalize Unicode path for consistent comparison.
    
    Converts path to NFC (Canonical Decomposition, followed by Canonical Composition)
    to handle different Unicode representations of the same characters.
    
    Args:
        path: File path string
    
    Returns:
        Normalized path string
    """
    if not path:
        return path
    return unicodedata.normalize('NFC', path)


def find_existing_media_by_params(cursor, metadata_dict):
    """Find existing media file by comparing metadata parameters.
    
    Uses cascading search:
    1. Exact match by size, duration, and resolution
    2. Filter by filename if multiple matches
    3. Fallback to size + fuzzy filename match
    
    Args:
        cursor: Database cursor
        metadata_dict: Dictionary with keys:
            - file_name: str or None
            - file_size: int
            - duration: int or None
            - width: int or None
            - height: int or None
            - file_extension: str or None
            - file_id: str or None (for filename matching)
    
    Returns:
        tuple: (media_file_id, file_path) if found, else (None, None)
    """
    file_name = metadata_dict.get('file_name')
    file_size = metadata_dict.get('file_size', 0)
    duration = metadata_dict.get('duration')
    width = metadata_dict.get('width')
    height = metadata_dict.get('height')
    extension = metadata_dict.get('file_extension')
    file_id = metadata_dict.get('file_id')
    
    if file_size == 0:
        return None, None
    
    # Step 1: Exact match by size, duration, and resolution
    query = """
        SELECT id, file_path, file_name FROM media_files 
        WHERE file_size = ?
    """
    params = [file_size]
    
    # Add optional parameters with NULL handling
    if duration is not None:
        query += " AND (duration = ? OR duration IS NULL)"
        params.append(duration)
    
    if width is not None and height is not None:
        query += " AND ((width = ? AND height = ?) OR (width IS NULL AND height IS NULL))"
        params.extend([width, height])
    
    cursor.execute(query, params)
    results = cursor.fetchall()
    
    if not results:
        return None, None
    
    # Step 2: If multiple results, filter by filename
    if len(results) > 1 and (file_name or file_id):
        # Check if file_id is in the filename
        if file_id:
            for media_id, file_path, db_file_name in results:
                if db_file_name and file_id in db_file_name:
                    return media_id, file_path
        
        # Fallback to normalized filename matching
        if file_name:
            normalized_search = normalize_filename_for_search(file_name)
            
            for media_id, file_path, db_file_name in results:
                if db_file_name:
                    normalized_db = normalize_filename_for_search(db_file_name)
                    # Check if normalized names match or one contains the other
                    if normalized_search and normalized_db:
                        if normalized_search in normalized_db or normalized_db in normalized_search:
                            return media_id, file_path
    
    # Step 3: Return first match if no filename filtering succeeded
    if results:
        return results[0][0], results[0][1]
    
    return None, None


def get_metadata_value(cursor, key):
    """Get a metadata value from backup_metadata table."""
    cursor.execute("SELECT value FROM backup_metadata WHERE key = ?", (key,))
    result = cursor.fetchone()
    return result[0] if result else None


def set_metadata_value(cursor, key, value):
    """Set a metadata value in backup_metadata table."""
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    cursor.execute("""
        INSERT OR REPLACE INTO backup_metadata (key, value, updated_at)
        VALUES (?, ?, ?)
    """, (key, value, now))


def should_reindex_media(cursor, media_dir):
    """Check if media directory needs reindexing.
    
    Returns True if:
    - Never indexed before
    - Media directory was modified since last index
    - File count in DB doesn't match directory
    
    Args:
        cursor: Database cursor
        media_dir: Path to media directory
        
    Returns:
        bool: True if reindexing is needed
    """
    if not os.path.exists(media_dir):
        return False
    
    # Get last index time
    last_index_time = get_metadata_value(cursor, 'last_media_index_time')
    if not last_index_time:
        return True  # Never indexed
    
    # Check if directory was modified since last index
    try:
        last_index_timestamp = datetime.datetime.fromisoformat(last_index_time)
        dir_mtime = datetime.datetime.fromtimestamp(os.path.getmtime(media_dir), tz=datetime.timezone.utc)
        
        if dir_mtime > last_index_timestamp:
            return True  # Directory modified
    except:
        return True  # Error checking, safer to reindex
    
    # Check file count consistency
    cursor.execute("SELECT COUNT(*) FROM media_files")
    db_count = cursor.fetchone()[0]
    
    try:
        actual_count = sum(1 for f in os.listdir(media_dir) 
                          if os.path.isfile(os.path.join(media_dir, f)) and not f.startswith('.'))
        
        if abs(db_count - actual_count) > 5:  # Allow small tolerance
            return True  # Significant mismatch
    except:
        return True
    
    return False  # No reindexing needed


def index_existing_media(cursor, entity_id, conn, media_dir):
    """Index all existing media files in the media folder before backup.
    
    Now with smart conditional indexing - only reindexes if directory changed.
    Extracts full metadata including filename, extension, duration, resolution.
    
    Args:
        cursor: Database cursor
        entity_id: Entity ID
        conn: Database connection
        media_dir: Path to media directory
    """
    from telegram_backup.metadata import extract_file_metadata
    
    if not os.path.exists(media_dir):
        return 0
    
    # Check if reindexing is needed
    if not should_reindex_media(cursor, media_dir):
        cursor.execute("SELECT COUNT(*) FROM media_files")
        existing_count = cursor.fetchone()[0]
        return 0
    
    # Step 1: Clean up database records for missing files
    cursor.execute("SELECT id, file_path FROM media_files")
    all_records = cursor.fetchall()
    
    deleted_records = 0
    for record_id, file_path in all_records:
        if not os.path.exists(file_path):
            # File doesn't exist - remove from database
            cursor.execute("DELETE FROM media_files WHERE id = ?", (record_id,))
            deleted_records += 1
            
            # Also clear media_file_id references in messages
            cursor.execute("UPDATE messages SET media_file_id = NULL WHERE media_file_id = ?", (record_id,))
    
    if deleted_records > 0:
        conn.commit()
    
    # Step 2: Index new files from disk with full metadata
    indexed_count = 0
    skipped_count = 0
    
    # Batch operations for better performance
    batch_inserts = []
    
    # Get all files in media directory
    for filename in os.listdir(media_dir):
        if filename.startswith('.'):  # Skip hidden files like .DS_Store
            continue
            
        file_path = os.path.join(media_dir, filename)
        if not os.path.isfile(file_path):
            continue
        
        # Check if already indexed
        cursor.execute("SELECT id FROM media_files WHERE file_path = ?", (file_path,))
        if cursor.fetchone():
            skipped_count += 1
            continue
        
        # Extract full metadata
        try:
            metadata = extract_file_metadata(file_path)
            file_hash = get_file_hash(file_path)
            
            if not file_hash:
                continue
            
            # Try to get media info from messages table (if exists)
            cursor.execute("""
                SELECT file_unique_id, file_id, media_type 
                FROM messages 
                WHERE media_file = ? 
                LIMIT 1
            """, (file_path,))
            result = cursor.fetchone()
            
            file_unique_id = result[0] if result else None
            file_id = result[1] if result else None
            media_type = result[2] if result else None
            
            # Add to batch with all metadata
            indexed_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
            batch_inserts.append((
                file_path,
                file_hash,
                metadata['file_size'],
                file_unique_id,
                file_id,
                media_type,
                None,  # mime_type
                metadata['file_name'],
                metadata['file_extension'],
                metadata['duration'],
                metadata['width'],
                metadata['height'],
                indexed_at
            ))
            
            indexed_count += 1
            
            # Insert batch every 100 files
            if len(batch_inserts) >= 100:
                cursor.executemany("""
                    INSERT OR IGNORE INTO media_files 
                    (file_path, file_hash, file_size, file_unique_id, file_id, media_type, mime_type,
                     file_name, file_extension, duration, width, height, indexed_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, batch_inserts)
                conn.commit()
                batch_inserts = []
                
        except Exception as e:
            continue
    
    # Insert remaining batch
    if batch_inserts:
        cursor.executemany("""
            INSERT OR IGNORE INTO media_files 
            (file_path, file_hash, file_size, file_unique_id, file_id, media_type, mime_type,
             file_name, file_extension, duration, width, height, indexed_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch_inserts)
    
    # Update metadata with indexing time
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    set_metadata_value(cursor, 'last_media_index_time', now)
    
    conn.commit()
    return indexed_count


def migrate_legacy_media_data(cursor, entity_id, conn):
    """Migrate legacy media data from messages table to media_files table.
    
    Scans messages table for records with media_file/media_hash and migrates
    them to the new media_files table structure.
    """
    # Check if old columns exist
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'")
    table_schema = cursor.fetchone()
    if not table_schema or 'media_file' not in table_schema[0]:
        return 0
    
    migrated_count = 0
    skipped_count = 0
    
    # Get all messages with media files
    cursor.execute("""
        SELECT DISTINCT media_file, media_hash, file_size, file_unique_id, file_id, media_type
        FROM messages 
        WHERE media_file IS NOT NULL 
        AND media_file != ''
        AND entity_id = ?
    """, (entity_id,))
    
    legacy_records = cursor.fetchall()
    total_records = len(legacy_records)
    
    if total_records == 0:
        return 0
    
    for i, (media_file, media_hash, file_size, file_unique_id, file_id, media_type) in enumerate(legacy_records, 1):
        if not media_file or not os.path.exists(media_file):
            skipped_count += 1
            continue
        
        # Check if already in media_files
        cursor.execute("SELECT id FROM media_files WHERE file_path = ?", (media_file,))
        existing = cursor.fetchone()
        
        if existing:
            media_file_id = existing[0]
            # Update messages to reference the media_file_id
            cursor.execute("""
                UPDATE messages 
                SET media_file_id = ? 
                WHERE media_file = ? AND entity_id = ?
            """, (media_file_id, media_file, entity_id))
            skipped_count += 1
            continue
        
        # Calculate hash if missing
        if not media_hash:
            media_hash = get_file_hash(media_file)
        
        # Get file size if missing
        if not file_size:
            try:
                file_size = os.path.getsize(media_file)
            except:
                file_size = 0
        
        if not media_hash:
            skipped_count += 1
            continue
        
        # Insert into media_files
        now = datetime.datetime.now(datetime.timezone.utc).isoformat()
        cursor.execute("""
            INSERT OR IGNORE INTO media_files 
            (file_path, file_hash, file_size, file_unique_id, file_id, media_type, indexed_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (media_file, media_hash, file_size, file_unique_id, file_id, media_type, now, now))
        
        media_file_id = cursor.lastrowid
        
        # Update all messages with this media file to reference the new media_file_id
        cursor.execute("""
            UPDATE messages 
            SET media_file_id = ? 
            WHERE media_file = ? AND entity_id = ?
        """, (media_file_id, media_file, entity_id))
        
        migrated_count += 1
        
        if i % 50 == 0:
            conn.commit()
    
    conn.commit()
    return migrated_count


async def find_or_create_media_file(cursor, conn, file_id, file_size, media, media_type=None, access_hash=None, media_dir=''):
    """Find existing media file by metadata or prepare path for new download.
    
    NEW: Uses metadata comparison to find existing files WITHOUT downloading.
    
    Args:
        cursor: Database cursor
        conn: Database connection (for commit after updates)
        file_id: Telegram file ID (unique identifier)
        file_size: File size in bytes
        media: Telegram media object (for metadata extraction)
        media_type: Media type string
        access_hash: Telegram access hash
        media_dir: Directory for media files
    
    Returns:
        tuple: (media_file_id, file_path, should_download)
        - media_file_id: ID from media_files table (None if not found)
        - file_path: Path to existing or future file
        - should_download: True if file needs to be downloaded
    """
    from telegram_backup.telegram_api.media import generate_media_filename
    from telegram_backup.metadata import extract_telegram_media_metadata
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # Step 1: Extract metadata from Telegram media object
    metadata = extract_telegram_media_metadata(media)
    metadata['file_size'] = file_size  # Ensure size is set
    metadata['file_id'] = file_id  # Add file_id for filename matching
    
    # Step 2: Search by metadata parameters FIRST
    existing_media_id, existing_path = find_existing_media_by_params(cursor, metadata)
    
    if existing_media_id and existing_path:
        # Found existing media - update file_id if missing
        cursor.execute("""
            UPDATE media_files 
            SET file_id = COALESCE(file_id, ?),
                access_hash = COALESCE(access_hash, ?),
                last_used_at = ?
            WHERE id = ?
        """, (file_id, access_hash, now, existing_media_id))
        
        # Commit immediately after metadata update
        conn.commit()
        
        # Try to rename to deterministic filename if needed
        if file_id and media:
            from telegram_backup.telegram_api.media import get_file_extension
            
            # Get absolute path
            if not os.path.isabs(existing_path):
                from telegram_backup.utils import get_backup_dir
                # Extract entity info from path
                existing_path_abs = os.path.join(media_dir, os.path.basename(existing_path)) if media_dir else existing_path
            else:
                existing_path_abs = existing_path
            
            # Check if file exists and doesn't already use fileID naming
            if os.path.exists(existing_path_abs):
                current_filename = os.path.basename(existing_path_abs)
                
                # Only rename if not already using fileID format
                if not current_filename.startswith(file_id):
                    _, extension = os.path.splitext(existing_path_abs)
                    
                    if extension:
                        new_filename = f"{file_id}{extension}"
                        new_path_abs = os.path.join(os.path.dirname(existing_path_abs), new_filename)
                        
                        # Check target doesn't exist
                        if not os.path.exists(new_path_abs) or new_path_abs == existing_path_abs:
                            try:
                                os.rename(existing_path_abs, new_path_abs)
                                
                                # Update database with new path
                                cursor.execute("""
                                    UPDATE media_files 
                                    SET file_path = ?
                                    WHERE id = ?
                                """, (new_path_abs, existing_media_id))
                                
                                # CRITICAL: Commit immediately after file rename
                                # to keep filesystem and database in sync
                                conn.commit()
                                
                                existing_path = new_path_abs
                            except Exception:
                                pass  # If rename fails, continue with old path
        
        return existing_media_id, existing_path, False  # Don't download
    
    # Step 3: Fallback to old logic - check by file_id in database
    if file_id:
        cursor.execute("""
            SELECT id, file_path, file_hash 
            FROM media_files 
            WHERE file_id = ?
            LIMIT 1
        """, (file_id,))
        result = cursor.fetchone()
        
        if result:
            media_file_id, existing_path, existing_hash = result
            
            # Try to rename to deterministic filename if needed
            if file_id and media and existing_path:
                # Get absolute path
                if not os.path.isabs(existing_path):
                    existing_path_abs = os.path.join(media_dir, os.path.basename(existing_path)) if media_dir else existing_path
                else:
                    existing_path_abs = existing_path
                
                # Check if file exists and doesn't already use fileID naming
                if os.path.exists(existing_path_abs):
                    current_filename = os.path.basename(existing_path_abs)
                    
                    # Only rename if not already using fileID format
                    if not current_filename.startswith(file_id):
                        _, extension = os.path.splitext(existing_path_abs)
                        
                        if extension:
                            new_filename = f"{file_id}{extension}"
                            new_path_abs = os.path.join(os.path.dirname(existing_path_abs), new_filename)
                            
                            # Check target doesn't exist
                            if not os.path.exists(new_path_abs) or new_path_abs == existing_path_abs:
                                try:
                                    os.rename(existing_path_abs, new_path_abs)
                                    
                                    # Update database with new path
                                    cursor.execute("""
                                        UPDATE media_files 
                                        SET file_path = ?
                                        WHERE id = ?
                                    """, (new_path_abs, media_file_id))
                                    
                                    # CRITICAL: Commit immediately after file rename
                                    # to keep filesystem and database in sync
                                    conn.commit()
                                    
                                    existing_path = new_path_abs
                                except Exception:
                                    pass  # If rename fails, continue with old path
            
            return media_file_id, existing_path, False  # Don't download
    
    # Step 4: Check filesystem for deterministic filename
    if file_id and media:
        deterministic_path = generate_media_filename(file_id, media, media_type, media_dir)
        
        if deterministic_path and os.path.exists(deterministic_path):
            # File exists but not in database - index it immediately
            file_hash = get_file_hash(deterministic_path)
            
            if file_hash:
                # Add to database with all metadata
                cursor.execute("""
                    INSERT OR IGNORE INTO media_files 
                    (file_path, file_hash, file_size, file_id, access_hash, media_type, 
                     file_name, file_extension, duration, width, height, indexed_at, last_used_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (deterministic_path, file_hash, file_size, file_id, access_hash, media_type,
                      metadata.get('file_name'), metadata.get('file_extension'),
                      metadata.get('duration'), metadata.get('width'), metadata.get('height'),
                      now, now))
                
                media_file_id = cursor.lastrowid
                if media_file_id > 0:
                    return media_file_id, deterministic_path, False  # Don't download
    
    # Step 5: Return deterministic path for download
    if file_id and media:
        deterministic_path = generate_media_filename(file_id, media, media_type, media_dir)
        if deterministic_path:
            return None, deterministic_path, True  # Download to this path
    
    # Ultimate fallback: Let Telethon use its default naming
    return None, None, True  # Download needed


async def save_media_file(cursor, file_path, file_hash, file_size, file_id=None, access_hash=None, media_type=None, mime_type=None, entity_backup_dir=None):
    """Save media file info to media_files table with hash-based deduplication.
    
    Simplified post-download deduplication:
    - Check for hash+size duplicates
    - If found, delete new file and reuse existing
    - Rename to deterministic name for future Level 2 detection
    - Extract and save full metadata
    
    HIGH PRIORITY FIX: Thread-safe deduplication with lock
    
    Args:
        cursor: Database cursor
        file_path: Path to the downloaded file
        file_hash: MD5 hash of the file
        file_size: File size in bytes
        file_id: Telegram file ID
        access_hash: Telegram access hash
        media_type: Media type string
        mime_type: MIME type of the file
        entity_backup_dir: Base directory for relative path conversion (optional)
    
    Returns:
        media_file_id: ID from media_files table
    """
    from telegram_backup.metadata import extract_file_metadata
    
    if not file_path or not os.path.exists(file_path):
        return None
    
    # Calculate hash and size if not provided
    if not file_hash:
        file_hash = get_file_hash(file_path)
    if not file_size:
        file_size = os.path.getsize(file_path)
    
    if not file_hash:
        return None
    
    # Convert to relative path for storage if entity_backup_dir is provided
    file_path_for_db = make_relative_path(file_path, entity_backup_dir) if entity_backup_dir else file_path
    
    # Extract metadata from downloaded file
    metadata = extract_file_metadata(file_path)
    
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    
    # HIGH PRIORITY FIX: Use lock for deduplication check and file operations
    with _deduplication_lock:
        # Check for hash+size duplicates
        cursor.execute("""
            SELECT id, file_path FROM media_files 
            WHERE file_hash = ? AND file_size = ?
            LIMIT 1
        """, (file_hash, file_size))
        duplicate = cursor.fetchone()
        
        if duplicate:
            duplicate_id, duplicate_path = duplicate
            
            # CRITICAL FIX: Check if duplicate file still exists before deleting new file
            if not os.path.exists(duplicate_path):
                # Duplicate file was deleted - keep the new file and update DB reference
                cursor.execute("""
                    UPDATE media_files 
                    SET file_path = ?,
                        file_id = COALESCE(?, file_id),
                        access_hash = COALESCE(?, access_hash),
                        last_used_at = ?
                    WHERE id = ?
                """, (file_path_for_db, file_id, access_hash, now, duplicate_id))
                return duplicate_id
            
            # Delete the newly downloaded file (it's a duplicate and original exists)
            if file_path != duplicate_path:
                try:
                    os.remove(file_path)
                except Exception as e:
                    pass
            
            # Update existing record with file_id if missing
            if file_id:
                cursor.execute("""
                    UPDATE media_files 
                    SET file_id = COALESCE(file_id, ?),
                        access_hash = COALESCE(access_hash, ?),
                        last_used_at = ?
                    WHERE id = ?
                """, (file_id, access_hash, now, duplicate_id))
                
                # Try to rename duplicate to deterministic name for future reuse
                if media_type:
                    from telegram_backup.telegram_api.media import get_file_extension
                    extension = get_file_extension(None, media_type)
                    if not extension or extension == '.bin':
                        _, extension = os.path.splitext(duplicate_path)
                    
                    media_dir = os.path.dirname(duplicate_path)
                    deterministic_name = f"{file_id}{extension}"
                    deterministic_path = os.path.join(media_dir, deterministic_name)
                    
                    if duplicate_path != deterministic_path and not os.path.exists(deterministic_path):
                        try:
                            os.rename(duplicate_path, deterministic_path)
                            cursor.execute("UPDATE media_files SET file_path = ? WHERE id = ?", 
                                         (deterministic_path, duplicate_id))
                        except Exception as e:
                            # MEDIUM PRIORITY FIX: Log rename errors
                            logger.warning(f"Failed to rename file {duplicate_path} to {deterministic_path}: {e}")
            else:
                cursor.execute("UPDATE media_files SET last_used_at = ? WHERE id = ?", (now, duplicate_id))
            
            return duplicate_id
        
        # Check if this exact path already exists in DB
        cursor.execute("SELECT id FROM media_files WHERE file_path = ?", (file_path_for_db,))
        result = cursor.fetchone()
        
        if result:
            # Update existing entry with metadata
            media_file_id = result[0]
            cursor.execute("""
                UPDATE media_files 
                SET file_hash = ?, file_size = ?, 
                    file_id = COALESCE(?, file_id),
                    access_hash = COALESCE(?, access_hash),
                    media_type = COALESCE(?, media_type),
                    mime_type = COALESCE(?, mime_type),
                    file_name = COALESCE(?, file_name),
                    file_extension = COALESCE(?, file_extension),
                    duration = COALESCE(?, duration),
                    width = COALESCE(?, width),
                    height = COALESCE(?, height),
                    last_used_at = ?
                WHERE id = ?
            """, (file_hash, file_size, file_id, access_hash, media_type, mime_type,
                  metadata.get('file_name'), metadata.get('file_extension'),
                  metadata.get('duration'), metadata.get('width'), metadata.get('height'),
                  now, media_file_id))
            return media_file_id
        
        # Rename to deterministic name if we have file_id
        if file_id and media_type:
            from telegram_backup.telegram_api.media import get_file_extension
            extension = get_file_extension(None, media_type)
            
            if not extension or extension == '.bin':
                _, extension = os.path.splitext(file_path)
            
            media_dir = os.path.dirname(file_path)
            deterministic_name = f"{file_id}{extension}"
            deterministic_path = os.path.join(media_dir, deterministic_name)
            
            if file_path != deterministic_path and not os.path.exists(deterministic_path):
                try:
                    os.rename(file_path, deterministic_path)
                    file_path = deterministic_path
                    # Update relative path for DB
                    file_path_for_db = make_relative_path(file_path, entity_backup_dir) if entity_backup_dir else file_path
                    # Update metadata with new name
                    metadata = extract_file_metadata(file_path)
                except Exception as e:
                    # MEDIUM PRIORITY FIX: Log rename errors
                    logger.warning(f"Failed to rename file {file_path} to {deterministic_path}: {e}")
        
        # Insert new entry with full metadata
        cursor.execute("""
            INSERT OR IGNORE INTO media_files 
            (file_path, file_hash, file_size, file_id, access_hash, media_type, mime_type,
             file_name, file_extension, duration, width, height, indexed_at, last_used_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (file_path_for_db, file_hash, file_size, file_id, access_hash, media_type, mime_type,
              metadata.get('file_name'), metadata.get('file_extension'),
              metadata.get('duration'), metadata.get('width'), metadata.get('height'),
              now, now))
        
        media_file_id = cursor.lastrowid
        
        # If INSERT was ignored due to UNIQUE constraint, get the existing record
        if media_file_id == 0:
            cursor.execute("""
                SELECT id FROM media_files 
                WHERE file_hash = ? AND file_size = ?
                LIMIT 1
            """, (file_hash, file_size))
            result = cursor.fetchone()
            if result:
                media_file_id = result[0]
        
        return media_file_id


def cleanup_orphaned_files(cursor, conn, media_dir):
    """Clean up orphaned media files (exist on disk but not in database).
    
    Args:
        cursor: Database cursor
        conn: Database connection
        media_dir: Path to media directory
    
    Returns:
        tuple: (deleted_count, freed_bytes)
    """
    if not os.path.exists(media_dir):
        return 0, 0
    
    # Get all file paths from database
    cursor.execute("SELECT file_path FROM media_files")
    db_files = set(row[0] for row in cursor.fetchall())
    
    deleted_count = 0
    freed_bytes = 0
    
    # Scan all files in media directory
    for filename in os.listdir(media_dir):
        if filename.startswith('.'):  # Skip hidden files
            continue
        
        file_path = os.path.join(media_dir, filename)
        
        if not os.path.isfile(file_path):
            continue
        
        # Check if file is in database
        if file_path not in db_files:
            # Check file age (safety: don't delete files created in last 5 minutes)
            file_mtime = os.path.getmtime(file_path)
            import time
            if time.time() - file_mtime < 300:  # 5 minutes
                continue
            
            try:
                file_size = os.path.getsize(file_path)
                os.remove(file_path)
                deleted_count += 1
                freed_bytes += file_size
            except Exception as e:
                pass
    
    return deleted_count, freed_bytes


def cleanup_unused_media_files(cursor, conn, media_dir):
    """Clean up media files not referenced by any message in the backup.
    
    Удаляет файлы которые есть в media_files, но НЕ используются ни в одном сообщении.
    Это файлы-дубликаты или временные файлы которые остались после дедупликации.
    
    Args:
        cursor: Database cursor
        conn: Database connection
        media_dir: Path to media directory
    
    Returns:
        tuple: (deleted_count, freed_bytes)
    """
    if not os.path.exists(media_dir):
        return 0, 0
    
    # Find media files not referenced by any message
    cursor.execute("""
        SELECT mf.id, mf.file_path, mf.file_size
        FROM media_files mf
        LEFT JOIN messages m ON m.media_file_id = mf.id
        WHERE m.id IS NULL
    """)
    
    unused_files = cursor.fetchall()
    deleted_count = 0
    freed_bytes = 0
    
    if not unused_files:
        return 0, 0
    
    for media_id, file_path, file_size in unused_files:
        # Delete physical file
        if os.path.exists(file_path):
            try:
                os.remove(file_path)
                deleted_count += 1
                freed_bytes += file_size if file_size else 0
            except Exception as e:
                continue
        
        # Delete database record
        cursor.execute("DELETE FROM media_files WHERE id = ?", (media_id,))
    
    conn.commit()
    
    return deleted_count, freed_bytes


def cleanup_duplicate_files_by_hash(cursor, conn, media_dir):
    """Clean up duplicate media files based on hash+size, keep only one copy.
    
    Args:
        cursor: Database cursor
        conn: Database connection
        media_dir: Path to media directory
    
    Returns:
        tuple: (deleted_count, freed_bytes)
    """
    # Find files with same hash and size
    cursor.execute("""
        SELECT file_hash, file_size, COUNT(*) as count
        FROM media_files
        WHERE file_hash IS NOT NULL AND file_size > 0
        GROUP BY file_hash, file_size
        HAVING count > 1
    """)
    
    duplicates_groups = cursor.fetchall()
    
    if not duplicates_groups:
        return 0, 0
    
    deleted_count = 0
    freed_bytes = 0
    
    for file_hash, file_size, count in duplicates_groups:
        # Get all files with this hash+size
        cursor.execute("""
            SELECT id, file_path, file_id, indexed_at
            FROM media_files
            WHERE file_hash = ? AND file_size = ?
            ORDER BY indexed_at ASC
        """, (file_hash, file_size))
        
        duplicates = cursor.fetchall()
        
        if len(duplicates) <= 1:
            continue
        
        # Keep the first one (oldest), delete the rest
        keep_id, keep_path, keep_file_id, keep_indexed = duplicates[0]
        
        for dup_id, dup_path, dup_file_id, dup_indexed in duplicates[1:]:
            # Update all messages that reference this duplicate to use the kept one
            cursor.execute("""
                UPDATE messages
                SET media_file_id = ?
                WHERE media_file_id = ?
            """, (keep_id, dup_id))
            
            # Delete physical file if it exists and is different from the kept one
            if dup_path != keep_path and os.path.exists(dup_path):
                try:
                    os.remove(dup_path)
                    deleted_count += 1
                    freed_bytes += file_size
                except Exception as e:
                    pass
            
            # Delete database record
            cursor.execute("DELETE FROM media_files WHERE id = ?", (dup_id,))
    
    conn.commit()
    
    return deleted_count, freed_bytes

