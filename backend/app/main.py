from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from contextlib import asynccontextmanager
import sqlite3
import uuid
import shutil
from datetime import datetime, timedelta
from pathlib import Path
import aiofiles
from typing import List, Dict, Any
import logging
import uvicorn
import sys
import asyncio
import os
from dotenv import load_dotenv

# Fix for Windows + Python 3.13 compatibility with Playwright
# This must be set at module import time to ensure it applies to all event loops
if sys.platform == "win32" and sys.version_info >= (3, 13):
    # Use WindowsProactorEventLoopPolicy for Python 3.13+ on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
    # Also set it for the current thread if there's already a loop
    try:
        loop = asyncio.get_running_loop()
        if not isinstance(loop, asyncio.ProactorEventLoop):
            # If we're already in a loop that's not ProactorEventLoop, we need to handle this
            print(
                "⚠️  Warning: Event loop already running, Playwright may still have issues"
            )
    except RuntimeError:
        # No loop running yet, which is fine
        pass

# Import our services

# Load environment variables
load_dotenv()


# Flexible deployment configuration with smart defaults and input validation
def get_deployment_config():
    """
    Get deployment configuration from environment variables with smart defaults.
    Handles user input validation and normalization.
    """
    # Get raw environment variables
    base_url = os.getenv("PUBLIC_BASE_URL", "").strip()
    subfolder_path = os.getenv("PUBLIC_SUBFOLDER_PATH", "").strip()
    use_subfolder = os.getenv("USE_SUBFOLDER", "false").lower() == "true"

    # Legacy fallback for DEPLOYMENT_PATH
    if not subfolder_path and not use_subfolder:
        legacy_path = os.getenv("DEPLOYMENT_PATH", "").strip()
        if legacy_path and legacy_path != "/":
            subfolder_path = legacy_path
            use_subfolder = True

    # Normalize subfolder path
    if subfolder_path:
        # Add leading slash if missing
        if not subfolder_path.startswith("/"):
            subfolder_path = "/" + subfolder_path
        # Remove trailing slash
        subfolder_path = subfolder_path.rstrip("/")
        # If it becomes just "/", treat as root deployment
        if subfolder_path == "/":
            subfolder_path = ""
            use_subfolder = False

    # Normalize base URL
    if base_url:
        # Add protocol if missing
        if not base_url.startswith(("http://", "https://")):
            # Smart protocol detection
            if (
                "localhost" in base_url
                or "127.0.0.1" in base_url
                or ":80" in base_url
                or base_url.startswith("192.168.")
                or base_url.startswith("10.")
                or base_url.startswith("172.")
            ):
                base_url = "http://" + base_url
            else:
                base_url = "https://" + base_url
        # Remove trailing slash
        base_url = base_url.rstrip("/")
    else:
        # Default for development
        base_url = "http://localhost:8000"

    # Determine root_path for FastAPI
    root_path = subfolder_path if use_subfolder else ""

    # Build CORS origins
    cors_origins = [
        "http://localhost:5173",  # Development frontend
        "http://localhost:8000",  # Local production
    ]

    if base_url and base_url not in cors_origins:
        cors_origins.append(base_url)

    config = {
        "base_url": base_url,
        "subfolder_path": subfolder_path,
        "use_subfolder": use_subfolder,
        "root_path": root_path,
        "cors_origins": cors_origins,
    }

    # Log configuration for debugging
    logger.info("=== Deployment Configuration ===")
    logger.info(f"Base URL: {config['base_url']}")
    logger.info(f"Subfolder Path: {config['subfolder_path'] or '(root deployment)'}")
    logger.info(f"Use Subfolder: {config['use_subfolder']}")
    logger.info(f"FastAPI Root Path: {config['root_path'] or '(none)'}")
    logger.info(f"CORS Origins: {config['cors_origins']}")
    logger.info("================================")

    return config


# Configure logging first (needed by deployment config)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Get deployment configuration
DEPLOYMENT_CONFIG = get_deployment_config()

# Import our services (after load_dotenv to ensure env vars are available)
try:
    logger.info("Importing database service...")
    from .services.database import database_service

    logger.info("Database service imported successfully")

    logger.info("Importing book_metadata service...")
    from .services.book_metadata import book_metadata_service

    logger.info("Book metadata service imported successfully")

    logger.info("Importing cover_storage service...")
    from .services.cover_storage import cover_storage_service

    logger.info("Cover storage service imported successfully")

    logger.info("Importing cleanup service...")
    from .services.cleanup_service import cleanup_service

    logger.info("Cleanup service imported successfully")

    # Initialize services
    logger.info("All services imported successfully")
    logger.info(f"book_metadata_service: {book_metadata_service}")
    logger.info(f"database_service: {database_service}")
    logger.info(f"cover_storage_service: {cover_storage_service}")
    logger.info(f"cleanup_service: {cleanup_service}")

