#!/usr/bin/env python3
"""
Playwright wrapper that runs in a separate process with the correct event loop policy.
This ensures Playwright works correctly on Windows with Python 3.13+.
"""

import asyncio
import sys
import multiprocessing
from typing import Optional, Dict, Any


def _run_playwright_in_subprocess(
    title: Optional[str] = None,
    author: Optional[str] = None,
    asin: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """
    Run Playwright scraping in a subprocess with the correct event loop policy.
    This function runs in a separate process to avoid event loop conflicts.
    """
    # Set the correct event loop policy for this subprocess
    if sys.platform == "win32" and sys.version_info >= (3, 13):
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())

    # Import the scraper function inside the subprocess
    from .amazon_scraper import scrape_amazon_book

    # Create a new event loop for this subprocess
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    try:
        # Run the scraping operation with appropriate parameters
        if asin:
            result = loop.run_until_complete(scrape_amazon_book(asin=asin))
        else:
            result = loop.run_until_complete(
                scrape_amazon_book(title=title, author=author)
            )
        return result
    except Exception as e:
        print(f"Subprocess scraping error: {e}")
        return None
    finally:
        loop.close()


async def scrape_amazon_book_safe(title: str, author: str) -> Optional[Dict[str, Any]]:
    """
    Safe wrapper for Amazon scraping that uses a subprocess to avoid event loop issues.

    Args:
        title (str): Book title to search for
        author (str): Author name to search for

    Returns:
        Optional[Dict[str, Any]]: Book metadata or None if scraping failed
    """
    try:
        # Use ProcessPoolExecutor to run Playwright in a separate process
        loop = asyncio.get_running_loop()

        # Create a process pool with a single worker
        with multiprocessing.Pool(processes=1) as pool:
            # Submit the task to the subprocess
            result = await loop.run_in_executor(
                None,
                lambda: pool.apply(
                    _run_playwright_in_subprocess,
                    (),
                    {"title": title, "author": author},
                ),
            )
            return result

    except Exception as e:
        print(f"Safe scraping wrapper error: {e}")
        return None


async def scrape_amazon_book_safe_by_asin(asin: str) -> Optional[Dict[str, Any]]:
    """
    Safe wrapper for Amazon scraping by ASIN that uses a subprocess to avoid event loop issues.

    Args:
        asin (str): Amazon ASIN to search for

    Returns:
        Optional[Dict[str, Any]]: Book metadata or None if scraping failed
    """
    try:
        # Use ProcessPoolExecutor to run Playwright in a separate process
        loop = asyncio.get_running_loop()

        # Create a process pool with a single worker
        with multiprocessing.Pool(processes=1) as pool:
            # Submit the task to the subprocess
            result = await loop.run_in_executor(
                None,
                lambda: pool.apply(_run_playwright_in_subprocess, (), {"asin": asin}),
            )
            return result

    except Exception as e:
        print(f"Safe ASIN scraping wrapper error: {e}")
        return None
