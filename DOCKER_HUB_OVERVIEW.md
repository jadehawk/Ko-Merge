# Ko-Merge - KOReader Statistics Database Merger

A modern, containerized KOReader Statistics Database Merger built with React + TypeScript frontend and FastAPI + UV backend.

## 🚀 Quick Start

```bash
# Basic deployment
docker run -d \
  --name ko-merge \
  -p 3000:8000 \
  -v ./data:/app/data \
  jadehawk/ko-merge:latest

# With environment variables
docker run -d \
  --name ko-merge \
  -p 3000:8000 \
  -v ./data:/app/data \
  -e PUBLIC_BASE_URL=https://yourdomain.com \
  -e USE_SUBFOLDER=true \
  -e PUBLIC_SUBFOLDER_PATH=ko-merge \
  -e GOOGLE_BOOKS_API_KEY=your_api_key \
  jadehawk/ko-merge:latest
```

## 🎯 Features

- **Modern UI**: Library-style grid layout with book covers and prominent MD5 display
- **Enhanced Book Details**: Rich metadata from Google Books, OpenLibrary, and Amazon APIs
- **Amazon Integration**: Full Amazon book scraping with duplicate request prevention
- **Smart Caching**: Global intelligent metadata caching with request deduplication
- **Flexible Deployment**: Supports both subdomain and subfolder deployment
- **Docker Ready**: Production-ready containers with Unraid compatibility
- **Persistent Preferences**: Cover choices saved across sessions without user accounts

## ⚠️ Important: Container Startup

**The optimized Docker image includes all dependencies pre-installed for fast startup:**

- **Container startup**: ~10-30 seconds (all dependencies pre-installed)
- **Full functionality**: All features including Amazon scraping available immediately
- **Optimized image**: Dependencies and browsers pre-installed during build

**🚀 Fast startup - no waiting for dependency installation!**

## 🔧 Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_BASE_URL` | - | Base URL for the application |
| `PUBLIC_SUBFOLDER_PATH` | - | Subfolder path for deployment |
| `USE_SUBFOLDER` | `false` | Enable subfolder deployment mode |
| `GOOGLE_BOOKS_API_KEY` | - | Google Books API key for enhanced metadata (falls back to OpenLibrary if not set) |
| `AMAZON_SCRAPING_ENABLED` | `true` | Enable/disable Amazon book scraping |
| `PUID` | `99` | User ID (Unraid default) |
| `PGID` | `100` | Group ID (Unraid default) |

## 🐳 Docker Compose Example

```yaml
version: '3.8'
services:
  ko-merge:
    image: jadehawk/ko-merge:latest
    container_name: ko-merge
    ports:
      - "3000:8000"
    volumes:
      - ./data:/app/data
    environment:
      - PUBLIC_BASE_URL=https://yourdomain.com
      - USE_SUBFOLDER=true
      - PUBLIC_SUBFOLDER_PATH=ko-merge
      - GOOGLE_BOOKS_API_KEY=your_api_key_here
      - PUID=99
      - PGID=100
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "python", "-c", "import requests; requests.get('http://localhost:8000/', timeout=5)"]
      interval: 30s
      timeout: 10s
      retries: 3
      start_period: 60s
```

## 📁 Volume Mounts

- `/app/data` - Persistent data storage for databases, covers, and preferences

## 🌐 Access Points

- **Web Interface**: `http://localhost:3000` (or your configured domain)
- **API Documentation**: `http://localhost:3000/api/docs`
- **Health Check**: `http://localhost:3000/health`

## 📖 API Configuration & Fallbacks

### Google Books API (Optional)

- **Enhanced source** for book covers and metadata when API key is provided
- Provides rich metadata including ratings, descriptions, and categories
- **Free tier**: 1,000 requests/day
- **Smart Detection**: App automatically detects if API key is available

### OpenLibrary API (Default)

- **Primary source** when Google Books API key is not configured
- No API key required - works out of the box
- Provides basic metadata and cover images
- **Reliable fallback**: Always available as backup source

### Amazon Scraping (Optional)

- **High-quality covers** but slower (web scraping)
- Enabled by default but can be disabled
- Includes duplicate request prevention and caching
- **Note**: Takes longer due to browser automation

## 🔍 Supported Architectures

- `linux/amd64`
- `linux/arm64`

## 📚 Usage

1. Upload your KOReader statistics database
2. Review detected books with covers and metadata
3. Select books to merge (duplicates with different MD5 hashes)
4. Execute merge operations
5. Download the cleaned database

## 🛡️ Security Features

- Non-root user execution
- Read-only mounts where appropriate
- Security headers in Nginx
- CORS configuration
- No authentication required (stateless design)

## 🏷️ Tags

- `latest` - Latest stable release
- `v1.x.x` - Specific version releases
- `develop` - Development builds (unstable)

## ⚠️ Important Notes

- **Backup your database** before using this tool
- This is a **weekend project** with **heavy AI-generated code**
- **Use at your own risk** - always test with copies first
- Designed for **KOReader statistics databases** only

## 🔗 Links

- **GitHub Repository**: <https://github.com/jadehawk/Ko-Merge>
- **Documentation**: <https://github.com/jadehawk/Ko-Merge#readme>
- **Issues**: <https://github.com/jadehawk/Ko-Merge/issues>

---

Made with ❤️ by [Jadehawk](https://techy-notes.com/) | Use at your own RISK!