except ImportError as e:
    # Services not available - will create inline implementations
    logger.error(f"Failed to import services: {e}")
    import traceback

    logger.error(f"Full traceback: {traceback.format_exc()}")
    book_metadata_service = None
    database_service = None
    cover_storage_service = None
    cleanup_service = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    cleanup_old_files()

    # Start cleanup service if available
    if cleanup_service:
        cleanup_service.start_background_task()
        logger.info("Started automated cleanup service")

    yield

    # Shutdown
    if cleanup_service:
        await cleanup_service.stop()
        logger.info("Stopped cleanup service")

    if cover_storage_service:
        await cover_storage_service.close()
        logger.info("Closed cover storage service")


app = FastAPI(
    title="Ko-Merge API",
    description="KOReader Statistics Database Merger API",
    version="2.0.0",
    lifespan=lifespan,
    root_path=DEPLOYMENT_CONFIG["root_path"],  # Dynamic root path from environment
)

# CORS middleware for frontend communication - uses dynamic origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=DEPLOYMENT_CONFIG[
        "cors_origins"
    ],  # Dynamic CORS origins from environment
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files (frontend build)
static_dir = os.environ.get("STATIC_FILES_DIR", "/app/static")
if os.path.exists(static_dir):
    app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Configuration
BASE_DIR = Path(__file__).parent.parent
DATA_DIR = BASE_DIR / "data"
UPLOAD_FOLDER = DATA_DIR / "uploads"
PROCESSED_FOLDER = DATA_DIR / "processed"
COUNTER_FILE = DATA_DIR / "download_count.txt"

# Session persistence configuration - 2 hours for better user experience
CLEANUP_AGE = timedelta(hours=2)  # Files cleaned up after 2 hours
SESSION_TIMEOUT = timedelta(hours=2)  # Sessions expire after 2 hours of inactivity

# Ensure directories exist
for path in (DATA_DIR, UPLOAD_FOLDER, PROCESSED_FOLDER):
    path.mkdir(parents=True, exist_ok=True)

# Enhanced session storage with persistence support
# In production, consider using Redis or database for better scalability
sessions: Dict[str, Dict[str, Any]] = {}


def get_download_count() -> int:
    """Get the download counter from database."""
    if database_service:
        return database_service.get_download_count()
    return 0


def increment_download_count() -> int:
    """Increment the download counter and return the new count."""
    if database_service:
        return database_service.increment_download_count()
    return 0


def cleanup_old_files():
    """Remove old files based on CLEANUP_AGE."""
    now = datetime.now()
    for folder in (UPLOAD_FOLDER, PROCESSED_FOLDER):
        for file_path in folder.glob("*"):
            if file_path.is_file():
                mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                if now - mtime > CLEANUP_AGE:
                    file_path.unlink()


def validate_db(path: Path) -> None:
    """Raise ValueError if schema isn't a KOReader stats DB."""
    con = sqlite3.connect(path)
    cur = con.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = {r[0] for r in cur.fetchall()}
    required = {"book", "page_stat_data"}
    if not required.issubset(tables):
        con.close()
        raise ValueError(f"Missing tables: {required - tables}")

    # Quick column check
    cur.execute("PRAGMA table_info(book)")
    cols = {r[1] for r in cur.fetchall()}
    if "total_read_time" not in cols or "md5" not in cols:
        con.close()
        raise ValueError("`book` table missing required columns")
    con.close()


def fetch_books(path: Path) -> List[Dict[str, Any]]:
    """Return list of books from the given DB with authors and series."""
    con = sqlite3.connect(path)
    cur = con.cursor()

    # First, check what columns are available in the book table
    cur.execute("PRAGMA table_info(book)")
    columns = {row[1] for row in cur.fetchall()}

    # Build query based on available columns
    base_query = "SELECT id, title, total_read_time, md5"
    fields = ["id", "title", "total_read_time", "md5"]

    if "authors" in columns:
        base_query += ", authors"
        fields.append("authors")

    if "series" in columns:
        base_query += ", series"
        fields.append("series")

    cur.execute(f"{base_query} FROM book ORDER BY id")
    rows = cur.fetchall()
    con.close()

    books = []
    for row in rows:
        book = {}
        for i, field in enumerate(fields):
            book[field] = row[i]

        # Add default values for missing fields
        if "authors" not in book:
            book["authors"] = "Unknown Author"
        if "series" not in book:
            book["series"] = None

        books.append(book)

    return books


