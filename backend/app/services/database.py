import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional, Any
import logging

logger = logging.getLogger(__name__)


class DatabaseService:
    def __init__(self, db_path: str = "data/preferences.sqlite3"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_database()

    def _init_database(self):
        """Initialize the database with required tables"""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Cover preferences table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cover_preferences (
                    book_key TEXT PRIMARY KEY,
                    cover_url TEXT NOT NULL,
                    selected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT,
                    author TEXT
                )
            """)

            # Book metadata cache table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS book_metadata_cache (
                    book_key TEXT PRIMARY KEY,
                    source TEXT NOT NULL,
                    data TEXT NOT NULL,  -- JSON data
                    cached_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP NOT NULL
                )
            """)

            # Download counter table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS download_counter (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    count INTEGER NOT NULL DEFAULT 0,
                    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)

            # Initialize counter if it doesn't exist
            cursor.execute("""
                INSERT OR IGNORE INTO download_counter (id, count) VALUES (1, 0)
            """)

            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cover_preferences_title_author 
                ON cover_preferences(title, author)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_metadata_cache_expires 
                ON book_metadata_cache(expires_at)
            """)

            conn.commit()

    def save_cover_preference(
        self, book_key: str, cover_url: str, title: str = "", author: str = ""
    ):
        """Save user's cover preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO cover_preferences 
                    (book_key, cover_url, title, author, selected_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (book_key, cover_url, title, author, datetime.now()),
                )
                conn.commit()
                logger.info(f"Saved cover preference for book_key: {book_key}")
        except Exception as e:
            logger.error(f"Error saving cover preference: {str(e)}")

    def get_cover_preference(self, book_key: str) -> Optional[str]:
        """Get user's saved cover preference"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT cover_url FROM cover_preferences WHERE book_key = ?
                """,
                    (book_key,),
                )
                result = cursor.fetchone()
                return result[0] if result else None
        except Exception as e:
            logger.error(f"Error getting cover preference: {str(e)}")
            return None

    def cache_book_metadata(
        self, book_key: str, source: str, data: Dict[str, Any], cache_hours: int = 24
    ):
        """Cache book metadata with expiration"""
        try:
            expires_at = datetime.now() + timedelta(hours=cache_hours)
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    INSERT OR REPLACE INTO book_metadata_cache 
                    (book_key, source, data, cached_at, expires_at)
                    VALUES (?, ?, ?, ?, ?)
                """,
                    (book_key, source, json.dumps(data), datetime.now(), expires_at),
                )
                conn.commit()
                logger.info(
                    f"Cached metadata for book_key: {book_key}, source: {source}"
                )
        except Exception as e:
            logger.error(f"Error caching book metadata: {str(e)}")

    def get_cached_book_metadata(
        self, book_key: str, source: str
    ) -> Optional[Dict[str, Any]]:
        """Get cached book metadata if not expired"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT data FROM book_metadata_cache 
                    WHERE book_key = ? AND source = ? AND expires_at > ?
                """,
                    (book_key, source, datetime.now()),
                )
                result = cursor.fetchone()
                if result:
                    return json.loads(result[0])
                return None
        except Exception as e:
            logger.error(f"Error getting cached metadata: {str(e)}")
            return None

    def cleanup_expired_cache(self):
        """Remove expired cache entries"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    DELETE FROM book_metadata_cache WHERE expires_at <= ?
                """,
                    (datetime.now(),),
                )
                deleted_count = cursor.rowcount
                conn.commit()
                if deleted_count > 0:
                    logger.info(f"Cleaned up {deleted_count} expired cache entries")
        except Exception as e:
            logger.error(f"Error cleaning up cache: {str(e)}")

    def get_cover_preferences_stats(self) -> Dict[str, int]:
        """Get statistics about saved cover preferences"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT COUNT(*) FROM cover_preferences")
                total_preferences = cursor.fetchone()[0]

                cursor.execute("""
                    SELECT COUNT(*) FROM cover_preferences 
                    WHERE selected_at >= datetime('now', '-30 days')
                """)
                recent_preferences = cursor.fetchone()[0]

                return {
                    "total_preferences": total_preferences,
                    "recent_preferences": recent_preferences,
                }
        except Exception as e:
            logger.error(f"Error getting preferences stats: {str(e)}")
            return {"total_preferences": 0, "recent_preferences": 0}

    def get_download_count(self) -> int:
        """Get the current download counter"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT count FROM download_counter WHERE id = 1")
                result = cursor.fetchone()
                return result[0] if result else 0
        except Exception as e:
            logger.error(f"Error getting download count: {str(e)}")
            return 0

    def increment_download_count(self) -> int:
        """Increment the download counter and return the new count"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    UPDATE download_counter 
                    SET count = count + 1, last_updated = ? 
                    WHERE id = 1
                """,
                    (datetime.now(),),
                )

                cursor.execute("SELECT count FROM download_counter WHERE id = 1")
                result = cursor.fetchone()
                new_count = result[0] if result else 0

                conn.commit()
                logger.info(f"Download counter incremented to: {new_count}")
                return new_count
        except Exception as e:
            logger.error(f"Error incrementing download count: {str(e)}")
            return self.get_download_count()


# Global instance
database_service = DatabaseService()
