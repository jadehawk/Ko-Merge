# Ko-Merge v2.0.0 Release Notes 🚀

## Major Features & Improvements

### 🎨 Modern UI Overhaul

- **Library-style grid layout** with book covers and prominent MD5 display
- **Enhanced book details** with rich metadata from Google Books, OpenLibrary, and Amazon APIs
- **Tailwind CSS v4+** with dark mode support and responsive design
- **Mobile-optimized** responsive layout (1-4+ columns based on screen size)

### 🔍 Enhanced Book Discovery

- **Multi-source cover fetching** from Google Books, OpenLibrary, and Amazon
- **On-demand cover search** with manual "Search for Covers" button
- **Source-specific badges** (GB, OL, AZ) for cover identification
- **Smart fallback system** ensuring comprehensive coverage

### 🏪 Amazon Integration

- **Full Amazon book scraping** with Playwright browser automation
- **Duplicate request prevention** with global deduplication system
- **ASIN-based search** for Amazon-specific book identification
- **Windows + Python 3.13 compatibility** fixes

### 💾 Unified Storage System

- **Local cover storage** with automatic cleanup and session protection
- **Persistent preferences** - cover choices saved across sessions without user accounts
- **SHA256-based book identification** using title+author (no MD5 dependency)
- **Automated cleanup service** running every 2 hours

### 🚀 Production Ready

- **Docker optimization** with pre-built dependencies for fast startup (~10-30 seconds)
- **Unraid compatibility** with configurable PUID/PGID
- **Flexible deployment** supporting both subdomain and subfolder configurations
- **Health checks** and monitoring for production environments

### ⚡ Performance & Caching

- **Global intelligent caching** with request deduplication
- **24-hour metadata caching** minimizing API usage
- **UV integration** for fast Python dependency management
- **Batch cover retrieval** endpoints for efficient loading

### 🛠️ Developer Experience

- **Windows development automation** with `start-dev.bat`
- **Custom server startup** with proper event loop handling
- **Enhanced API documentation** at `/docs` endpoint
- **TypeScript integration** with comprehensive type definitions

## Technical Improvements

### Backend (FastAPI + UV)

- Fixed Playwright compatibility issues on Windows + Python 3.13
- Implemented session-based merge operations with temporary file handling
- Added global caching system with title/author normalization
- Enhanced error handling and logging throughout

### Frontend (React + TypeScript)

- Complete UI redesign with modern component architecture
- Implemented efficient state management for book operations
- Added comprehensive loading states and user feedback
- Mobile-first responsive design approach

### Infrastructure

- Multi-stage Docker builds for optimized production images
- Pre-installed browser dependencies for immediate functionality
- Environment-based configuration system
- Comprehensive deployment documentation

## Breaking Changes

- UI completely redesigned - previous interface no longer available
- API endpoints restructured for better organization
- Configuration format updated for flexible deployment options

## Migration Notes

- Existing databases remain compatible
- Cover preferences will need to be re-selected due to new storage system
- Environment variables updated - see documentation for new format

## What's Next

This release establishes Ko-Merge as a production-ready application with modern UI/UX and robust backend infrastructure. Future releases will focus on additional metadata sources and advanced merge capabilities.

---

**Full Changelog**: [View on GitHub](https://github.com/jadehawk/Ko-Merge/compare/v1.0.0...v2.0.0)
**Docker Image**: `jadehawk/ko-merge:v2.0.0`