def merge_books(path: Path, keep_id: int, merge_ids: List[int]) -> None:
    """
    Merge logic from original app:
     - copy all sessions under keep_id using MAX() on conflict
     - delete merged books
     - rebuild totals from page_stat_data
    """
    con = sqlite3.connect(path)
    cur = con.cursor()
    try:
        cur.execute("BEGIN")
        for mid in merge_ids:
            cur.execute(
                """
                INSERT INTO page_stat_data
                  (id_book, page, start_time, duration, total_pages)
                SELECT ?, page, start_time, duration, total_pages
                  FROM page_stat_data
                 WHERE id_book = ?
                ON CONFLICT(id_book, page, start_time) DO UPDATE SET
                  duration    = MAX(duration, excluded.duration),
                  total_pages = MAX(total_pages, excluded.total_pages)
            """,
                (keep_id, mid),
            )
            cur.execute("DELETE FROM book WHERE id = ?", (mid,))

        # Recompute totals
        cur.execute(
            """
            UPDATE book SET
              total_read_time = COALESCE((
                SELECT SUM(duration) FROM page_stat_data WHERE id_book = ?
              ), 0),
              total_read_pages = COALESCE((
                SELECT COUNT(DISTINCT page)
                  FROM page_stat_data WHERE id_book = ?
              ), 0)
            WHERE id = ?;
        """,
            (keep_id, keep_id, keep_id),
        )

        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


# Remove the root API endpoint so the catch-all route can serve the frontend
# @app.get("/")
# async def root():
#     return {"message": "Ko-Merge API v2.0", "download_count": get_download_count()}


@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    """Upload and validate SQLite database file."""
    if not file.filename or not file.filename.endswith(".sqlite3"):
        raise HTTPException(status_code=400, detail="Please upload a .sqlite3 file")

    # Generate session ID
    session_id = str(uuid.uuid4())

    # Save uploaded file
    file_path = UPLOAD_FOLDER / f"{session_id}.sqlite3"

    try:
        async with aiofiles.open(file_path, "wb") as f:
            content = await file.read()
            await f.write(content)

        # Validate the database
        validate_db(file_path)

        # Create enhanced session with persistence support
        now = datetime.now()
        sessions[session_id] = {
            "upload_db": f"{session_id}.sqlite3",
            "merge_groups": [],
            "created_at": now,  # File cleanup timer (fixed at 2 hours)
            "last_accessed": now,  # Session activity tracking
            "expires_at": now + SESSION_TIMEOUT,  # Rolling session expiration (2 hours)
        }

        return {
            "session_id": session_id,
            "message": "File uploaded and validated successfully",
        }

    except ValueError as e:
        # Remove invalid file
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=400, detail=f"Invalid KOReader DB: {str(e)}")
    except Exception as e:
        # Remove file on any error
        if file_path.exists():
            file_path.unlink()
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/books/{session_id}")
async def get_books(session_id: str):
    """Get books from uploaded database."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    file_path = UPLOAD_FOLDER / session["upload_db"]

    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Database file not found")

    try:
        books = fetch_books(file_path)
        return {"books": books, "merge_groups": session["merge_groups"]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to fetch books: {str(e)}")


@app.post("/api/merge-groups/{session_id}")
async def add_merge_group(session_id: str, merge_group: Dict[str, Any]):
    """Add a merge group to the session."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    keep_id = merge_group.get("keep_id")
    merge_ids = merge_group.get("merge_ids", [])

    if not keep_id or not merge_ids:
        raise HTTPException(
            status_code=400, detail="keep_id and merge_ids are required"
        )

    # Remove keep_id from merge_ids if present
    merge_ids = [mid for mid in merge_ids if mid != keep_id]

    if not merge_ids:
        raise HTTPException(
            status_code=400, detail="Select at least one different book to merge"
        )

    sessions[session_id]["merge_groups"].append((keep_id, merge_ids))

    return {"message": "Merge group added successfully"}


