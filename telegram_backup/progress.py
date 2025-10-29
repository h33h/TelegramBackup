"""Progress tracking and display for downloads."""

import time
from rich.progress import (
    Progress,
    SpinnerColumn,
    TextColumn,
    BarColumn,
    TaskProgressColumn,
    DownloadColumn,
    TransferSpeedColumn,
    TimeRemainingColumn,
    TaskID
)
from rich.console import Console, Group
from rich.table import Table
from rich.live import Live
from rich.panel import Panel


class DownloadProgress:
    """Track and display download progress with rich."""
    
    def __init__(self, total_messages=0):
        """Initialize progress tracker.
        
        Args:
            total_messages: Total number of messages to process
        """
        self.console = Console()
        
        # Progress bar for overall message processing (no download columns)
        self.main_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold blue]{task.description}"),
            BarColumn()
        )
        
        # Progress bar for individual file downloads (with download columns)
        self.download_progress = Progress(
            SpinnerColumn(),
            TextColumn("[bold cyan]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            DownloadColumn(),
            TransferSpeedColumn()
        )
        
        self.task_id = None
        self.total_messages = total_messages
        self.messages_processed = 0
        
        # Download statistics
        self.total_files_to_download = 0
        self.files_downloaded = 0
        self.files_skipped = 0
        self.bytes_downloaded = 0
        self.bytes_skipped = 0
        
        self.start_time = None
        
        # Active downloads tracking
        self.active_downloads = {}  # {task_id: {'filename': str, 'size': int, 'downloaded': int}}
        self.live = None
    
    def start(self, description="Processing messages"):
        """Start progress display.
        
        Args:
            description: Task description to display
        """
        self.start_time = time.time()
        
        # Use Live to display both progress bars together with Group
        progress_group = Group(
            self.main_progress,
            self.download_progress
        )
        self.live = Live(progress_group, console=self.console, refresh_per_second=10)
        self.live.start()
        
        self.task_id = self.main_progress.add_task(
            description,
            total=self.total_messages if self.total_messages > 0 else None
        )
    
    def stop(self):
        """Stop progress display."""
        if self.live:
            self.live.stop()
    
    def update_message_count(self, processed):
        """Update the count of processed messages.
        
        Args:
            processed: Number of messages processed
        """
        self.messages_processed = processed
        if self.task_id is not None:
            desc = f"Messages: {processed}"
            if self.total_messages > 0:
                desc += f"/{self.total_messages}"
            desc += f" | Downloaded: {self.files_downloaded} | Skipped: {self.files_skipped}"
            self.main_progress.update(self.task_id, completed=processed, description=desc)
    
    def add_file_to_download(self, file_size):
        """Mark a file for download.
        
        Args:
            file_size: Size of file in bytes
        """
        self.total_files_to_download += 1
        self.update_message_count(self.messages_processed)
    
    def start_file_download(self, file_id, filename, total_size):
        """Register a new file download.
        
        Args:
            file_id: Unique identifier for this download
            filename: Name of the file
            total_size: Total size in bytes
            
        Returns:
            task_id for this download
        """
        task_id = self.download_progress.add_task(
            f"⬇ {filename}",
            total=total_size
        )
        self.active_downloads[file_id] = {
            'task_id': task_id,
            'filename': filename,
            'size': total_size,
            'downloaded': 0,
            'start_time': time.time()
        }
        return task_id
    
    def update_file_progress(self, file_id, downloaded):
        """Update progress for a specific file download.
        
        Args:
            file_id: Unique identifier for this download
            downloaded: Bytes downloaded so far
        """
        if file_id in self.active_downloads:
            download_info = self.active_downloads[file_id]
            download_info['downloaded'] = downloaded
            
            # Update progress bar (speed is calculated automatically by TransferSpeedColumn)
            self.download_progress.update(
                download_info['task_id'],
                completed=downloaded
            )
    
    def complete_file_download(self, file_id):
        """Mark a file download as complete.
        
        Args:
            file_id: Unique identifier for this download
        """
        if file_id in self.active_downloads:
            download_info = self.active_downloads[file_id]
            self.download_progress.update(
                download_info['task_id'],
                completed=download_info['size'],
                visible=False
            )
            del self.active_downloads[file_id]
    
    def file_skipped(self, file_size, filename=None):
        """Mark a file as skipped (already exists).
        
        Args:
            file_size: Size of file in bytes
            filename: Optional filename for display
        """
        self.files_skipped += 1
        self.bytes_skipped += file_size
        self.update_message_count(self.messages_processed)
    
    def file_downloaded(self, file_size, filename=None):
        """Mark a file as successfully downloaded.
        
        Args:
            file_size: Size of file in bytes
            filename: Optional filename for display
        """
        self.files_downloaded += 1
        self.bytes_downloaded += file_size
        self.update_message_count(self.messages_processed)
    
    def update_current_file(self, filename):
        """Update the currently processing file.
        
        Args:
            filename: Name of the file being processed
        """
        # This is now handled by start_file_download
        pass
    
    def get_stats(self):
        """Get download statistics.
        
        Returns:
            dict: Statistics about the download session
        """
        elapsed = time.time() - self.start_time if self.start_time else 0
        avg_speed = self.bytes_downloaded / elapsed if elapsed > 0 else 0
        
        return {
            'messages_processed': self.messages_processed,
            'files_downloaded': self.files_downloaded,
            'files_skipped': self.files_skipped,
            'bytes_downloaded': self.bytes_downloaded,
            'bytes_skipped': self.bytes_skipped,
            'elapsed_time': elapsed,
            'avg_speed': avg_speed
        }
    
    def display_summary(self, entity_name=None):
        """Display final summary statistics.
        
        Args:
            entity_name: Optional entity name to include in summary
        """
        stats = self.get_stats()
        
        title = f"Backup Summary: {entity_name}" if entity_name else "Backup Summary"
        table = Table(title=title, show_header=False, border_style="green")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="yellow")
        
        table.add_row("Messages Processed", str(stats['messages_processed']))
        table.add_row("Files Downloaded", str(stats['files_downloaded']))
        table.add_row("Files Skipped (already exist)", str(stats['files_skipped']))
        table.add_row("Data Downloaded", self._format_bytes(stats['bytes_downloaded']))
        table.add_row("Data Saved (skipped)", self._format_bytes(stats['bytes_skipped']))
        table.add_row("Average Speed", f"{self._format_bytes(stats['avg_speed'])}/s")
        table.add_row("Total Time", f"{stats['elapsed_time']:.1f} seconds")
        
        self.console.print()
        self.console.print(table)
        self.console.print()
    
    @staticmethod
    def _format_bytes(size):
        """Format bytes to human-readable string.
        
        Args:
            size: Size in bytes
            
        Returns:
            str: Formatted size (e.g., "1.5 MB")
        """
        for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
            if size < 1024.0:
                return f"{size:.1f} {unit}"
            size /= 1024.0
        return f"{size:.1f} PB"

