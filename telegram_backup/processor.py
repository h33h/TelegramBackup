"""Entity processing - backup and update operations."""

import os
import sqlite3
import asyncio
import datetime
import shutil  # HIGH PRIORITY FIX: for disk space check
from telethon import errors
from telethon.tl.types import ChannelForbidden

from telegram_backup.utils import sanitize_filename, extract_file_identifiers, get_backup_dir
from telegram_backup.config import (
    MAX_CONCURRENT_DOWNLOADS, 
    DOWNLOAD_BATCH_SIZE, 
    DOWNLOAD_BATCH_SIZE_BYTES,
    BACKUP_DIR
)
from telegram_backup.database.schema import init_database, migrate_schema
from telegram_backup.database.operations import save_message_to_db, get_last_message_id
from telegram_backup.database.media_manager import (
    index_existing_media, 
    migrate_legacy_media_data,
    find_or_create_media_file,
    save_media_file
)
from telegram_backup.telegram_api.messages import process_service_message, get_total_message_count
from telegram_backup.telegram_api.media import download_media_batch


def check_disk_space(path, required_bytes):
    """Check if there's enough disk space available.
    
    HIGH PRIORITY FIX: Prevent disk full errors during download.
    
    Args:
        path: Path to check (any path on the target filesystem)
        required_bytes: Minimum required space in bytes
    
    Returns:
        tuple: (has_space: bool, available_bytes: int)
    """
    try:
        stat = shutil.disk_usage(path)
        available = stat.free
        # Keep 500MB safety margin
        safety_margin = 500 * 1024 * 1024
        has_space = available > (required_bytes + safety_margin)
        return has_space, available
    except Exception as e:
        # If we can't check, assume we have space (don't block downloads)
        print(f"Warning: Cannot check disk space: {e}")
        return True, 0


