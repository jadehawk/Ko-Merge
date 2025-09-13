import asyncio
import json
import re
import html
import time
import sys
from datetime import datetime

# Fix for Windows + Python 3.13 compatibility with Playwright
if sys.platform == "win32" and sys.version_info >= (3, 13):
    # Use WindowsProactorEventLoopPolicy for Python 3.13+ on Windows
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

# Try to import Playwright for web scraping, handle gracefully if not installed
try:
    from playwright.async_api import async_playwright
except ImportError:
    print("Warning: Playwright not installed. Amazon scraping will not be available.")
    async_playwright = None


def strip_html_tags(text):
    """
    Remove HTML tags from text content.
    Used to clean up scraped text that may contain HTML markup.
    """
    return re.sub(r"<[^>]+>", "", text).strip()


def build_amazon_query(title, author):
    """
    Build a search query string for Amazon search.
    Cleans the title and author text by removing punctuation and extra spaces,
    then formats it as a quoted search query suitable for Amazon's search URL.

    Args:
        title (str): Book title
        author (str): Author name

    Returns:
        str: URL-encoded search query string
    """

    def clean(text):
        # Remove all non-alphanumeric characters except spaces
        text = re.sub(r"[^\w\s]", "", text)
        # Normalize multiple spaces to single spaces
        return re.sub(r"\s+", " ", text.strip())

    # Create quoted search query and replace spaces with + for URL encoding
    return f'"{clean(title)}" "by {clean(author)}"'.replace(" ", "+")


async def search_amazon_for_asin(page, title, author):
    """
    Search Amazon for a book using title and author to find its ASIN.
    ASIN (Amazon Standard Identification Number) is Amazon's unique product identifier.

    Args:
        page: Playwright page object for browser interaction
        title (str): Book title to search for
        author (str): Author name to search for

    Returns:
        str or None: ASIN if found, None if not found
    """
    # Build the search query and construct Amazon search URL
    query = build_amazon_query(title, author)
    search_url = f"https://www.amazon.com/s?k={query}"
    print(f"[Debug] Amazon search URL: {search_url}")

    # Navigate to search results page
    await page.goto(search_url)
    # Wait for search results to load
    await page.wait_for_selector("div.s-main-slot div[data-asin]")
    # Get all search result items that have ASIN attributes
    results = page.locator("div.s-main-slot div[data-asin]")

    # Loop through search results to find the first valid ASIN
    for i in range(await results.count()):
        item = results.nth(i)
        asin = await item.get_attribute("data-asin")
        if asin:
            return asin

    print("[Info] No ASIN found in search results.")
    return None


# Optional field extraction functions - these run in parallel to gather additional book metadata
async def try_get_series_info(page, result):
    """
    Extract book series information from Amazon product page.
    Looks for series name, book number, and position within the series.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    print("→ try_get_series_info() was called", flush=True)
    start = time.perf_counter()
    try:
        # Look for series information in the rich product information section
        series_card = page.locator(
            "#rich_product_information [data-rpi-attribute-name='book_details-series']"
        )
        if await series_card.count() > 0:
            # Extract series title from the link
            title = await series_card.locator(
                ".rpi-attribute-value a span"
            ).inner_text()
            # Extract position information (e.g., "Book 1 of 5")
            pos = await series_card.locator(".rpi-attribute-label span").inner_text()
            # Parse book number from position text
            match = re.search(r"Book\s+(\d+)", pos)
            result["Series"] = title.strip()
            result["Series Index"] = int(match.group(1)) if match else None
            result["Series Position"] = pos.strip()
    except Exception:
        # Silently fail if series info not found or parsing fails
        pass
    print(f"[Timing] Series Info took {time.perf_counter() - start:.2f}s")


async def try_get_rating(page, result):
    """
    Extract book rating from Amazon product page.
    Tries multiple methods to find the average customer rating.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    try:
        # Try the newer, cleaner innerText-based node first
        new_rating_node = page.locator(
            "#averageCustomerReviews .a-size-base.a-color-base"
        )
        if await new_rating_node.count() > 0:
            rating_text = (await new_rating_node.first.inner_text()).strip()
            # Validate that the text matches a rating pattern (e.g., "4.5")
            if re.match(r"\d+(\.\d+)?", rating_text):
                result["Average Rating"] = rating_text
                print(f"[Debug] ✅ Rating found via new node: {rating_text}")
                return

        # Fallback to legacy method using title attribute
        legacy = page.locator("#acrPopover")
        if await legacy.count() > 0:
            title = await legacy.get_attribute("title")
            if title:
                # Extract rating from title like "4.5 out of 5 stars"
                result["Average Rating"] = title.split(" ")[0]
                print(f"[Debug] ✅ Rating found via legacy: {title}")
    except Exception as e:
        print(f"[Error] try_get_rating failed: {e}")


