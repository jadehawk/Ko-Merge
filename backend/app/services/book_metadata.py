import aiohttp
import hashlib
import os
import asyncio
from typing import Dict, List, Any, Set
import logging

logger = logging.getLogger(__name__)

# Global set to track ongoing Amazon scraping requests
_ongoing_amazon_requests: Set[str] = set()
_request_lock = asyncio.Lock()

# Import Amazon scraping functionality with error handling
try:
    from .playwright_wrapper import (
        scrape_amazon_book_safe,
        scrape_amazon_book_safe_by_asin,
    )
    from .amazon_cachedb import (
        initialize_db,
        get_book_by_title_author,
        get_book_by_asin,
        save_book_metadata,
    )

    AMAZON_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Amazon scraping not available: {e}")
    # Set imports to None if not available - much cleaner than dummy functions
    scrape_amazon_book_safe = None
    scrape_amazon_book_safe_by_asin = None
    initialize_db = None
    get_book_by_title_author = None
    get_book_by_asin = None
    save_book_metadata = None
    AMAZON_AVAILABLE = False


class BookMetadataService:
    def __init__(self):
        self.google_books_api_key = os.getenv("GOOGLE_BOOKS_API_KEY")
        self.session = None

    async def get_session(self):
        if self.session is None:
            self.session = aiohttp.ClientSession()
        return self.session

    async def close(self):
        if self.session:
            await self.session.close()

    def generate_book_key(self, title: str, author: str = "", md5: str = "") -> str:
        """Generate a unique key for book identification (includes MD5 for user-specific data)"""
        # Normalize strings for consistent hashing
        title_norm = title.lower().strip() if title else ""
        author_norm = author.lower().strip() if author else ""
        md5_norm = md5.lower().strip() if md5 else ""

        key_string = f"{title_norm}|{author_norm}|{md5_norm}"
        return hashlib.md5(key_string.encode()).hexdigest()

    def generate_amazon_cache_key(self, title: str, author: str = "") -> str:
        """Generate a global cache key for Amazon data (title/author only)"""
        # Use the same normalization as Amazon database for consistency
        from .amazon_cachedb import normalize_text

        title_norm = normalize_text(title) if title else ""
        author_norm = normalize_text(author) if author else ""
        return f"{title_norm}|{author_norm}"

    async def search_google_books(self, title: str, author: str = "") -> Dict[str, Any]:
        """Search Google Books API for book metadata with multiple query strategies"""
        if not self.google_books_api_key:
            logger.warning("Google Books API key not configured")
            return {}

        try:
            session = await self.get_session()
            url = "https://www.googleapis.com/books/v1/volumes"

            # Try multiple search strategies in order of preference
            search_strategies = []

            if title and author:
                # Strategy 1: Exact match with quotes
                search_strategies.append(f'intitle:"{title}" inauthor:"{author}"')
                # Strategy 2: Broad match without quotes
                search_strategies.append(f"{title} {author}")
                # Strategy 3: Title focused with author
                search_strategies.append(f"intitle:{title} {author}")
                # Strategy 4: Author focused with title
                search_strategies.append(f'inauthor:"{author}" {title}')
            elif title:
                # Title-only searches
                search_strategies.append(f'intitle:"{title}"')
                search_strategies.append(f"intitle:{title}")
                search_strategies.append(title)
            elif author:
                # Author-only searches
                search_strategies.append(f'inauthor:"{author}"')
                search_strategies.append(author)

            # Try each search strategy
            for i, query in enumerate(search_strategies):
                logger.info(
                    f"Google Books search attempt {i + 1}/{len(search_strategies)}: {query}"
                )

                params = {
                    "q": query,
                    "key": self.google_books_api_key,
                    "maxResults": 10,  # Increased for better results
                    "printType": "books",
                }

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = self._normalize_google_books_response(
                            data, title, author
                        )
                        if result:  # If we found a match
                            logger.info(
                                f"Google Books found match with strategy {i + 1}: {query}"
                            )
                            return result
                    else:
                        logger.warning(
                            f"Google Books API error for query '{query}': {response.status}"
                        )

            logger.info(f"Google Books: No matches found for '{title}' by '{author}'")
            return {}

        except Exception as e:
            logger.error(f"Error searching Google Books: {str(e)}")
            return {}

    async def search_openlibrary(self, title: str, author: str = "") -> Dict[str, Any]:
        """Search OpenLibrary API for book metadata with multiple query strategies"""
        try:
            session = await self.get_session()
            url = "https://openlibrary.org/search.json"

            # Try multiple search strategies
            search_strategies = []

            if title and author:
                # Strategy 1: Both title and author
                search_strategies.append({"title": title, "author": author})
                # Strategy 2: General search with both
                search_strategies.append({"q": f"{title} {author}"})
                # Strategy 3: Title only with author in general search
                search_strategies.append({"title": title, "q": author})
            elif title:
                # Title-only searches
                search_strategies.append({"title": title})
                search_strategies.append({"q": title})
            elif author:
                # Author-only searches
                search_strategies.append({"author": author})
                search_strategies.append({"q": author})

            # Try each search strategy
            for i, params in enumerate(search_strategies):
                logger.info(
                    f"OpenLibrary search attempt {i + 1}/{len(search_strategies)}: {params}"
                )

                # Add common parameters
                params.update(
                    {
                        "limit": 10,
                        "fields": "key,title,subtitle,author_name,first_publish_year,publisher,number_of_pages_median,subject,language,cover_i,isbn,lccn,oclc",
                    }
                )

                async with session.get(url, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        result = self._normalize_openlibrary_response(
                            data, title, author
                        )
                        if result:  # If we found a match
                            logger.info(
                                f"OpenLibrary found match with strategy {i + 1}: {params}"
                            )
                            return result
                    else:
                        logger.warning(
                            f"OpenLibrary API error for params {params}: {response.status}"
                        )

            logger.info(f"OpenLibrary: No matches found for '{title}' by '{author}'")
            return {}

        except Exception as e:
            logger.error(f"Error searching OpenLibrary: {str(e)}")
            return {}

    async def search_amazon(self, title: str, author: str = "") -> Dict[str, Any]:
        """
        Search Amazon for book metadata using web scraping with caching and request deduplication.
        First checks cache, then scrapes if not found, preventing duplicate concurrent requests.

        Args:
            title (str): Book title to search for
            author (str, optional): Author name to search for

        Returns:
            Dict[str, Any]: Normalized book metadata or empty dict if not found
        """
        if not AMAZON_AVAILABLE or not initialize_db:
            logger.warning("Amazon scraping not available")
            return {}

        if not title:
            logger.warning("Amazon search requires at least a title")
            return {}

        # Generate cache key for deduplication
        cache_key = self.generate_amazon_cache_key(title, author)

        try:
            # Initialize Amazon database if needed
            initialize_db()

            # Check cache first
            logger.info(
                f"Amazon: Checking cache for '{title}' by '{author}' (cache_key: {cache_key})"
            )
            cached_result = (
                get_book_by_title_author(title, author)
                if get_book_by_title_author
                else None
            )
            if cached_result:
                logger.info(f"Amazon: Found cached result for '{title}' by '{author}'")
                return self._normalize_amazon_response(cached_result)
            else:
                logger.info(
                    f"Amazon: No cached result found for '{title}' by '{author}' (cache_key: {cache_key})"
                )

            # Check if scraping is already in progress for this book
            async with _request_lock:
                if cache_key in _ongoing_amazon_requests:
                    logger.info(
                        f"Amazon: Scraping already in progress for '{title}' by '{author}', waiting..."
                    )
                    # Wait for the ongoing request to complete
                    while cache_key in _ongoing_amazon_requests:
                        await asyncio.sleep(0.5)  # Wait 500ms before checking again

                    # Check cache again after waiting
                    cached_result = (
                        get_book_by_title_author(title, author)
                        if get_book_by_title_author
                        else None
                    )
                    if cached_result:
                        logger.info(
                            f"Amazon: Found cached result after waiting for '{title}' by '{author}'"
                        )
                        return self._normalize_amazon_response(cached_result)
                    else:
                        logger.warning(
                            f"Amazon: No cached result found after waiting for '{title}' by '{author}'"
                        )
                        return {}

                # Mark this request as in progress
                _ongoing_amazon_requests.add(cache_key)

            try:
                # If not in cache, scrape Amazon
                if scrape_amazon_book_safe:
                    logger.info(
                        f"Amazon: Loading Book Details for '{title}' by '{author}'"
                    )
                    scraped_data = await scrape_amazon_book_safe(
                        title=title, author=author
                    )

                    if (
                        scraped_data
                        and scraped_data.get("Title")
                        and scraped_data.get("Author")
                    ):
                        # Save to cache
                        if save_book_metadata:
                            save_book_metadata(scraped_data)
                        logger.info(
                            f"Amazon: Successfully scraped and cached '{title}' by '{author}'"
                        )
                        return self._normalize_amazon_response(scraped_data)
                    else:
                        logger.info(
                            f"Amazon: No results found for '{title}' by '{author}'"
                        )
                        return {}
                else:
                    logger.warning("Amazon scraper function not available")
                    return {}
            finally:
                # Always remove from ongoing requests when done
                async with _request_lock:
                    _ongoing_amazon_requests.discard(cache_key)

        except Exception as e:
            # Make sure to clean up on error
            async with _request_lock:
                _ongoing_amazon_requests.discard(cache_key)
            logger.error(f"Error searching Amazon: {str(e)}")
            return {}

    def _normalize_google_books_response(
        self, data: Dict, title: str = "", author: str = ""
    ) -> Dict[str, Any]:
        """Normalize Google Books API response to standard format"""
        if not data.get("items"):
            return {}

        # Take the first (most relevant) result
        item = data["items"][0]
        volume_info = item.get("volumeInfo", {})

        # Extract cover images
        covers = []
        image_links = volume_info.get("imageLinks", {})
        for size in [
            "extraLarge",
            "large",
            "medium",
            "small",
            "thumbnail",
            "smallThumbnail",
        ]:
            if size in image_links:
                # Get the original URL and convert to HTTPS
                original_url = image_links[size].replace("http://", "https://")

                # Try to get a cleaner version without the Google Books watermark
                # by modifying URL parameters
                clean_url = original_url

                # Remove edge=curl parameter which adds the folded corner effect
                if "edge=curl" in clean_url:
                    clean_url = (
                        clean_url.replace("&edge=curl", "")
                        .replace("?edge=curl&", "?")
                        .replace("?edge=curl", "")
                    )

                # Add parameters to try to get cleaner images
                if "?" in clean_url:
                    clean_url += "&printsec=frontcover&img=1&zoom=1&source=gbs_api"
                else:
                    clean_url += "?printsec=frontcover&img=1&zoom=1&source=gbs_api"

                covers.append(
                    {
                        "size": size,
                        "url": clean_url,
                        "source": "google_books",
                    }
                )

        # Extract categories/genres
        categories = volume_info.get("categories", [])
        subjects = volume_info.get("subjects", [])
        all_genres = list(set(categories + subjects))

        # Extract identifiers
        identifiers = {}
        for identifier in volume_info.get("industryIdentifiers", []):
            identifiers[identifier.get("type", "").lower()] = identifier.get(
                "identifier", ""
            )

        return {
            "source": "googlebooks",
            "title": volume_info.get("title", ""),
            "subtitle": volume_info.get("subtitle", ""),
            "authors": volume_info.get("authors", []),
            "publisher": volume_info.get("publisher", ""),
            "published_date": volume_info.get("publishedDate", ""),
            "description": volume_info.get("description", ""),
            "page_count": volume_info.get("pageCount", 0),
            "categories": all_genres,
            "language": volume_info.get("language", ""),
            "preview_link": volume_info.get("previewLink", ""),
            "info_link": volume_info.get("infoLink", ""),
            "canonical_volume_link": volume_info.get("canonicalVolumeLink", ""),
            "covers": covers,
            "identifiers": identifiers,
            "average_rating": volume_info.get("averageRating", 0),
            "ratings_count": volume_info.get("ratingsCount", 0),
            "maturity_rating": volume_info.get("maturityRating", ""),
            "print_type": volume_info.get("printType", ""),
            "content_version": volume_info.get("contentVersion", ""),
            "raw_data": item,  # Store full response for debugging
        }

    def _normalize_openlibrary_response(
        self, data: Dict, title: str = "", author: str = ""
    ) -> Dict[str, Any]:
        """Normalize OpenLibrary API response to standard format"""
        if not data.get("docs"):
            return {}

        # Take the first (most relevant) result
        doc = data["docs"][0]

        # Extract cover images
        covers = []
        if doc.get("cover_i"):
            cover_id = doc["cover_i"]
            for size in ["L", "M", "S"]:
                covers.append(
                    {
                        "size": size.lower(),
                        "url": f"https://covers.openlibrary.org/b/id/{cover_id}-{size}.jpg",
                        "source": "openlibrary",
                    }
                )

        # Extract identifiers
        identifiers = {}
        for field in ["isbn", "lccn", "oclc"]:
            if doc.get(field):
                identifiers[field] = (
                    doc[field][0] if isinstance(doc[field], list) else doc[field]
                )

        return {
            "source": "openlibrary",
            "title": doc.get("title", ""),
            "subtitle": doc.get("subtitle", ""),
            "authors": doc.get("author_name", []),
            "publisher": doc.get("publisher", [""])[0] if doc.get("publisher") else "",
            "published_date": str(doc.get("first_publish_year", "")),
            "description": "",  # OpenLibrary search doesn't include descriptions
            "page_count": doc.get("number_of_pages_median", 0),
            "categories": doc.get("subject", [])[:10],  # Limit subjects
            "language": doc.get("language", [""])[0] if doc.get("language") else "",
            "preview_link": "",
            "info_link": f"https://openlibrary.org{doc.get('key', '')}",
            "canonical_volume_link": f"https://openlibrary.org{doc.get('key', '')}",
            "covers": covers,
            "identifiers": identifiers,
            "average_rating": 0,  # OpenLibrary doesn't provide ratings in search
            "ratings_count": 0,
            "maturity_rating": "",
            "print_type": "BOOK",
            "content_version": "",
            "raw_data": doc,  # Store full response for debugging
        }

    def _normalize_amazon_response(self, data: Dict) -> Dict[str, Any]:
        """
        Normalize Amazon scraper response to standard format.
        Converts Amazon's field names to match the standard format used by other sources.
        Handles both direct scraper format (capitalized keys) and cached database format (lowercase keys).

        Args:
            data (Dict): Raw Amazon scraper data or cached database data

        Returns:
            Dict[str, Any]: Normalized book metadata
        """
        if not data:
            return {}

        # Extract cover images - Amazon provides a single cover URL
        # Handle both direct scraper format ("Cover URL") and cached database format ("cover_url")
        covers = []
        cover_url = data.get("Cover URL") or data.get("cover_url")
        if cover_url:
            covers.append(
                {
                    "size": "large",
                    "url": cover_url,
                    "source": "amazon",
                }
            )

        # Parse genres from comma-separated string
        # Handle both formats: "Genres" and "genres"
        categories = []
        genres = data.get("Genres") or data.get("genres")
        if genres:
            if isinstance(genres, list):
                categories = genres
            elif isinstance(genres, str):
                categories = [g.strip() for g in genres.split(",") if g.strip()]

        # Extract authors - Amazon provides a single author string
        # Handle both formats: "Author" and "author"
        authors = []
        author = data.get("Author") or data.get("author")
        if author:
            authors = [author]

        # Parse page count from string like "320 pages"
        # Handle both formats: "Print Length" and "print_length"
        page_count = 0
        print_length = data.get("Print Length") or data.get("print_length")
        if print_length:
            try:
                # Extract number from strings like "320 pages" or "320"
                import re

                match = re.search(r"\d+", str(print_length))
                if match:
                    page_count = int(match.group())
            except (ValueError, AttributeError):
                pass

        # Parse rating
        # Handle both formats: "Average Rating"/"Review Count" and "average_rating"/"review_count"
        average_rating = 0
        ratings_count = 0
        try:
            rating = data.get("Average Rating") or data.get("average_rating")
            if rating:
                average_rating = float(rating)

            count = data.get("Review Count") or data.get("review_count")
            if count:
                ratings_count = int(count)
        except (ValueError, TypeError):
            pass

        # Handle both title formats: "Title" and "title"
        title = data.get("Title") or data.get("title") or ""

        # Handle both publisher formats: "Publisher" and "publisher"
        publisher = data.get("Publisher") or data.get("publisher") or ""

        # Handle both publication date formats: "Publication Date" and "publication_date"
        published_date = (
            data.get("Publication Date") or data.get("publication_date") or ""
        )

        # Handle both description formats: "Book Description" and "book_description"
        description = data.get("Book Description") or data.get("book_description") or ""

        # Handle both language formats: "Language" and "language"
        language = data.get("Language") or data.get("language") or ""

        # Handle both URL formats: "Book URL" and "book_url"
        book_url = data.get("Book URL") or data.get("book_url") or ""

        # Handle both ISBN formats: "ISBN" and "isbn"
        isbn = data.get("ISBN") or data.get("isbn") or ""

        # Handle both Kindle Unlimited formats: "isKindleUnlimited" and "is_kindle_unlimited"
        kindle_unlimited_value = (
            data.get("isKindleUnlimited") or data.get("is_kindle_unlimited") or "NO"
        )

        # Handle both series formats: "Series" and "series"
        series = data.get("Series") or data.get("series") or ""

        # Handle both series index formats: "Series Index" and "series_index"
        series_index = data.get("Series Index") or data.get("series_index")

        # Handle both status formats: "Status" and "status"
        status = data.get("Status") or data.get("status") or ""

        return {
            "source": "amazon",
            "title": title,
            "subtitle": "",  # Amazon doesn't typically separate subtitles
            "authors": authors,
            "publisher": publisher,
            "published_date": published_date,
            "description": description,
            "page_count": page_count,
            "categories": categories,
            "language": language,
            "preview_link": "",  # Amazon doesn't provide preview links
            "info_link": book_url,
            "canonical_volume_link": book_url,
            "covers": covers,
            "identifiers": {"isbn": isbn},
            "average_rating": average_rating,
            "ratings_count": ratings_count,
            "maturity_rating": "",
            "print_type": "BOOK",
            "content_version": "",
            "kindle_unlimited": kindle_unlimited_value == "YES",
            "series": series,
            "series_index": series_index,
            "status": status,
            "raw_data": data,  # Store full response for debugging
        }

    async def get_book_details(
        self, title: str, author: str = "", source: str = "google_books"
    ) -> Dict[str, Any]:
        """
        Get book details from specified source with fallback.

        Args:
            title (str): Book title to search for
            author (str, optional): Author name to search for
            source (str): Source to search ('google_books', 'openlibrary', or 'amazon')

        Returns:
            Dict[str, Any]: Book metadata or empty dict if not found
        """
        if source == "google_books":
            result = await self.search_google_books(title, author)
            if not result:
                # Fallback to OpenLibrary
                logger.info(f"Google Books failed for '{title}', trying OpenLibrary")
                result = await self.search_openlibrary(title, author)
        elif source == "amazon":
            result = await self.search_amazon(title, author)
            if not result:
                # Fallback to Google Books
                logger.info(f"Amazon failed for '{title}', trying Google Books")
                result = await self.search_google_books(title, author)
        else:  # openlibrary
            result = await self.search_openlibrary(title, author)
            if not result:
                # Fallback to Google Books
                logger.info(f"OpenLibrary failed for '{title}', trying Google Books")
                result = await self.search_google_books(title, author)

        return result

    async def get_cover_options(
        self,
        title: str,
        author: str = "",
        source: str = "google_books",
        exclude_sources: str = "",
    ) -> List[Dict[str, str]]:
        """
        Get cover options for a book from specified source or all sources.

        Args:
            title (str): Book title to search for
            author (str, optional): Author name to search for
            source (str): Source to search ('google_books', 'openlibrary', 'amazon', or 'all')
            exclude_sources (str, optional): Comma-separated list of sources to exclude

        Returns:
            List[Dict[str, str]]: List of cover options with URLs and source info
        """
        all_covers = []

        # Parse excluded sources
        excluded_sources = set()
        if exclude_sources:
            excluded_sources = {
                s.strip().lower() for s in exclude_sources.split(",") if s.strip()
            }

        # Determine which sources to search based on the source parameter and exclusions
        if source == "all":
            # Search all sources for maximum cover options, but respect exclusions
            all_sources = [
                ("google_books", self.search_google_books),
                ("openlibrary", self.search_openlibrary),
                ("amazon", self.search_amazon if AMAZON_AVAILABLE else None),
            ]
            # Filter out excluded sources
            sources_to_try = [
                (name, func)
                for name, func in all_sources
                if name not in excluded_sources and func is not None
            ]
        elif source == "google_books" and "google_books" not in excluded_sources:
            sources_to_try = [("google_books", self.search_google_books)]
        elif source == "openlibrary" and "openlibrary" not in excluded_sources:
            sources_to_try = [("openlibrary", self.search_openlibrary)]
        elif source == "amazon" and "amazon" not in excluded_sources:
            sources_to_try = [
                ("amazon", self.search_amazon if AMAZON_AVAILABLE else None)
            ]
        else:
            # If the requested source is excluded or unknown, default to google_books (if not excluded)
            if "google_books" not in excluded_sources:
                sources_to_try = [("google_books", self.search_google_books)]
            elif "openlibrary" not in excluded_sources:
                sources_to_try = [("openlibrary", self.search_openlibrary)]
            else:
                # All fast sources excluded, return empty
                logger.warning(
                    f"All fast sources excluded or source '{source}' unknown"
                )
                sources_to_try = []

        for source_name, search_func in sources_to_try:
            if search_func is None:
                continue

            try:
                logger.info(
                    f"Fetching covers from {source_name} for '{title}' by '{author}'"
                )
                details = await search_func(title, author)

                if details and details.get("covers"):
                    # Add covers from this source, avoiding duplicates
                    existing_urls = {cover.get("url") for cover in all_covers}
                    new_covers = []

                    for cover in details["covers"]:
                        if cover.get("url") and cover.get("url") not in existing_urls:
                            new_covers.append(cover)
                            existing_urls.add(cover.get("url"))

                    all_covers.extend(new_covers)
                    logger.info(f"Added {len(new_covers)} covers from {source_name}")
                else:
                    logger.info(f"No covers found from {source_name}")

            except Exception as e:
                logger.warning(f"Error getting covers from {source_name}: {e}")
                continue

        logger.info(
            f"Total covers found: {len(all_covers)} for '{title}' by '{author}'"
        )
        return all_covers

    async def get_cover_options_by_asin(self, asin: str) -> List[Dict[str, str]]:
        """
        Get cover options for a book using Amazon ASIN.

        Args:
            asin (str): Amazon ASIN to search for

        Returns:
            List[Dict[str, str]]: List of cover options with URLs and source info
        """
        if not AMAZON_AVAILABLE:
            logger.warning("Amazon scraping not available for ASIN search")
            return []

        try:
            logger.info(f"Fetching covers from Amazon for ASIN: {asin}")
            details = await self.search_amazon_by_asin(asin)

            if details and details.get("covers"):
                logger.info(f"Found {len(details['covers'])} covers for ASIN {asin}")
                return details["covers"]
            else:
                logger.info(f"No covers found for ASIN {asin}")
                return []

        except Exception as e:
            logger.error(f"Error getting covers for ASIN {asin}: {e}")
            return []

    async def get_cover_options_by_isbn(
        self, isbn: str, source: str = "google_books"
    ) -> List[Dict[str, str]]:
        """
        Get cover options for a book using ISBN.

        Args:
            isbn (str): ISBN to search for
            source (str): Primary source to search (google_books or openlibrary)

        Returns:
            List[Dict[str, str]]: List of cover options with URLs and source info
        """
        all_covers = []

        # For ISBN searches, try Google Books and OpenLibrary (not Amazon)
        sources_to_try = [
            ("google_books", self.search_google_books_by_isbn),
            ("openlibrary", self.search_openlibrary_by_isbn),
        ]

        for source_name, search_func in sources_to_try:
            try:
                logger.info(f"Fetching covers from {source_name} for ISBN: {isbn}")
                details = await search_func(isbn)

                if details and details.get("covers"):
                    # Add covers from this source, avoiding duplicates
                    existing_urls = {cover.get("url") for cover in all_covers}
                    new_covers = []

                    for cover in details["covers"]:
                        if cover.get("url") and cover.get("url") not in existing_urls:
                            new_covers.append(cover)
                            existing_urls.add(cover.get("url"))

                    all_covers.extend(new_covers)
                    logger.info(f"Added {len(new_covers)} covers from {source_name}")
                else:
                    logger.info(f"No covers found from {source_name} for ISBN {isbn}")

            except Exception as e:
                logger.warning(
                    f"Error getting covers from {source_name} for ISBN {isbn}: {e}"
                )
                continue

        logger.info(f"Total covers found: {len(all_covers)} for ISBN {isbn}")
        return all_covers

    async def search_amazon_by_asin(self, asin: str) -> Dict[str, Any]:
        """
        Search Amazon for book metadata using ASIN directly.

        Args:
            asin (str): Amazon ASIN to search for

        Returns:
            Dict[str, Any]: Normalized book metadata or empty dict if not found
        """
        if not AMAZON_AVAILABLE or not initialize_db:
            logger.warning("Amazon scraping not available")
            return {}

        if not asin:
            logger.warning("ASIN is required for Amazon ASIN search")
            return {}

        try:
            # Initialize Amazon database if needed
            initialize_db()

            # Check cache first using ASIN
            cached_result = None
            if get_book_by_asin:
                cached_result = get_book_by_asin(asin)

            if cached_result:
                logger.info(f"Amazon: Found cached result for ASIN {asin}")
                return self._normalize_amazon_response(cached_result)

            # If not in cache, scrape Amazon using ASIN directly
            if scrape_amazon_book_safe_by_asin:
                logger.info(f"Amazon: Loading Book Details for ASIN {asin}")
                scraped_data = await scrape_amazon_book_safe_by_asin(asin)

                if scraped_data and scraped_data.get("ASIN"):
                    # Save to cache
                    if save_book_metadata:
                        save_book_metadata(scraped_data)
                    logger.info(f"Amazon: Successfully scraped and cached ASIN {asin}")
                    return self._normalize_amazon_response(scraped_data)
                else:
                    logger.info(f"Amazon: No results found for ASIN {asin}")
                    return {}
            else:
                logger.warning("Amazon ASIN scraper function not available")
                return {}

        except Exception as e:
            logger.error(f"Error searching Amazon by ASIN {asin}: {str(e)}")
            return {}

    async def search_google_books_by_isbn(self, isbn: str) -> Dict[str, Any]:
        """
        Search Google Books API for book metadata using ISBN.

        Args:
            isbn (str): ISBN to search for

        Returns:
            Dict[str, Any]: Normalized book metadata or empty dict if not found
        """
        if not self.google_books_api_key:
            logger.warning("Google Books API key not configured")
            return {}

        try:
            session = await self.get_session()
            url = "https://www.googleapis.com/books/v1/volumes"

            # Search by ISBN
            params = {
                "q": f"isbn:{isbn}",
                "key": self.google_books_api_key,
                "maxResults": 5,
                "printType": "books",
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = self._normalize_google_books_response(data, "", "")
                    if result:
                        logger.info(f"Google Books found match for ISBN {isbn}")
                        return result
                else:
                    logger.warning(
                        f"Google Books API error for ISBN {isbn}: {response.status}"
                    )

            logger.info(f"Google Books: No matches found for ISBN {isbn}")
            return {}

        except Exception as e:
            logger.error(f"Error searching Google Books by ISBN {isbn}: {str(e)}")
            return {}

    async def search_openlibrary_by_isbn(self, isbn: str) -> Dict[str, Any]:
        """
        Search OpenLibrary API for book metadata using ISBN.

        Args:
            isbn (str): ISBN to search for

        Returns:
            Dict[str, Any]: Normalized book metadata or empty dict if not found
        """
        try:
            session = await self.get_session()
            url = "https://openlibrary.org/search.json"

            # Search by ISBN
            params = {
                "isbn": isbn,
                "limit": 5,
                "fields": "key,title,subtitle,author_name,first_publish_year,publisher,number_of_pages_median,subject,language,cover_i,isbn,lccn,oclc",
            }

            async with session.get(url, params=params) as response:
                if response.status == 200:
                    data = await response.json()
                    result = self._normalize_openlibrary_response(data, "", "")
                    if result:
                        logger.info(f"OpenLibrary found match for ISBN {isbn}")
                        return result
                else:
                    logger.warning(
                        f"OpenLibrary API error for ISBN {isbn}: {response.status}"
                    )

            logger.info(f"OpenLibrary: No matches found for ISBN {isbn}")
            return {}

        except Exception as e:
            logger.error(f"Error searching OpenLibrary by ISBN {isbn}: {str(e)}")
            return {}


# Global instance
book_metadata_service = BookMetadataService()
