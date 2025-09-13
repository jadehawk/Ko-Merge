import asyncio
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Set

logger = logging.getLogger(__name__)


class CleanupService:
    """
    Automated cleanup service that runs periodically to remove old files and maintain system health.
    Handles cleanup of upload files, processed files, and orphaned cover images.
    """

    def __init__(
        self,
        upload_dir: str = "data/uploads",
        processed_dir: str = "data/processed",
        cleanup_interval_minutes: int = 10,
        file_max_age_minutes: int = 60,
    ):
        """
        Initialize the cleanup service.

        Args:
            upload_dir (str): Directory containing uploaded files
            processed_dir (str): Directory containing processed files
            cleanup_interval_minutes (int): How often to run cleanup (default: 10 minutes)
            file_max_age_minutes (int): Maximum age for files before cleanup (default: 60 minutes)
        """
        self.upload_dir = Path(upload_dir)
        self.processed_dir = Path(processed_dir)
        self.cleanup_interval = timedelta(minutes=cleanup_interval_minutes)
        self.file_max_age = timedelta(minutes=file_max_age_minutes)

        # Track active sessions to avoid deleting files in use
        self.active_sessions: Set[str] = set()
        self.cleanup_task = None
        self.running = False

        logger.info(
            f"Cleanup service initialized - interval: {cleanup_interval_minutes}min, max age: {file_max_age_minutes}min"
        )

    def add_active_session(self, session_id: str):
        """
        Mark a session as active to protect its files from cleanup.

        Args:
            session_id (str): Session ID to protect
        """
        self.active_sessions.add(session_id)
        logger.debug(f"Added active session: {session_id}")

    def remove_active_session(self, session_id: str):
        """
        Remove a session from active list, allowing its files to be cleaned up.

        Args:
            session_id (str): Session ID to remove protection from
        """
        self.active_sessions.discard(session_id)
        logger.debug(f"Removed active session: {session_id}")

    def is_file_protected(self, file_path: Path) -> bool:
        """
        Check if a file is protected by an active session.

        Args:
            file_path (Path): Path to the file to check

        Returns:
            bool: True if file is protected, False otherwise
        """
        filename = file_path.name

        # Extract session ID from filename (format: session_id.sqlite3 or session_id_fixed.sqlite3)
        if filename.endswith(".sqlite3"):
            if filename.endswith("_fixed.sqlite3"):
                session_id = filename[:-13]  # Remove '_fixed.sqlite3'
            else:
                session_id = filename[:-8]  # Remove '.sqlite3'

            return session_id in self.active_sessions

        return False

    def cleanup_directory(self, directory: Path, description: str) -> int:
        """
        Clean up old files in a directory, respecting active sessions.

        Args:
            directory (Path): Directory to clean up
            description (str): Description for logging

        Returns:
            int: Number of files deleted
        """
        if not directory.exists():
            return 0

        deleted_count = 0
        now = datetime.now()

        try:
            for file_path in directory.glob("*"):
                if not file_path.is_file():
                    continue

                # Check if file is protected by active session
                if self.is_file_protected(file_path):
                    logger.debug(f"Skipping protected file: {file_path.name}")
                    continue

                # Check file age
                try:
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    file_age = now - file_mtime

                    if file_age > self.file_max_age:
                        file_path.unlink()
                        deleted_count += 1
                        logger.info(
                            f"Deleted old {description} file: {file_path.name} (age: {file_age})"
                        )
                    else:
                        logger.debug(
                            f"Keeping {description} file: {file_path.name} (age: {file_age})"
                        )

                except (OSError, ValueError) as e:
                    logger.error(f"Error processing file {file_path}: {e}")
                    continue

        except Exception as e:
            logger.error(f"Error cleaning up {description} directory {directory}: {e}")

        return deleted_count

    async def run_cleanup_cycle(self):
        """
        Run a single cleanup cycle across all managed directories.
        """
        logger.info("Starting cleanup cycle")
        start_time = datetime.now()

        total_deleted = 0

        # Clean up upload directory
        upload_deleted = self.cleanup_directory(self.upload_dir, "upload")
        total_deleted += upload_deleted

        # Clean up processed directory
        processed_deleted = self.cleanup_directory(self.processed_dir, "processed")
        total_deleted += processed_deleted

        # Clean up orphaned cover files (if cover storage service is available)
        try:
            from .cover_storage import cover_storage_service

            cover_deleted = cover_storage_service.cleanup_orphaned_files()
            total_deleted += cover_deleted
        except ImportError:
            logger.debug("Cover storage service not available for cleanup")
        except Exception as e:
            logger.error(f"Error cleaning up cover files: {e}")

        duration = datetime.now() - start_time

        if total_deleted > 0:
            logger.info(
                f"Cleanup cycle completed: {total_deleted} files deleted in {duration}"
            )
        else:
            logger.debug(f"Cleanup cycle completed: no files deleted in {duration}")

        # Log active sessions for debugging
        if self.active_sessions:
            logger.debug(
                f"Active sessions protecting files: {list(self.active_sessions)}"
            )

    async def start(self):
        """
        Start the periodic cleanup service.
        """
        if self.running:
            logger.warning("Cleanup service is already running")
            return

        self.running = True
        logger.info(f"Starting cleanup service with {self.cleanup_interval} interval")

        try:
            while self.running:
                await self.run_cleanup_cycle()

                # Wait for next cleanup cycle
                await asyncio.sleep(self.cleanup_interval.total_seconds())

        except asyncio.CancelledError:
            logger.info("Cleanup service cancelled")
        except Exception as e:
            logger.error(f"Cleanup service error: {e}")
        finally:
            self.running = False
            logger.info("Cleanup service stopped")

    async def stop(self):
        """
        Stop the cleanup service.
        """
        if not self.running:
            return

        logger.info("Stopping cleanup service")
        self.running = False

        if self.cleanup_task and not self.cleanup_task.done():
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass

    def start_background_task(self):
        """
        Start the cleanup service as a background task.

        Returns:
            asyncio.Task: The background cleanup task
        """
        if self.cleanup_task and not self.cleanup_task.done():
            logger.warning("Cleanup task already running")
            return self.cleanup_task

        self.cleanup_task = asyncio.create_task(self.start())
        logger.info("Started cleanup service as background task")
        return self.cleanup_task

    async def force_cleanup(self):
        """
        Force an immediate cleanup cycle (useful for testing or manual cleanup).
        """
        logger.info("Running forced cleanup cycle")
        await self.run_cleanup_cycle()

    def get_status(self) -> dict:
        """
        Get the current status of the cleanup service.

        Returns:
            dict: Status information
        """
        return {
            "running": self.running,
            "cleanup_interval_minutes": self.cleanup_interval.total_seconds() / 60,
            "file_max_age_minutes": self.file_max_age.total_seconds() / 60,
            "active_sessions": list(self.active_sessions),
            "active_session_count": len(self.active_sessions),
            "upload_dir": str(self.upload_dir),
            "processed_dir": str(self.processed_dir),
            "upload_dir_exists": self.upload_dir.exists(),
            "processed_dir_exists": self.processed_dir.exists(),
        }


# Global instance
cleanup_service = CleanupService()