async def try_get_review_count(page, result):
    """
    Extract the number of customer reviews from Amazon product page.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    try:
        # Look for review count text (e.g., "1,234 ratings")
        locator = page.locator("#acrCustomerReviewText").first
        if await locator.count() > 0:
            text = await locator.inner_text()
            # Extract numbers with possible commas
            match = re.search(r"\d[\d,]*", text)
            if match:
                # Remove commas from the number
                result["Review Count"] = match.group().replace(",", "")
                print(f"[Debug] ✅ Review count found: {result['Review Count']}")

    except Exception as e:
        print(f"[Error] try_get_review_count failed: {e}")


async def try_get_genres(page, result):
    """
    Extract book genres/categories from Amazon product page.
    Parses the bestseller rank information to extract category names.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    print("→ try_get_genre() was called", flush=True)
    start = time.perf_counter()
    try:
        genres = []
        # Look for bestseller rank information which contains categories
        nodes = page.locator(
            "#detailBullets_feature_div li span.a-list-item ul.zg_hrsr li"
        )
        for i in range(await nodes.count()):
            raw = await nodes.nth(i).inner_text()
            # Clean: remove rank number and isolate category name
            # Text format: "#1,234 in Science Fiction & Fantasy"
            match = re.search(r"in\s+(.*)", raw)
            if match:
                clean = match.group(1)
            else:
                clean = raw
            # Remove parenthetical information like "(Books)"
            clean = re.sub(r"\s+\(.*?\)$", "", clean).strip()
            genres.append(clean)

        # Remove duplicates while preserving order
        seen = set()
        result["Genres"] = [g for g in genres if not (g in seen or seen.add(g))]
    except Exception:
        # Silently fail if genre extraction fails
        pass
    print(f"[Timing] genre took {time.perf_counter() - start:.2f}s")


async def try_get_description(page, result):
    """
    Extract book description from Amazon product page.
    Looks for the expandable content section that contains the book synopsis.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    print("→ try_get_description() was called", flush=True)
    start = time.perf_counter()
    try:
        # Get the HTML content from the expandable description section
        html_raw = await page.inner_html("div.a-expander-content")
        # Strip HTML tags to get clean text
        result["Book Description"] = re.sub("<[^<]+?>", "", html_raw).strip()
    except Exception:
        # Silently fail if description not found
        pass
    print(f"[Timing] description took {time.perf_counter() - start:.2f}s")


async def try_get_metadata(page, result):
    """
    Extract detailed book metadata from Amazon product page.
    Scrapes publication details, ISBN, publisher info, etc. from multiple page sections.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    print("→ try_get_metadata() was called", flush=True)
    start = time.perf_counter()
    metadata = {}

    try:
        # Extract from rich product information cards (newer Amazon layout)
        cards = page.locator("#rich_product_information .rpi-attribute-content")
        for i in range(await cards.count()):
            card = cards.nth(i)
            # Get the label (e.g., "Publisher", "Publication date")
            label = (
                await card.locator(".rpi-attribute-label span").inner_text()
            ).strip()
            # Get the value, could be in span or link
            val_node = card.locator(".rpi-attribute-value span, .rpi-attribute-value a")
            value = (await val_node.inner_text()).strip()
            metadata[label] = value
    except Exception:
        # Silently continue if rich product info not available
        pass

    try:
        # Extract from detail bullets section (older Amazon layout)
        bullets = page.locator("#detailBullets_feature_div li span.a-list-item")
        for i in range(await bullets.count()):
            item = bullets.nth(i)
            # Look for bold labels (e.g., "Publisher:")
            label_span = item.locator("span.a-text-bold")
            if await label_span.count() == 0:
                continue
            # Extract label and value from "Label: Value" format
            label = (await label_span.inner_text()).split(":")[0].strip()
            value = (await item.inner_text()).split(":", 1)[-1].strip()
            metadata[label] = value
    except Exception:
        # Silently continue if detail bullets not available
        pass

    print(f"[Timing] metadata took {time.perf_counter() - start:.2f}s")

    # Map Amazon's field names to our standardized field names
    field_map = {
        "Print length": "Print Length",
        "Publication date": "Publication Date",
        "Publisher": "Publisher",
        "ISBN-13": "ISBN",
        "ISBN-10": "ISBN",
        "Edition": "Edition",
        "Language": "Language",
        "File size": "File Size",
    }

    # Apply the field mapping and only update empty fields
    for label, value in metadata.items():
        field = field_map.get(label)
        if field and result.get(field) in (None, ""):
            result[field] = value

    # Determine release status based on publication date
    pub_date = result.get("Publication Date")
    if pub_date:
        try:
            # Parse date in format "Month Day, Year"
            pub_dt = datetime.strptime(pub_date, "%B %d, %Y")
            if pub_dt > datetime.now():
                result["Status"] = "Pre-Release"
            else:
                result["Status"] = "Released"
        except Exception:
            # Silently fail if date parsing fails
            pass