async def process_entity(client, entity_id, entity_name, entity, limit=None, download_media=False, cleanup_orphaned=True):
    """Process an entity - download all messages and optionally media.
    
    Args:
        client: TelegramClient instance
        entity_id: Entity ID
        entity_name: Entity display name
        entity: Entity object
        limit: Maximum number of messages to retrieve (None for all)
        download_media: Whether to download media files
    """
    from telegram_backup.progress import DownloadProgress
    from rich.console import Console
    
    console = Console()
    console.print(f"\n[bold green]Processing:[/bold green] {entity_name} (ID: {entity_id})")
    
    if isinstance(entity, ChannelForbidden):
        console.print(f"[red]The entity {entity_name} (ID: {entity_id}) is not accessible.[/red]")
        return

    # Get entity-specific backup directory
    entity_backup_dir = get_backup_dir(entity_id, entity_name)
    os.makedirs(entity_backup_dir, exist_ok=True)
    
    sanitized_name = sanitize_filename(f"{entity_id}_{entity_name}")
    db_name = os.path.join(entity_backup_dir, "backup.db")
    
    # CRITICAL FIX: Use context manager for database connection
    # This ensures connection is properly closed even if exceptions occur
    with sqlite3.connect(db_name) as conn:
        cursor = conn.cursor()
        
        # Initialize database
        init_database(cursor, conn)
        
        # Index existing media files before starting backup
        if download_media:
            media_dir = os.path.join(entity_backup_dir, "media")
            console.print("[cyan]Indexing existing media files...[/cyan]")
            index_existing_media(cursor, entity_id, conn, media_dir)
            migrate_legacy_media_data(cursor, entity_id, conn)
    
        extraction_time = datetime.datetime.now(datetime.timezone.utc).isoformat()
        
        # Get total message count from the entity
        console.print("[cyan]Getting total message count...[/cyan]")
        total_count = await get_total_message_count(client, entity)
        
        # Determine effective total to display
        if limit is None:
            # No limit specified - show actual total from channel
            effective_total = total_count
        else:
            # Limit specified - show the minimum of limit and actual total
            effective_total = min(limit, total_count) if total_count > 0 else limit
        
        # Create progress tracker with effective total
        progress = DownloadProgress(total_messages=effective_total)
        progress.start(f"Processing {entity_name}")
        
        # Create semaphore for parallel downloads
        download_semaphore = asyncio.Semaphore(MAX_CONCURRENT_DOWNLOADS)
        
        # Batch collection for parallel downloads
        media_download_batch = []
        messages_processed = 0

        try:
            async for message in client.iter_messages(entity, limit=limit):
                messages_processed += 1
                progress.update_message_count(messages_processed)
                
                message_dict = message.to_dict()
                id = message_dict["id"]
                text = message_dict.get("message", None)
                media_type = None
                file_id = None
                file_unique_id = None
                file_size = None
                is_service_message = False
                
                # Handle service messages
                service_text, is_service = await process_service_message(message, client)
                if is_service:
                    text = service_text
                    is_service_message = True
                
                # Handle media
                if message.media:
                    media_type = message_dict["media"]["_"]
                    
                    # Extract file identifiers
                    file_id, access_hash, file_size = extract_file_identifiers(message.media)
                    
                    if download_media:
                        # Check if media already exists WITHOUT downloading
                        media_dir = os.path.join(entity_backup_dir, "media")
                        media_file_id, file_path, needs_download = await find_or_create_media_file(
                            cursor, conn, file_id, file_size, message.media, media_type, access_hash, media_dir
                        )
                        
                        if not needs_download:
                            # Media already exists - save message and skip download
                            progress.file_skipped(file_size, os.path.basename(file_path) if file_path else None)
                            await save_message_to_db(
                                cursor, entity_id, message, extraction_time,
                                media_file_id=media_file_id,
                                file_id=file_id, file_unique_id=access_hash, file_size=file_size
                            )
                            conn.commit()  # Commit immediately
                            continue
                        else:
                            # Need to download - add to batch
                            progress.add_file_to_download(file_size or 0)
                            media_download_batch.append((message, id, file_id, access_hash, file_size, media_type, file_path))
                        
                        # Calculate current batch size in bytes
                        current_batch_size = sum(fsize or 0 for _, _, _, _, fsize, _, _ in media_download_batch)
                        
                        # Process batch if it reaches threshold (by count OR by size)
                        if len(media_download_batch) >= DOWNLOAD_BATCH_SIZE or current_batch_size >= DOWNLOAD_BATCH_SIZE_BYTES:
                            # HIGH PRIORITY FIX: Check disk space before batch download
                            total_batch_size = sum(fsize or 0 for _, _, _, _, fsize, _, _ in media_download_batch)
                            has_space, available = check_disk_space(entity_backup_dir, total_batch_size)
                            
                            if not has_space:
                                console.print(f"[red]Insufficient disk space![/red]")
                                console.print(f"Required: {total_batch_size / (1024**3):.2f} GB")
                                console.print(f"Available: {available / (1024**3):.2f} GB")
                                console.print("[yellow]Stopping download to prevent disk full error[/yellow]")
                                break
                            
                            media_dir = os.path.join(entity_backup_dir, "media")
                            download_results = await download_media_batch(
                                client, [(m, mid) for m, mid, *_ in media_download_batch], 
                                media_dir, download_semaphore, progress
                            )
                            
                            # Save EACH message immediately after download
                            for msg, msg_id, fid, ahash, fsize, mtype, fpath in media_download_batch:
                                media_file, media_hash, mime_type = download_results.get(msg_id, (None, None, None))
                                
                                # Save media file to media_files table
                                media_file_id = None
                                if media_file and os.path.exists(media_file):
                                    media_file_id = await save_media_file(
                                        cursor, media_file, media_hash, fsize, fid, ahash, mtype, mime_type,
                                        entity_backup_dir=entity_backup_dir
                                    )
                                
                                # Save message
                                await save_message_to_db(
                                    cursor, entity_id, msg, extraction_time,
                                    media_file_id=media_file_id,
                                    file_id=fid, file_unique_id=ahash, file_size=fsize
                                )
                                
                                # IMMEDIATE commit after each file
                                conn.commit()
                            
                            # Clear batch
                            media_download_batch = []
                        
                        # Skip to next message since we're batching
                        continue
                
                # For messages without media, save immediately
                await save_message_to_db(
                    cursor, entity_id, message, extraction_time,
                    media_file_id=None,
                    file_id=file_id if 'file_id' in locals() else None,
                    file_unique_id=access_hash if 'access_hash' in locals() else None,
                    file_size=file_size if 'file_size' in locals() else None
                )
                conn.commit()
            
            # Process any remaining items in batch
            if media_download_batch:
                media_dir = os.path.join(entity_backup_dir, "media")
                download_results = await download_media_batch(
                    client, [(m, mid) for m, mid, *_ in media_download_batch],
                    media_dir, download_semaphore, progress
                )
                
                for msg, msg_id, fid, ahash, fsize, mtype, fpath in media_download_batch:
                    media_file, media_hash, mime_type = download_results.get(msg_id, (None, None, None))
                    
                    # Save media file to media_files table
                    media_file_id = None
                    if media_file and os.path.exists(media_file):
                        media_file_id = await save_media_file(
                            cursor, media_file, media_hash, fsize, fid, ahash, mtype, mime_type,
                            entity_backup_dir=entity_backup_dir
                        )
                    
                    # Save message
                    await save_message_to_db(
                        cursor, entity_id, msg, extraction_time,
                        media_file_id=media_file_id,
                        file_id=fid, file_unique_id=ahash, file_size=fsize
                    )
                    
                    # IMMEDIATE commit after each file
                    conn.commit()
            
            # Stop progress and show summary
            progress.stop()
            progress.display_summary(entity_name)
            
        except errors.FloodWaitError as e:
            progress.stop()
            console.print(f'[red]A flood error occurred. Waiting {e.seconds} seconds before continuing.[/red]')
            await asyncio.sleep(e.seconds)
        except errors.ChannelPrivateError:
            progress.stop()
            console.print(f"[red]Cannot access entity {entity_name} (ID: {entity_id})[/red]")
        except KeyboardInterrupt:
            progress.stop()
            progress.display_summary(entity_name)
            console.print("\n[yellow]Interrupted by user[/yellow]")
            console.print("[cyan]Saving progress to database...[/cyan]")
            # Final commit to save all progress
            try:
                conn.commit()
                console.print("[green]✓ Progress saved successfully[/green]")
            except Exception as e:
                console.print(f"[red]Failed to save progress: {e}[/red]")
            raise
        except asyncio.CancelledError:
            progress.stop()
            progress.display_summary(entity_name)
            console.print("\n[yellow]Download cancelled[/yellow]")
            console.print("[cyan]Saving progress to database...[/cyan]")
            # Final commit to save all progress
            try:
                conn.commit()
                console.print("[green]✓ Progress saved successfully[/green]")
            except Exception as e:
                console.print(f"[red]Failed to save progress: {e}[/red]")
            raise
        finally:
            # Cleanup orphaned files if requested
            if cleanup_orphaned and download_media:
                from telegram_backup.database.media_manager import cleanup_orphaned_files, cleanup_unused_media_files
                media_dir = os.path.join(entity_backup_dir, "media")
                cleanup_orphaned_files(cursor, conn, media_dir)
                cleanup_unused_media_files(cursor, conn, media_dir)