@app.delete("/api/merge-groups/{session_id}")
async def remove_last_merge_group(session_id: str):
    """Remove the last merge group."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    if session["merge_groups"]:
        session["merge_groups"].pop()
        return {"message": "Last merge group removed"}
    else:
        raise HTTPException(status_code=400, detail="No merge groups to remove")


@app.delete("/api/merge-groups/{session_id}/all")
async def clear_merge_groups(session_id: str):
    """Clear all merge groups."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    sessions[session_id]["merge_groups"] = []
    return {"message": "All merge groups cleared"}


@app.post("/api/execute-merge/{session_id}")
async def execute_merge(session_id: str):
    """Execute all merge operations."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    merge_groups = session["merge_groups"]

    if not merge_groups:
        raise HTTPException(status_code=400, detail="No merge groups to execute")

    # Copy upload to processed
    src_path = UPLOAD_FOLDER / session["upload_db"]
    dst_filename = f"{session_id}_fixed.sqlite3"
    dst_path = PROCESSED_FOLDER / dst_filename

    try:
        shutil.copy(src_path, dst_path)

        # Apply all merge operations
        for keep_id, merge_ids in merge_groups:
            merge_books(dst_path, keep_id, merge_ids)

        session["fixed_db"] = dst_filename

        return {
            "message": "Merge completed successfully",
            "download_filename": dst_filename,
        }

    except Exception as e:
        # Clean up on error
        if dst_path.exists():
            dst_path.unlink()
        raise HTTPException(status_code=500, detail=f"Merge failed: {str(e)}")


@app.get("/api/result/{session_id}")
async def get_result(session_id: str):
    """Get merged database results."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    fixed_db = session.get("fixed_db")

    if not fixed_db:
        raise HTTPException(status_code=404, detail="No merged database found")

    file_path = PROCESSED_FOLDER / fixed_db
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="Merged database file not found")

    try:
        books = fetch_books(file_path)
        return {"books": books}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch results: {str(e)}"
        )


@app.get("/api/download/{session_id}")
async def download_file(session_id: str):
    """Download the merged database file."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    fixed_db = session.get("fixed_db")

    if not fixed_db:
        raise HTTPException(status_code=404, detail="No merged database found")

    file_path = PROCESSED_FOLDER / fixed_db
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")

    # Increment download counter when user actually downloads the file
    increment_download_count()

    return FileResponse(
        path=file_path,
        filename="statistics_fixed.sqlite3",
        media_type="application/octet-stream",
    )


@app.delete("/api/cleanup/{session_id}")
async def cleanup_session(session_id: str):
    """Clean up session files."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]

    # Remove upload file
    if "upload_db" in session:
        upload_path = UPLOAD_FOLDER / session["upload_db"]
        if upload_path.exists():
            upload_path.unlink()

    # Remove processed file
    if "fixed_db" in session:
        processed_path = PROCESSED_FOLDER / session["fixed_db"]
        if processed_path.exists():
            processed_path.unlink()

    # Remove session
    del sessions[session_id]

    return {"message": "Session cleaned up successfully"}


# Session Persistence API Endpoints for 2-hour session management


