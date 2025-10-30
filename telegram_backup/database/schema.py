"""Database schema management and migrations."""

import sqlite3


def create_messages_table(cursor):
    """Create the messages table with all columns."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER,
        entity_id INTEGER,
        date TEXT,
        text TEXT,
        media_type TEXT,
        media_file TEXT,
        media_hash TEXT,
        forwarded TEXT,
        from_id TEXT,
        views INTEGER,
        sender_name TEXT,
        reply_to_msg_id INTEGER,
        reactions TEXT,
        web_preview TEXT,
        extraction_time TEXT,
        is_service_message BOOLEAN,
        is_voice_message BOOLEAN,
        is_pinned BOOLEAN,
        user_id TEXT,
        file_id TEXT,
        file_unique_id TEXT,
        file_size INTEGER,
        media_file_id INTEGER,
        PRIMARY KEY (id, entity_id),
        FOREIGN KEY (media_file_id) REFERENCES media_files(id)
    )""")


def create_media_files_table(cursor):
    """Create the media_files table for media deduplication."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS media_files (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        file_path TEXT UNIQUE NOT NULL,
        file_hash TEXT NOT NULL,
        file_size INTEGER NOT NULL,
        file_unique_id TEXT,
        file_id TEXT,
        access_hash TEXT,
        media_type TEXT,
        mime_type TEXT,
        file_name TEXT,
        file_extension TEXT,
        duration INTEGER,
        width INTEGER,
        height INTEGER,
        indexed_at TEXT,
        last_used_at TEXT
    )""")


def create_media_indexes(cursor):
    """Create indexes on media_files table for faster lookups."""
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_hash ON media_files(file_hash)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_unique_id ON media_files(file_unique_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_file_id ON media_files(file_id)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_size ON media_files(file_size)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_path ON media_files(file_path)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_name ON media_files(file_name)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_size_duration ON media_files(file_size, duration)")
    cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_resolution ON media_files(width, height)")
    
    # CRITICAL FIX: Add UNIQUE constraint on (file_hash, file_size) for DB-level deduplication
    # This prevents race conditions when multiple threads try to insert the same file
    cursor.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_media_hash_size_unique ON media_files(file_hash, file_size)")


def create_buttons_table(cursor):
    """Create the buttons table for message buttons."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS buttons (
        message_id INTEGER,
        entity_id INTEGER,
        row INTEGER,
        column INTEGER,
        text TEXT,
        data TEXT,
        url TEXT,
        UNIQUE(message_id, entity_id, row, column)
    )""")


def create_replies_table(cursor):
    """Create the replies table for message replies."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS replies (
        message_id INTEGER,
        entity_id INTEGER,
        reply_to_msg_id INTEGER,
        quote_text TEXT,
        UNIQUE(message_id, entity_id)
    )""")


def create_reactions_table(cursor):
    """Create the reactions table for message reactions."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS reactions (
        message_id INTEGER,
        entity_id INTEGER,
        emoji TEXT,
        count INTEGER,
        UNIQUE(message_id, entity_id, emoji)
    )""")


