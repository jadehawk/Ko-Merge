#!/usr/bin/env python3
"""
Custom server startup script that properly sets the event loop policy
before starting uvicorn. This fixes the Playwright NotImplementedError
on Windows with Python 3.13+.
"""

import sys
import asyncio
import uvicorn

# Fix for Windows + Python 3.13 compatibility with Playwright
# This MUST be set before uvicorn creates its event loop
if sys.platform == "win32" and sys.version_info >= (3, 13):
    print("🔧 Applying Windows + Python 3.13 event loop policy fix for Playwright...")
    asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())


def main():
    """Start the FastAPI server with the correct event loop policy."""
    print("🚀 Starting Ko-Merge API server...")

    # Start uvicorn with the app import string to enable reload
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["app"],
        log_level="info",
    )


if __name__ == "__main__":
    main()