async def scrape_optional_fields(page, result):
    """
    Coordinate the extraction of optional metadata fields in parallel.
    Runs multiple extraction functions concurrently with a timeout to prevent hanging.

    Args:
        page: Playwright page object
        result (dict): Dictionary to store extracted data
    """
    print("→ scrape_optional_fields started", flush=True)
    # List of async functions to run in parallel
    tasks = [
        try_get_rating(page, result),
        try_get_review_count(page, result),
        try_get_genres(page, result),
        try_get_description(page, result),
        try_get_metadata(page, result),
    ]
    try:
        # Run all tasks concurrently with a 25-second timeout
        await asyncio.wait_for(asyncio.gather(*tasks), timeout=25)
    except asyncio.TimeoutError:
        print("[Timeout] Optional field scraping capped at 25 seconds.")


async def scrape_amazon_book(asin=None, title=None, author=None):
    """
    Main function to scrape book metadata from Amazon.
    Can work with either an ASIN directly or search using title/author.

    Args:
        asin (str, optional): Amazon ASIN to scrape directly
        title (str, optional): Book title for search-based scraping
        author (str, optional): Author name for search-based scraping

    Returns:
        dict or None: Dictionary containing book metadata, or None if scraping failed

    Raises:
        ValueError: If neither ASIN nor title/author are provided
        RuntimeError: If Playwright is not available
    """
    # Validate input parameters
    if not asin and not (title and author):
        raise ValueError("Provide either ASIN or both title and author.")

    # Check if Playwright is available
    if async_playwright is None:
        raise RuntimeError("Playwright not available. Cannot scrape Amazon.")

    # Force the correct event loop policy for this specific operation
    if sys.platform == "win32" and sys.version_info >= (3, 13):
        # Ensure the policy is set
        if not isinstance(
            asyncio.get_event_loop_policy(), asyncio.WindowsProactorEventLoopPolicy
        ):
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Amazon product URL template
    url_template = "https://www.amazon.com/dp/{asin}"

    # Initialize result dictionary with all possible fields
    result = {
        "ASIN": asin,
        "Title": None,
        "Author": None,
        "Cover URL": None,
        "Book URL": None,
        "isKindleUnlimited": "NO",
        "ISBN": None,
        "Genres": [],
        "Print Length": None,
        "Series": None,
        "Series Index": None,
        "Series Position": None,
        "Publisher": None,
        "Publication Date": None,
        "Edition": None,
        "Language": None,
        "File Size": None,
        "Average Rating": None,
        "Review Count": None,
        "Status": None,
        "Book Description": None,
    }

    # Start browser automation
    async with async_playwright() as p:
        browser = await p.firefox.launch(
            headless=True
        )  # Changed to headless for server use
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/115.0"
            )
        )
        page = await context.new_page()

        if not asin:
            print("[Info] ASIN not provided. Searching Amazon...")
            try:
                asin = await asyncio.wait_for(
                    search_amazon_for_asin(page, title, author), timeout=10
                )
            except asyncio.TimeoutError:
                print("[Timeout] Amazon search took too long—skipping.")
                await browser.close()
                return None
            if not asin:
                print("[Error] ASIN not found for provided title and author.")
                await browser.close()
                return None

        result["ASIN"] = asin
        result["Book URL"] = url_template.format(asin=asin)
        await page.goto(result["Book URL"], timeout=60000)
        start = time.perf_counter()
        try:
            result["Title"] = (await page.locator("#productTitle").inner_text()).strip()
        except Exception:
            # Fallback: JSON extraction
            try:
                script_blob = await page.evaluate("""() => {
                    return [...document.querySelectorAll('script')].find(s => s.textContent.includes('jQuery.parseJSON'))?.textContent || '';
                }""")
                match = re.search(r"jQuery\.parseJSON\('(.+?)'\)", script_blob)
                if match:
                    parsed = json.loads(html.unescape(match.group(1)))
                    result["Title"] = parsed.get("title")
                    result["ASIN"] = (
                        parsed.get("mediaAsin") or parsed.get("parentAsin") or asin
                    )
            except Exception:
                pass
        print(f"[Timing] Title took {time.perf_counter() - start:.2f}s")

        try:
            result["Author"] = (
                await page.locator(".author a").first.inner_text()
            ).strip()
        except Exception:
            pass

        # Try to get the best quality cover image, prioritizing book covers over audiobook covers
        try:
            img = page.locator("#landingImage")

            # First try to get high-resolution image
            cover_url = await img.get_attribute("data-old-hires")
            if not cover_url:
                cover_url = await img.get_attribute("src")

            # Check if this is an audiobook cover by examining the image dimensions
            # Audiobook covers have max-width and max-height of 250px
            is_audiobook_cover = False
            try:
                # Check the specific XPath for audiobook detection
                audiobook_element = page.locator(
                    "xpath=/html/body/div[1]/div/div/div[8]/div/div[3]/div[1]/div[1]/div/div/div/div[1]/div[1]/ul/li[1]/span/span/div"
                )
                if await audiobook_element.count() > 0:
                    # Get the computed style of the element
                    style = await audiobook_element.first.get_attribute("style")
                    if style:
                        # Check if max-width and max-height are 250px (audiobook indicator)
                        if "max-width: 250px" in style and "max-height: 250px" in style:
                            is_audiobook_cover = True
                            print(
                                "[Debug] Detected audiobook cover via 250px dimensions"
                            )
                        else:
                            print(f"[Debug] Element style: {style}")

                    # Alternative: check computed styles via JavaScript
                    if not is_audiobook_cover:
                        try:
                            dimensions = await page.evaluate("""
                                () => {
                                    const element = document.evaluate(
                                        '/html/body/div[1]/div/div/div[8]/div/div[3]/div[1]/div[1]/div/div/div/div[1]/div[1]/ul/li[1]/span/span/div',
                                        document,
                                        null,
                                        XPathResult.FIRST_ORDERED_NODE_TYPE,
                                        null
                                    ).singleNodeValue;
                                    
                                    if (element) {
                                        const computedStyle = window.getComputedStyle(element);
                                        return {
                                            maxWidth: computedStyle.maxWidth,
                                            maxHeight: computedStyle.maxHeight,
                                            width: computedStyle.width,
                                            height: computedStyle.height
                                        };
                                    }
                                    return null;
                                }
                            """)

                            if dimensions:
                                print(f"[Debug] Element dimensions: {dimensions}")
                                if (
                                    dimensions.get("maxWidth") == "250px"
                                    and dimensions.get("maxHeight") == "250px"
                                ):
                                    is_audiobook_cover = True
                                    print(
                                        "[Debug] Detected audiobook cover via computed style dimensions"
                                    )
                        except Exception as e:
                            print(f"[Debug] Error checking computed dimensions: {e}")
            except Exception as e:
                print(f"[Debug] Error checking audiobook element: {e}")

            # If we detected an audiobook cover, try to find the book cover instead
            if is_audiobook_cover:
                print("[Debug] Audiobook cover detected, looking for book cover...")

                # Try to find Kindle edition or other book formats
                try:
                    # Look for format selector buttons
                    format_buttons = page.locator("#tmmSwatches .a-button-text")
                    button_count = await format_buttons.count()

                    for i in range(button_count):
                        button = format_buttons.nth(i)
                        button_text = await button.inner_text()

                        # Prioritize Kindle, Paperback, Hardcover over Audible
                        if any(
                            format_type in button_text.lower()
                            for format_type in [
                                "kindle",
                                "paperback",
                                "hardcover",
                                "mass market",
                            ]
                        ):
                            print(f"[Debug] Found {button_text} format, clicking...")
                            await button.click()
                            await page.wait_for_timeout(2000)  # Wait for page to update

                            # Get the new cover image
                            new_img = page.locator("#landingImage")
                            new_cover_url = await new_img.get_attribute(
                                "data-old-hires"
                            ) or await new_img.get_attribute("src")

                            if new_cover_url and new_cover_url != cover_url:
                                print(
                                    f"[Debug] ✅ Found better cover from {button_text} format"
                                )
                                cover_url = new_cover_url

                                # Verify the new cover is not also an audiobook cover
                                try:
                                    new_dimensions = await page.evaluate("""
                                        () => {
                                            const element = document.evaluate(
                                                '/html/body/div[1]/div/div/div[8]/div/div[3]/div[1]/div[1]/div/div/div/div[1]/div[1]/ul/li[1]/span/span/div',
                                                document,
                                                null,
                                                XPathResult.FIRST_ORDERED_NODE_TYPE,
                                                null
                                            ).singleNodeValue;
                                            
                                            if (element) {
                                                const computedStyle = window.getComputedStyle(element);
                                                return {
                                                    maxWidth: computedStyle.maxWidth,
                                                    maxHeight: computedStyle.maxHeight
                                                };
                                            }
                                            return null;
                                        }
                                    """)

                                    if new_dimensions:
                                        if (
                                            new_dimensions.get("maxWidth") != "250px"
                                            or new_dimensions.get("maxHeight")
                                            != "250px"
                                        ):
                                            print(
                                                f"[Debug] ✅ Confirmed book cover (dimensions: {new_dimensions})"
                                            )
                                            break
                                        else:
                                            print(
                                                "[Debug] Still audiobook cover, continuing search..."
                                            )
                                    else:
                                        # If we can't check dimensions, assume it's better
                                        print(
                                            f"[Debug] ✅ Using {button_text} cover (dimensions check failed)"
                                        )
                                        break
                                except Exception as e:
                                    print(
                                        f"[Debug] Error verifying new cover dimensions: {e}"
                                    )
                                    # If verification fails, use the new cover anyway
                                    break
                except Exception as e:
                    print(f"[Debug] Error trying to find book format: {e}")
            else:
                print("[Debug] Book cover detected (not audiobook)")

            result["Cover URL"] = cover_url
        except Exception as e:
            print(f"[Error] Error getting cover image: {e}")
        print(f"[Timing] Author took {time.perf_counter() - start:.2f}s")

        try:
            ku_icon_count = await page.locator(
                "i[aria-label='kindle unlimited']"
            ).count()
            kindle_price = await page.locator(
                "#tmm-grid-swatch-KINDLE .slot-price"
            ).inner_text()
            if ku_icon_count > 0 or "$0.00" in kindle_price:
                result["isKindleUnlimited"] = "YES"
        except Exception:
            pass
        print(f"[Timing] KU took {time.perf_counter() - start:.2f}s")

        try:
            await asyncio.wait_for(try_get_series_info(page, result), timeout=5)
            print("[Timing] Series block completed")
        except asyncio.TimeoutError:
            print("[Timing] Series block timed out after 5s")

        try:
            await scrape_optional_fields(page, result)
        finally:
            await browser.close()

        return result
