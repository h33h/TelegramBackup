"""Download statistics and monitoring for file downloads."""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, List
from datetime import datetime

logger = logging.getLogger('telegram_backup.download_stats')


@dataclass
class DownloadStats:
    """Statistics for tracking download performance and issues."""
    
    # Success metrics
    total_files: int = 0
    successful_downloads: int = 0
    failed_downloads: int = 0
    skipped_files: int = 0
    
    # Size metrics
    total_bytes_downloaded: int = 0
    total_bytes_skipped: int = 0
    
    # Performance metrics
    start_time: float = field(default_factory=time.time)
    total_download_time: float = 0.0
    
    # Error tracking
    errors_by_type: Dict[str, int] = field(default_factory=dict)
    failed_file_ids: List[str] = field(default_factory=list)
    
    # Retry metrics
    total_retries: int = 0
    files_requiring_retry: int = 0
    
    def record_success(self, file_size: int, download_time: float = 0.0):
        """Record a successful download."""
        self.successful_downloads += 1
        self.total_bytes_downloaded += file_size
        self.total_download_time += download_time
    
    def record_failure(self, file_id: str, error_type: str):
        """Record a failed download."""
        self.failed_downloads += 1
        self.failed_file_ids.append(file_id)
        
        # Track error types
        if error_type not in self.errors_by_type:
            self.errors_by_type[error_type] = 0
        self.errors_by_type[error_type] += 1
    
    def record_skip(self, file_size: int):
        """Record a skipped file (already exists)."""
        self.skipped_files += 1
        self.total_bytes_skipped += file_size
    
    def record_retry(self):
        """Record a retry attempt."""
        self.total_retries += 1
    
    def record_file_with_retry(self):
        """Record that a file required retry."""
        self.files_requiring_retry += 1
    
    def get_success_rate(self) -> float:
        """Calculate success rate."""
        total_attempted = self.successful_downloads + self.failed_downloads
        if total_attempted == 0:
            return 0.0
        return (self.successful_downloads / total_attempted) * 100
    
    def get_average_speed(self) -> float:
        """Calculate average download speed in MB/s."""
        if self.total_download_time == 0:
            return 0.0
        return (self.total_bytes_downloaded / (1024 * 1024)) / self.total_download_time
    
    def get_elapsed_time(self) -> float:
        """Get elapsed time since start."""
        return time.time() - self.start_time
    
    def get_summary(self) -> str:
        """Get a formatted summary of statistics."""
        elapsed = self.get_elapsed_time()
        success_rate = self.get_success_rate()
        avg_speed = self.get_average_speed()
        
        summary = [
            "\n" + "="*60,
            "Download Statistics Summary",
            "="*60,
            f"Total files processed: {self.total_files}",
            f"Successful: {self.successful_downloads}",
            f"Failed: {self.failed_downloads}",
            f"Skipped (already exist): {self.skipped_files}",
            f"Success rate: {success_rate:.2f}%",
            "",
            f"Data downloaded: {self.total_bytes_downloaded / (1024**3):.2f} GB",
            f"Data skipped: {self.total_bytes_skipped / (1024**3):.2f} GB",
            f"Average speed: {avg_speed:.2f} MB/s",
            f"Total time: {elapsed:.1f}s",
            "",
            f"Retries: {self.total_retries}",
            f"Files requiring retry: {self.files_requiring_retry}",
        ]
        
        if self.errors_by_type:
            summary.append("")
            summary.append("Errors by type:")
            for error_type, count in sorted(self.errors_by_type.items(), key=lambda x: x[1], reverse=True):
                summary.append(f"  {error_type}: {count}")
        
        if self.failed_file_ids:
            summary.append("")
            summary.append(f"Failed file IDs ({len(self.failed_file_ids)}):")
            for file_id in self.failed_file_ids[:10]:  # Show first 10
                summary.append(f"  {file_id}")
            if len(self.failed_file_ids) > 10:
                summary.append(f"  ... and {len(self.failed_file_ids) - 10} more")
        
        summary.append("="*60)
        
        return "\n".join(summary)
    
    def log_summary(self):
        """Log the statistics summary."""
        logger.info(self.get_summary())