@app.get("/api/validate-session/{session_id}")
async def validate_session(session_id: str):
    """
    Validate and extend an existing session.

    This endpoint checks if a session exists and is still valid, then extends
    the session timeout by another 2 hours from the current time. This enables
    session persistence across browser refreshes and provides a rolling timeout.

    Args:
        session_id: The session ID to validate

    Returns:
        Dict with session validity status and updated expiration time
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    now = datetime.now()

    # Check if session has expired
    if now > session["expires_at"]:
        # Session expired - clean it up
        try:
            await cleanup_session(session_id)
        except Exception:
            pass  # Session might already be cleaned up
        raise HTTPException(status_code=410, detail="Session expired")

    # Check if database file still exists
    file_path = UPLOAD_FOLDER / session["upload_db"]
    if not file_path.exists():
        # File was cleaned up - session is invalid
        del sessions[session_id]
        raise HTTPException(status_code=410, detail="Session files no longer available")

    # Session is valid - extend the timeout (rolling 2-hour window)
    session["last_accessed"] = now
    session["expires_at"] = now + SESSION_TIMEOUT

    # Calculate time remaining for file cleanup (fixed 2 hours from upload)
    file_cleanup_remaining = (session["created_at"] + CLEANUP_AGE) - now
    session_remaining = session["expires_at"] - now

    return {
        "valid": True,
        "session_id": session_id,
        "expires_at": session["expires_at"].isoformat(),
        "session_remaining_minutes": int(session_remaining.total_seconds() / 60),
        "file_cleanup_remaining_minutes": max(
            0, int(file_cleanup_remaining.total_seconds() / 60)
        ),
        "message": "Session validated and extended",
    }


@app.get("/api/session-info/{session_id}")
async def get_session_info(session_id: str):
    """
    Get detailed information about a session without extending it.

    This endpoint provides session metadata including creation time, expiration,
    merge groups, and file status. Useful for debugging and session management.

    Args:
        session_id: The session ID to get information for

    Returns:
        Dict with comprehensive session information
    """
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")

    session = sessions[session_id]
    now = datetime.now()

    # Check file existence
    upload_file_exists = (UPLOAD_FOLDER / session["upload_db"]).exists()
    processed_file_exists = False
    if "fixed_db" in session:
        processed_file_exists = (PROCESSED_FOLDER / session["fixed_db"]).exists()

    # Calculate time remaining
    file_cleanup_remaining = (session["created_at"] + CLEANUP_AGE) - now
    session_remaining = session["expires_at"] - now

    return {
        "session_id": session_id,
        "created_at": session["created_at"].isoformat(),
        "last_accessed": session["last_accessed"].isoformat(),
        "expires_at": session["expires_at"].isoformat(),
        "is_expired": now > session["expires_at"],
        "session_remaining_minutes": int(session_remaining.total_seconds() / 60),
        "file_cleanup_remaining_minutes": max(
            0, int(file_cleanup_remaining.total_seconds() / 60)
        ),
        "upload_db": session["upload_db"],
        "upload_file_exists": upload_file_exists,
        "fixed_db": session.get("fixed_db"),
        "processed_file_exists": processed_file_exists,
        "merge_groups_count": len(session["merge_groups"]),
        "merge_groups": session["merge_groups"],
    }


async def cleanup_expired_sessions():
    """
    Clean up expired sessions and their associated files.

    This function is called periodically to remove sessions that have exceeded
    their timeout period. It also handles file cleanup based on the fixed
    2-hour file retention policy.
    """
    now = datetime.now()
    expired_sessions = []

    # Find expired sessions
    for session_id, session in sessions.items():
        if now > session["expires_at"]:
            expired_sessions.append(session_id)

    # Clean up expired sessions
    for session_id in expired_sessions:
        try:
            # This will handle file cleanup as well
            await cleanup_session(session_id)
            logger.info(f"Cleaned up expired session: {session_id}")
        except Exception as e:
            logger.error(f"Error cleaning up expired session {session_id}: {e}")

    # Also clean up old files (independent of session status)
    cleanup_old_files()

    return len(expired_sessions)


@app.get("/api/cleanup-expired-sessions")
async def cleanup_expired_sessions_endpoint():
    """
    Manual endpoint to trigger cleanup of expired sessions.

    This endpoint allows manual triggering of the session cleanup process,
    which is useful for testing and maintenance. In production, this would
    typically be called by a background task.

    Returns:
        Dict with cleanup statistics
    """
    try:
        cleaned_count = await cleanup_expired_sessions()
        return {
            "success": True,
            "cleaned_sessions": cleaned_count,
            "active_sessions": len(sessions),
            "message": f"Cleaned up {cleaned_count} expired sessions",
        }
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to cleanup expired sessions: {str(e)}"
        )


# New Book Details and Cover API Endpoints


@app.post("/api/book-details")
async def get_book_details(request: Dict[str, Any]):
    """Get detailed book information from external APIs"""
    title = request.get("title", "")
    author = request.get("authors", "")
    source = request.get("source", "googlebooks")
    asin = request.get("asin", "")
    isbn = request.get("isbn", "")

    if not book_metadata_service:
        # Fallback response when service is not available
        return {
            "success": True,
            "metadata": {
                "title": title,
                "authors": [author] if author else ["Unknown Author"],
                "description": f"This is a placeholder description for '{title}'. The book metadata service is currently not available, but the interactive book details functionality is working correctly. In a full setup with Google Books API key, this would show rich metadata including description, publisher, ratings, categories, and high-quality cover images.",
                "publisher": "Demo Publisher",
                "published_date": "2024",
                "page_count": 250,
                "categories": ["Demo Category", "Interactive Features"],
                "average_rating": 4.2,
                "ratings_count": 42,
                "covers": [
                    f"https://covers.openlibrary.org/b/title/{title.replace(' ', '%20')}-M.jpg"
                ],
                "source": "demo",
            },
        }

    try:
        # Handle ASIN-based searches
        if asin and source == "amazon":
            details = await book_metadata_service.search_amazon_by_asin(asin)  # type: ignore
            if details:
                return {"success": True, "metadata": details}
            else:
                return {"success": False, "error": "Book not found for ASIN"}

        # Handle ISBN-based searches
        elif isbn:
            details = None
            if source == "google_books":
                details = await book_metadata_service.search_google_books_by_isbn(isbn)
            elif source == "openlibrary":
                details = await book_metadata_service.search_openlibrary_by_isbn(isbn)
            else:
                # Try both for ISBN searches
                google_result = await book_metadata_service.search_google_books_by_isbn(
                    isbn
                )
                if google_result:
                    details = google_result
                else:
                    details = await book_metadata_service.search_openlibrary_by_isbn(
                        isbn
                    )

            if details:
                return {"success": True, "metadata": details}
            else:
                return {"success": False, "error": "Book not found for ISBN"}

        # Handle regular title/author searches
        else:
            # Generate book key for caching
            book_key = book_metadata_service.generate_book_key(title, author)

            # Check cache first if database service is available
            cached_data = None
            if database_service:
                cached_data = database_service.get_cached_book_metadata(
                    book_key, source
                )

            if cached_data:
                return cached_data

            # Fetch from API
            details = await book_metadata_service.get_book_details(
                title, author, source
            )

            if not details:
                return {"success": False, "error": "Book not found"}

            # Cache the result if database service is available
            if database_service and details:
                database_service.cache_book_metadata(book_key, source, details)

            return {"success": True, "metadata": details}

    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to fetch book details: {str(e)}"
        )


@app.get("/api/cover-options")
async def get_cover_options(
    title: str = "",
    author: str = "",
    source: str = "googlebooks",
    isbn: str = "",
    asin: str = "",
    exclude_sources: str = "",
):
    """Get multiple cover options for a book"""
    if not book_metadata_service:
        # Return fallback response when service is not available
        return {
            "success": True,
            "covers": [
                {
                    "url": f"https://covers.openlibrary.org/b/title/{title.replace(' ', '%20')}-M.jpg",
                    "source": "openlibrary",
                    "size": "medium",
                }
            ],
        }

    try:
        covers = None
        # Handle ASIN-only searches for Amazon
        if asin and source == "amazon":
            covers = await book_metadata_service.get_cover_options_by_asin(asin)  # type: ignore
        # Handle ISBN searches
        elif isbn:
            covers = await book_metadata_service.get_cover_options_by_isbn(isbn, source)
        # Handle regular title/author searches
        elif title:
            covers = await book_metadata_service.get_cover_options(
                title, author, source, exclude_sources
            )
        else:
            return {"success": False, "error": "Must provide title, ISBN, or ASIN"}

        return {"success": True, "covers": covers}
    except Exception as e:
        return {"success": False, "error": f"Failed to fetch cover options: {str(e)}"}


@app.post("/api/cover-preference")
async def save_cover_preference(preference: Dict[str, Any]):
    """
    Save user's selected cover preference without triggering new searches.

    This endpoint stores the user's selected cover locally without fetching
    new covers from external sources. It only processes the cover URL that
    the user has already selected from previously searched results.

    Args:
        preference: Dict containing title, author, cover_url, and optionally md5

    Returns:
        Dict with success status, stored covers, and book hash
    """
    if not cover_storage_service:
        raise HTTPException(
            status_code=503, detail="Cover storage service not available"
        )

    title = preference.get("title", "")
    author = preference.get("author", "")
    cover_url = preference.get("cover_url", "")
    # Note: MD5 is no longer used for book identification, only title+author hash

    if not title:
        raise HTTPException(status_code=400, detail="title is required")

    if not cover_url:
        raise HTTPException(status_code=400, detail="cover_url is required")

    try:
        # Generate book hash using only title and author (no MD5)
        book_hash = cover_storage_service.generate_book_hash(title, author)

        # Determine source from URL
        source = "unknown"
        if "books.google.com" in cover_url:
            source = "google_books"
        elif "covers.openlibrary.org" in cover_url:
            source = "openlibrary"
        elif "amazon.com" in cover_url or "images-amazon.com" in cover_url:
            source = "amazon"

        # Download and store the selected cover only
        image_hash = await cover_storage_service.download_and_store_cover(
            title, author, cover_url, source
        )

        if image_hash:
            stored_cover = cover_storage_service.get_stored_cover(book_hash)
            stored_covers = [stored_cover] if stored_cover else []
            cover_count = 1
        else:
            stored_covers = []
            cover_count = 0

        return {
            "success": True,
            "message": f"Successfully stored {cover_count} covers",
            "book_hash": book_hash,
            "stored_covers": stored_covers,
        }

    except Exception as e:
        logger.error(
            f"Failed to save cover preference for '{title}' by '{author}': {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to save cover preference: {str(e)}"
        )


@app.get("/api/cover-preference")
async def get_cover_preference(title: str, author: str = ""):
    """
    Enhanced cover preference endpoint with batch support and unified storage.

    This endpoint retrieves locally stored cover images instead of external URLs.
    It supports both single book queries and batch queries for multiple books.

    Args:
        title: Book title (required)
        author: Book author (optional, but recommended for better matching)
        batch: Optional comma-separated list of book hashes for batch retrieval

    Returns:
        Dict with stored covers and metadata, or batch results if batch parameter provided
    """
    if not cover_storage_service:
        raise HTTPException(
            status_code=503, detail="Cover storage service not available"
        )

    try:
        # Generate book hash using only title and author
        book_hash = cover_storage_service.generate_book_hash(title, author)

        # Get stored covers for this book
        stored_cover = cover_storage_service.get_stored_cover(book_hash)

        if stored_cover:
            return {
                "success": True,
                "book_hash": book_hash,
                "stored_covers": [stored_cover],
                "title": title,
                "author": author,
            }
        else:
            raise HTTPException(
                status_code=404,
                detail=f"No stored covers found for '{title}' by '{author}'",
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(
            f"Failed to get cover preference for '{title}' by '{author}': {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get cover preference: {str(e)}"
        )


@app.get("/api/covers/batch")
async def get_batch_covers(book_hashes: str):
    """
    Batch endpoint for retrieving multiple book covers efficiently.

    This endpoint allows the frontend to request covers for multiple books in a single
    request, reducing network overhead when loading book lists or search results.

    Args:
        book_hashes: Comma-separated list of book hashes

    Returns:
        Dict mapping book hashes to their stored cover data
    """
    if not cover_storage_service:
        raise HTTPException(
            status_code=503, detail="Cover storage service not available"
        )

    try:
        # Parse comma-separated book hashes
        hash_list = [h.strip() for h in book_hashes.split(",") if h.strip()]

        if not hash_list:
            raise HTTPException(status_code=400, detail="No book hashes provided")

        # Get batch covers by querying each book hash individually
        batch_results = {}
        for book_hash in hash_list:
            stored_cover = cover_storage_service.get_stored_cover(book_hash)
            batch_results[book_hash] = stored_cover

        return {
            "success": True,
            "covers": batch_results,
            "total_requested": len(hash_list),
            "total_found": len([r for r in batch_results.values() if r]),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get batch covers: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get batch covers: {str(e)}"
        )


@app.get("/api/covers/{image_hash}")
async def serve_cover_image(image_hash: str):
    """
    Serve locally stored cover images.

    This endpoint serves cover images that have been downloaded and stored locally
    by the cover storage service. Images are served with appropriate caching headers
    and content types for optimal browser performance.

    Args:
        image_hash: SHA256 hash of the cover image

    Returns:
        FileResponse with the cover image
    """
    if not cover_storage_service:
        raise HTTPException(
            status_code=503, detail="Cover storage service not available"
        )

    try:
        # Get the file path for the image
        image_path = cover_storage_service.get_cover_file_path(image_hash)

        if not image_path or not image_path.exists():
            raise HTTPException(status_code=404, detail="Cover image not found")

        # Determine content type based on file extension
        content_type = "image/jpeg"  # Default
        if image_path.suffix.lower() == ".png":
            content_type = "image/png"
        elif image_path.suffix.lower() == ".webp":
            content_type = "image/webp"
        elif image_path.suffix.lower() == ".gif":
            content_type = "image/gif"

        return FileResponse(
            path=image_path,
            media_type=content_type,
            headers={
                "Cache-Control": "public, max-age=86400",  # Cache for 24 hours
                "ETag": image_hash[:16],  # Use part of hash as ETag
            },
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to serve cover image {image_hash}: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to serve cover image: {str(e)}"
        )


@app.get("/api/proxy-image")
async def proxy_image(url: str):
    """
    Proxy external images to bypass CORS restrictions.

    This endpoint fetches external images (from Google Books, OpenLibrary, etc.)
    and serves them to the frontend, bypassing CORS restrictions that prevent
    direct fetching from the browser.

    Args:
        url: The external image URL to proxy

    Returns:
        The image content with appropriate headers
    """
    import httpx
    from fastapi.responses import Response

    if not url:
        raise HTTPException(status_code=400, detail="URL parameter is required")

    # Validate URL to prevent abuse
    allowed_domains = [
        "books.google.com",
        "covers.openlibrary.org",
        "images-na.ssl-images-amazon.com",
        "m.media-amazon.com",
        "images.amazon.com",
    ]

    from urllib.parse import urlparse

    parsed_url = urlparse(url)

    if not any(domain in parsed_url.netloc for domain in allowed_domains):
        raise HTTPException(status_code=400, detail="URL domain not allowed")

    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                url,
                headers={
                    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36"
                },
            )

            if response.status_code != 200:
                raise HTTPException(status_code=404, detail="Image not found")

            # Determine content type
            content_type = response.headers.get("content-type", "image/jpeg")

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",  # Cache for 1 hour
                    "Access-Control-Allow-Origin": "*",
                },
            )

    except httpx.TimeoutException:
        raise HTTPException(status_code=408, detail="Request timeout")
    except Exception as e:
        logger.error(f"Failed to proxy image {url}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to proxy image: {str(e)}")


@app.get("/api/download-count")
async def get_download_count_api():
    """Get the current download counter"""
    try:
        count = get_download_count()
        return {"download_count": count}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get download count: {str(e)}"
        )


@app.get("/api/config")
async def get_api_config():
    """Get API configuration including available services"""
    config = {
        "google_books_available": bool(
            book_metadata_service and book_metadata_service.google_books_api_key
        ),
        "amazon_scraping_available": bool(
            book_metadata_service and hasattr(book_metadata_service, "search_amazon")
        ),
        "openlibrary_available": True,  # OpenLibrary is always available (no API key required)
        "cover_storage_available": bool(cover_storage_service),
        "default_source": "openlibrary"
        if not (book_metadata_service and book_metadata_service.google_books_api_key)
        else "google_books",
    }

    return {"success": True, "config": config}


@app.get("/api/preferences-stats")
async def get_preferences_stats():
    """Get statistics about saved preferences"""
    if not database_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        stats = database_service.get_cover_preferences_stats()
        return stats
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get preferences stats: {str(e)}"
        )


@app.get("/api/cached-metadata")
async def get_cached_metadata_only(title: str, author: str = ""):
    """Get ONLY cached metadata without triggering new API calls"""
    if not database_service or not book_metadata_service:
        raise HTTPException(status_code=503, detail="Database service not available")

    try:
        # Generate book key using the same method as the metadata service
        book_key = book_metadata_service.generate_book_key(title, author)

        # Try all sources to find cached metadata (no API calls)
        sources_to_try = ["amazon", "google_books", "openlibrary"]
        all_metadata = {}

        for source in sources_to_try:
            cached_data = database_service.get_cached_book_metadata(book_key, source)
            if cached_data:
                all_metadata[source] = cached_data

        if all_metadata:
            # Return the best metadata (prioritize Amazon, then Google Books, then OpenLibrary)
            best_source = None
            best_metadata = None

            for source in sources_to_try:
                if source in all_metadata:
                    best_source = source
                    best_metadata = all_metadata[source]
                    break

            return {
                "success": True,
                "metadata": best_metadata,
                "source": best_source,
                "all_sources": all_metadata,
                "book_key": book_key,
            }

        # No cached metadata found
        return {
            "success": False,
            "error": "No cached metadata found",
            "book_key": book_key,
        }

    except Exception as e:
        logger.error(
            f"Failed to get cached metadata for '{title}' by '{author}': {str(e)}"
        )
        raise HTTPException(
            status_code=500, detail=f"Failed to get cached metadata: {str(e)}"
        )


# Serve frontend at root path (must be last to avoid interfering with API routes)
@app.get("/{full_path:path}")
async def serve_frontend(full_path: str):
    """Serve frontend files, fallback to index.html for SPA routing"""
    # Try to serve the requested file
    file_path = os.path.join(static_dir, full_path)
    if os.path.isfile(file_path):
        return FileResponse(file_path)

    # Fallback to index.html for SPA routing
    index_path = os.path.join(static_dir, "index.html")
    if os.path.isfile(index_path):
        return FileResponse(index_path)

    raise HTTPException(status_code=404, detail="File not found")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
