import sqlite3
import re
from pathlib import Path


def normalize_text(text):
    if not text:
        return ""
    text = re.sub(r"[^\w\s]", "", text)  # remove punctuation
    return re.sub(r"\s+", " ", text.strip().lower())


# Use a database in the backend data directory
DB_NAME = Path(__file__).parent.parent.parent / "data" / "amazon_books.db"


def initialize_db():
    # Ensure the data directory exists
    DB_NAME.parent.mkdir(parents=True, exist_ok=True)

    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS books (
                asin TEXT PRIMARY KEY,
                title TEXT,
                author TEXT,
                title_search TEXT,
                author_search TEXT,
                cover_url TEXT,
                book_url TEXT,
        is_kindle_unlimited TEXT,
                isbn TEXT,
                genres TEXT,
                print_length TEXT,
                series TEXT,
                series_index INTEGER,
                series_position TEXT,
                publisher TEXT,
                publication_date TEXT,
                edition TEXT,
                language TEXT,
                file_size TEXT,                                       
                average_rating TEXT,
                review_count TEXT,
                status TEXT,
                book_description TEXT
            )
        """)
        conn.commit()


def get_book_by_asin(asin):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM books WHERE asin = ?", (asin,))
        row = cursor.fetchone()
        return dict(row) if row else None


def get_book_by_title_author(title, author):
    normalized_title = normalize_text(title)
    normalized_author = normalize_text(author)

    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()

        # First try exact match
        cursor.execute(
            """
            SELECT * FROM books
            WHERE title_search = ? AND author_search = ?
        """,
            (normalized_title, normalized_author),
        )
        row = cursor.fetchone()

        # If no exact match, try fuzzy match with LIKE
        if not row:
            cursor.execute(
                """
                SELECT * FROM books
                WHERE title_search LIKE ? AND author_search = ?
            """,
                (f"%{normalized_title}%", normalized_author),
            )
            row = cursor.fetchone()

        return dict(row) if row else None


def save_book_metadata(metadata):
    print("SAVING TO DATABASE")
    title = metadata.get("Title")
    author = metadata.get("Author")
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT OR REPLACE INTO books (
                asin, title, author, title_search, author_search, cover_url, book_url,
                is_kindle_unlimited, isbn, genres, print_length, series, series_index, series_position,
                publisher, publication_date, edition, language, file_size,
                average_rating, review_count, status, book_description
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
            (
                metadata.get("ASIN"),
                title,
                author,
                normalize_text(title),
                normalize_text(author),
                metadata.get("Cover URL"),
                metadata.get("Book URL"),
                metadata.get("isKindleUnlimited"),
                metadata.get("ISBN"),
                ", ".join(metadata.get("Genres", [])),
                metadata.get("Print Length"),
                metadata.get("Series"),
                metadata.get("Series Index"),
                metadata.get("Series Position"),
                metadata.get("Publisher"),
                metadata.get("Publication Date"),
                metadata.get("Edition"),
                metadata.get("Language"),
                metadata.get("File Size"),
                metadata.get("Average Rating"),
                metadata.get("Review Count"),
                metadata.get("Status"),
                metadata.get("Book Description"),
            ),
        )
        conn.commit()
