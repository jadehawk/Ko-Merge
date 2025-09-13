import sqlite3
import hashlib
import aiohttp
import aiofiles
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional, Any, List
import logging

logger = logging.getLogger(__name__)


class CoverStorageService:
    """
    Unified cover storage service that downloads and stores cover images locally.
    Provides consistent behavior for all cover sources (Google Books, OpenLibrary, Amazon).
    """

    def __init__(
        self,
        db_path: str = "data/cover_storage.sqlite3",
        covers_dir: str = "data/covers",
    ):
        """
        Initialize the cover storage service.

        Args:
            db_path (str): Path to the SQLite database for cover metadata
            covers_dir (str): Directory to store downloaded cover images
        """
        self.db_path = Path(db_path)
        self.covers_dir = Path(covers_dir)

        # Ensure directories exist
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.covers_dir.mkdir(parents=True, exist_ok=True)

        self._init_database()
        self.session = None

    async def get_session(self):
        """Get or create aiohttp session for downloading images."""
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        """Close aiohttp session."""
        if self.session:
            await self.session.close()

    def _init_database(self):
        """Initialize the database with required tables for cover storage."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Cover images table - stores metadata about downloaded covers
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS cover_images (
                    book_hash TEXT PRIMARY KEY,        -- SHA256 of "title|author" (no MD5)
                    image_hash TEXT UNIQUE NOT NULL,   -- SHA256 of image content
                    local_path TEXT NOT NULL,          -- Relative path to stored image file
                    original_source TEXT NOT NULL,     -- google_books/openlibrary/amazon
                    original_url TEXT NOT NULL,        -- Original URL for reference
                    file_size INTEGER NOT NULL,        -- File size in bytes
                    image_format TEXT NOT NULL,        -- jpg/png/webp etc.
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    title TEXT NOT NULL,               -- For human readability
                    author TEXT NOT NULL               -- For human readability
                )
            """)

            # Create indexes for better performance
            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cover_images_title_author 
                ON cover_images(title, author)
            """)

            cursor.execute("""
                CREATE INDEX IF NOT EXISTS idx_cover_images_source 
                ON cover_images(original_source)
            """)

            conn.commit()
            logger.info("Cover storage database initialized")

    def generate_book_hash(self, title: str, author: str = "") -> str:
        """
        Generate a unique hash for book identification based on title + author only.
        Does NOT include MD5 hash from KOReader database.

        Args:
            title (str): Book title
            author (str): Book author

        Returns:
            str: SHA256 hash of normalized "title|author"
        """
        # Normalize strings for consistent hashing
        title_norm = title.lower().strip() if title else ""
        author_norm = author.lower().strip() if author else ""

        key_string = f"{title_norm}|{author_norm}"
        return hashlib.sha256(key_string.encode()).hexdigest()

    def generate_image_hash(self, image_data: bytes) -> str:
        """
        Generate a unique hash for image content to avoid storing duplicates.

        Args:
            image_data (bytes): Raw image data

        Returns:
            str: SHA256 hash of image content
        """
        return hashlib.sha256(image_data).hexdigest()

    async def download_and_store_cover(
        self, title: str, author: str, cover_url: str, source: str
    ) -> Optional[str]:
        """
        Download a cover image from URL and store it locally.

        Args:
            title (str): Book title
            author (str): Book author
            cover_url (str): URL of the cover image to download
            source (str): Source of the cover (google_books/openlibrary/amazon)

        Returns:
            Optional[str]: Local image hash if successful, None if failed
        """
        try:
            # Generate book hash for identification
            book_hash = self.generate_book_hash(title, author)

            # Check if we already have a cover for this book
            existing_cover = self.get_stored_cover(book_hash)
            if existing_cover:
                logger.info(f"Cover already exists for '{title}' by '{author}'")
                return existing_cover["image_hash"]

            # Download the image
            session = await self.get_session()
            async with session.get(cover_url) as response:
                if response.status != 200:
                    logger.error(
                        f"Failed to download cover from {cover_url}: HTTP {response.status}"
                    )
                    return None

                image_data = await response.read()

                if not image_data:
                    logger.error(f"Empty image data from {cover_url}")
                    return None

                # Generate image hash
                image_hash = self.generate_image_hash(image_data)

                # Determine file format from content type or URL
                content_type = response.headers.get("content-type", "").lower()
                if "jpeg" in content_type or "jpg" in content_type:
                    file_ext = "jpg"
                elif "png" in content_type:
                    file_ext = "png"
                elif "webp" in content_type:
                    file_ext = "webp"
                else:
                    # Fallback to URL extension or default to jpg
                    file_ext = (
                        cover_url.split(".")[-1].lower() if "." in cover_url else "jpg"
                    )
                    if file_ext not in ["jpg", "jpeg", "png", "webp", "gif"]:
                        file_ext = "jpg"

                # Create local file path
                local_filename = f"{image_hash}.{file_ext}"
                local_path = self.covers_dir / local_filename

                # Save image to disk
                async with aiofiles.open(local_path, "wb") as f:
                    await f.write(image_data)

                # Save metadata to database
                with sqlite3.connect(self.db_path) as conn:
                    cursor = conn.cursor()
                    cursor.execute(
                        """
                        INSERT OR REPLACE INTO cover_images 
                        (book_hash, image_hash, local_path, original_source, original_url, 
                         file_size, image_format, title, author, created_at)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                        (
                            book_hash,
                            image_hash,
                            local_filename,  # Store relative path
                            source,
                            cover_url,
                            len(image_data),
                            file_ext,
                            title,
                            author,
                            datetime.now(),
                        ),
                    )
                    conn.commit()

                logger.info(
                    f"Successfully stored cover for '{title}' by '{author}' from {source}"
                )
                return image_hash

        except Exception as e:
            logger.error(
                f"Error downloading and storing cover from {cover_url}: {str(e)}"
            )
            return None

    def get_stored_cover(self, book_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get stored cover information for a book.

        Args:
            book_hash (str): Book hash generated from title + author

        Returns:
            Optional[Dict[str, Any]]: Cover information or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT book_hash, image_hash, local_path, original_source, original_url,
                           file_size, image_format, title, author, created_at
                    FROM cover_images 
                    WHERE book_hash = ?
                """,
                    (book_hash,),
                )

                result = cursor.fetchone()
                if result:
                    return {
                        "book_hash": result[0],
                        "image_hash": result[1],
                        "local_path": result[2],
                        "original_source": result[3],
                        "original_url": result[4],
                        "file_size": result[5],
                        "image_format": result[6],
                        "title": result[7],
                        "author": result[8],
                        "created_at": result[9],
                    }
                return None
        except Exception as e:
            logger.error(f"Error getting stored cover: {str(e)}")
            return None

    def get_batch_stored_covers(
        self, book_list: List[Dict[str, str]]
    ) -> Dict[str, Dict[str, Any]]:
        """
        Get stored covers for multiple books in a single database query.

        Args:
            book_list (List[Dict[str, str]]): List of books with 'title' and 'author' keys

        Returns:
            Dict[str, Dict[str, Any]]: Dictionary mapping book_hash to cover information
        """
        try:
            # Generate book hashes for all books
            book_hashes = []
            hash_to_book = {}

            for book in book_list:
                title = book.get("title", "")
                author = book.get("author", "")
                book_hash = self.generate_book_hash(title, author)
                book_hashes.append(book_hash)
                hash_to_book[book_hash] = {"title": title, "author": author}

            if not book_hashes:
                return {}

            # Query database for all book hashes
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                placeholders = ",".join(["?" for _ in book_hashes])
                cursor.execute(
                    f"""
                    SELECT book_hash, image_hash, local_path, original_source, original_url,
                           file_size, image_format, title, author, created_at
                    FROM cover_images 
                    WHERE book_hash IN ({placeholders})
                """,
                    book_hashes,
                )

                results = {}
                for row in cursor.fetchall():
                    book_hash = row[0]
                    results[book_hash] = {
                        "book_hash": row[0],
                        "image_hash": row[1],
                        "local_path": row[2],
                        "original_source": row[3],
                        "original_url": row[4],
                        "file_size": row[5],
                        "image_format": row[6],
                        "title": row[7],
                        "author": row[8],
                        "created_at": row[9],
                    }

                logger.info(
                    f"Found {len(results)} stored covers out of {len(book_hashes)} requested"
                )
                return results

        except Exception as e:
            logger.error(f"Error getting batch stored covers: {str(e)}")
            return {}

    def get_cover_file_path(self, image_hash: str) -> Optional[Path]:
        """
        Get the full file path for a stored cover image.

        Args:
            image_hash (str): Image hash

        Returns:
            Optional[Path]: Full path to image file or None if not found
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    """
                    SELECT local_path FROM cover_images WHERE image_hash = ?
                """,
                    (image_hash,),
                )

                result = cursor.fetchone()
                if result:
                    local_path = result[0]
                    full_path = self.covers_dir / local_path

                    # Verify file exists
                    if full_path.exists():
                        return full_path
                    else:
                        logger.warning(f"Cover file not found: {full_path}")
                        return None

                return None
        except Exception as e:
            logger.error(f"Error getting cover file path: {str(e)}")
            return None

    def delete_stored_cover(self, book_hash: str) -> bool:
        """
        Delete a stored cover image and its metadata.

        Args:
            book_hash (str): Book hash

        Returns:
            bool: True if deleted successfully, False otherwise
        """
        try:
            # Get cover info first
            cover_info = self.get_stored_cover(book_hash)
            if not cover_info:
                logger.warning(f"No stored cover found for book_hash: {book_hash}")
                return False

            # Delete file from disk
            file_path = self.covers_dir / cover_info["local_path"]
            if file_path.exists():
                file_path.unlink()
                logger.info(f"Deleted cover file: {file_path}")

            # Delete from database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(
                    "DELETE FROM cover_images WHERE book_hash = ?", (book_hash,)
                )
                conn.commit()

                if cursor.rowcount > 0:
                    logger.info(f"Deleted cover metadata for book_hash: {book_hash}")
                    return True
                else:
                    logger.warning(
                        f"No database record deleted for book_hash: {book_hash}"
                    )
                    return False

        except Exception as e:
            logger.error(f"Error deleting stored cover: {str(e)}")
            return False

    def cleanup_orphaned_files(self) -> int:
        """
        Clean up orphaned image files that have no database record.

        Returns:
            int: Number of files cleaned up
        """
        try:
            # Get all image hashes from database
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT image_hash, local_path FROM cover_images")
                db_files = {row[1] for row in cursor.fetchall()}

            # Get all files in covers directory
            disk_files = set()
            for file_path in self.covers_dir.glob("*"):
                if file_path.is_file():
                    disk_files.add(file_path.name)

            # Find orphaned files
            orphaned_files = disk_files - db_files

            # Delete orphaned files
            deleted_count = 0
            for filename in orphaned_files:
                file_path = self.covers_dir / filename
                try:
                    file_path.unlink()
                    deleted_count += 1
                    logger.info(f"Deleted orphaned file: {filename}")
                except Exception as e:
                    logger.error(f"Error deleting orphaned file {filename}: {e}")

            if deleted_count > 0:
                logger.info(f"Cleaned up {deleted_count} orphaned cover files")

            return deleted_count

        except Exception as e:
            logger.error(f"Error during cleanup: {str(e)}")
            return 0

    def get_storage_stats(self) -> Dict[str, Any]:
        """
        Get statistics about stored covers.

        Returns:
            Dict[str, Any]: Storage statistics
        """
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()

                # Total covers
                cursor.execute("SELECT COUNT(*) FROM cover_images")
                total_covers = cursor.fetchone()[0]

                # Total file size
                cursor.execute("SELECT SUM(file_size) FROM cover_images")
                total_size = cursor.fetchone()[0] or 0

                # Covers by source
                cursor.execute("""
                    SELECT original_source, COUNT(*) 
                    FROM cover_images 
                    GROUP BY original_source
                """)
                by_source = dict(cursor.fetchall())

                # Recent covers (last 7 days)
                cursor.execute("""
                    SELECT COUNT(*) FROM cover_images 
                    WHERE created_at >= datetime('now', '-7 days')
                """)
                recent_covers = cursor.fetchone()[0]

                return {
                    "total_covers": total_covers,
                    "total_size_bytes": total_size,
                    "total_size_mb": round(total_size / (1024 * 1024), 2),
                    "by_source": by_source,
                    "recent_covers": recent_covers,
                }

        except Exception as e:
            logger.error(f"Error getting storage stats: {str(e)}")
            return {
                "total_covers": 0,
                "total_size_bytes": 0,
                "total_size_mb": 0,
                "by_source": {},
                "recent_covers": 0,
            }


# Global instance
cover_storage_service = CoverStorageService()