def create_backup_metadata_table(cursor):
    """Create the backup_metadata table for tracking backup state."""
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS backup_metadata (
        key TEXT PRIMARY KEY,
        value TEXT,
        updated_at TEXT
    )""")


def init_database(cursor, conn):
    """Initialize all database tables and indexes."""
    create_messages_table(cursor)
    create_media_files_table(cursor)
    create_buttons_table(cursor)
    create_replies_table(cursor)
    create_reactions_table(cursor)
    create_backup_metadata_table(cursor)
    
    # LOW PRIORITY FIX: Initialize schema version
    init_schema_version(cursor, conn)
    
    # Run migrations first to add any missing columns
    migrate_schema(cursor, conn)
    
    # Then create indexes (in case new columns were added)
    create_media_indexes(cursor)
    
    conn.commit()


def init_schema_version(cursor, conn):
    """Initialize schema version metadata.
    
    LOW PRIORITY FIX: Track schema version for future migrations.
    """
    from telegram_backup.database.media_manager import get_metadata_value, set_metadata_value
    
    current_version = get_metadata_value(cursor, 'schema_version')
    if current_version is None:
        # Set initial schema version
        set_metadata_value(cursor, 'schema_version', '1.0')
        conn.commit()


def check_and_add_column(cursor, table_name, column_name, column_type, default_value=None):
    """Check if column exists and add it if missing.
    
    MEDIUM PRIORITY FIX: Better validation of input parameters.
    """
    # Validate table and column names to prevent SQL injection
    # (even though these are internal calls, it's good practice)
    valid_name_pattern = r'^[a-zA-Z_][a-zA-Z0-9_]*$'
    import re
    
    if not re.match(valid_name_pattern, table_name):
        raise ValueError(f"Invalid table name: {table_name}")
    if not re.match(valid_name_pattern, column_name):
        raise ValueError(f"Invalid column name: {column_name}")
    
    cursor.execute(f"SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    result = cursor.fetchone()
    
    if not result:
        return False
    
    table_schema = result[0]
    
    if column_name not in table_schema:
        # Validate column_type is safe (basic check)
        allowed_types = ['TEXT', 'INTEGER', 'REAL', 'BLOB', 'BOOLEAN']
        column_type_upper = column_type.upper()
        if not any(t in column_type_upper for t in allowed_types):
            raise ValueError(f"Invalid column type: {column_type}")
        
        default_clause = f"DEFAULT {default_value}" if default_value is not None else ""
        # Safe to use f-string here after validation
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type} {default_clause}")
        return True
    
    return False


def migrate_schema(cursor, conn):
    """Update database schema to latest version.
    
    LOW PRIORITY FIX: Track migrations with schema version.
    """
    from telegram_backup.database.media_manager import get_metadata_value, set_metadata_value
    
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='messages'")
    table_schema_result = cursor.fetchone()
    
    if not table_schema_result:
        return  # Table doesn't exist yet
    
    # Get current schema version
    current_version = get_metadata_value(cursor, 'schema_version')
    if current_version is None:
        current_version = '0.0'  # Legacy database without version tracking
    
    table_schema = table_schema_result[0]
    migrations_performed = []
    
    # Add new columns if they don't exist
    if check_and_add_column(cursor, 'messages', 'file_id', 'TEXT'):
        migrations_performed.append('Added file_id column')
    
    if check_and_add_column(cursor, 'messages', 'file_unique_id', 'TEXT'):
        migrations_performed.append('Added file_unique_id column')
    
    if check_and_add_column(cursor, 'messages', 'file_size', 'INTEGER'):
        migrations_performed.append('Added file_size column')
    
    if check_and_add_column(cursor, 'messages', 'media_file_id', 'INTEGER'):
        migrations_performed.append('Added media_file_id column')
    
    if check_and_add_column(cursor, 'messages', 'is_service_message', 'BOOLEAN', '0'):
        migrations_performed.append('Added is_service_message column')
    
    if check_and_add_column(cursor, 'messages', 'is_voice_message', 'BOOLEAN', '0'):
        migrations_performed.append('Added is_voice_message column')
    
    if check_and_add_column(cursor, 'messages', 'is_pinned', 'BOOLEAN', '0'):
        migrations_performed.append('Added is_pinned column')
    
    if check_and_add_column(cursor, 'messages', 'user_id', 'TEXT'):
        migrations_performed.append('Added user_id column')
    
    # Check replies table for quote_text column
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='replies'")
    replies_schema = cursor.fetchone()
    
    if replies_schema and check_and_add_column(cursor, 'replies', 'quote_text', 'TEXT'):
        migrations_performed.append('Added quote_text column to replies')
    
    # Migrate media_files table
    cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='media_files'")
    media_files_schema = cursor.fetchone()
    
    if media_files_schema:
        if check_and_add_column(cursor, 'media_files', 'access_hash', 'TEXT'):
            migrations_performed.append('Added access_hash column to media_files')
        
        if check_and_add_column(cursor, 'media_files', 'mime_type', 'TEXT'):
            migrations_performed.append('Added mime_type column to media_files')
        
        if check_and_add_column(cursor, 'media_files', 'file_name', 'TEXT'):
            migrations_performed.append('Added file_name column to media_files')
        
        if check_and_add_column(cursor, 'media_files', 'file_extension', 'TEXT'):
            migrations_performed.append('Added file_extension column to media_files')
        
        if check_and_add_column(cursor, 'media_files', 'duration', 'INTEGER'):
            migrations_performed.append('Added duration column to media_files')
        
        if check_and_add_column(cursor, 'media_files', 'width', 'INTEGER'):
            migrations_performed.append('Added width column to media_files')
        
        if check_and_add_column(cursor, 'media_files', 'height', 'INTEGER'):
            migrations_performed.append('Added height column to media_files')
        
        # Create new indexes
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_file_id ON media_files(file_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_name ON media_files(file_name)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_size_duration ON media_files(file_size, duration)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_media_resolution ON media_files(width, height)")
            migrations_performed.append('Added new indexes for media search')
        except:
            pass
    
    if migrations_performed:
        print(f"Database schema updated: {', '.join(migrations_performed)}")
        # LOW PRIORITY FIX: Update schema version after migrations
        set_metadata_value(cursor, 'schema_version', '1.1')
        conn.commit()

