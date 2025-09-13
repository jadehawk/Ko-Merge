[![Docker Image CI](https://github.com/jadehawk/Ko-Merge/actions/workflows/docker-image.yml/badge.svg)](https://github.com/jadehawk/Ko-Merge/actions/workflows/docker-image.yml)
# Ko-Merge

![Ko-Merge Logo](logo.png)

KOReader Statistics Database Merger with Modern UI

## 🚀 Features

- **Modern UI**: Library-style grid layout with book covers and prominent MD5 display
- **Download Counter**: Database-stored counter showing successful database fixes in header
- **Enhanced Book Details**: Rich metadata from Google Books, OpenLibrary, and Amazon APIs
- **Amazon Integration**: Full Amazon book scraping with duplicate request prevention
- **Unified Cover Storage**: Local image storage with automatic cleanup and session protection
- **On-Demand Cover Search**: Manual "Search for Covers" button instead of automatic loading
- **Smart Caching**: Global intelligent metadata caching with request deduplication
- **Windows + Python 3.13 Compatible**: Fixed Playwright compatibility issues
- **Tailwind CSS v4+**: Dark mode support with responsive design
- **Docker Ready**: Production-ready containers with Unraid compatibility
- **UV Integration**: Fast Python dependency management
- **Persistent Preferences**: Cover choices saved across sessions without user accounts
- **Flexible Deployment**: Supports both subdomain and subfolder deployment
- **Windows Development**: Automated development environment setup
- **Subfolder Support**: Full support for deployment at custom paths like `/ko-merge`

## 📋 Requirements

### Development

- **Python 3.13+** with [UV](https://docs.astral.sh/uv/getting-started/installation/)
- **Node.js 20+** with npm
- **Windows 11** (for development automation)
- **Playwright Browser Dependencies** (automatically handled in Docker)

### Production

- **Docker** and **Docker Compose**
- **Unraid** (optional, but optimized for it)

## 🛠️ Quick Start

### Using Pre-built Docker Image (Recommended)

The easiest way to run Ko-Merge is using the pre-built Docker image from Docker Hub:

1. **Create docker-compose.yml**

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
         - PUBLIC_BASE_URL=http://localhost:3000
         - USE_SUBFOLDER=false
       restart: unless-stopped
   ```

2. **Start the application**

   ```bash
   docker-compose up -d
   ```

3. **Access the application**
   - Application: <http://localhost:3000>
   - API Documentation: <http://localhost:3000/docs>

### Building from Source

If you want to build the image yourself:

1. **Clone the repository**

   ```bash
   git clone https://github.com/jadehawk/Ko-Merge.git
   cd Ko-Merge
   ```

2. **Build and run**

   ```bash
   # Build the image
   docker build -t ko-merge-local .
   
   # Run with docker-compose (update image name in docker-compose.yml)
   docker-compose up -d
   ```

### Development Setup

For development, see the development documentation in the repository.

#### ⚠️ Important: Container Startup

**The optimized Docker image includes all dependencies pre-installed for fast startup:**

- **Container startup**: ~10-30 seconds (all dependencies pre-installed)
- **Full functionality**: All features including Amazon scraping available immediately
- **Optimized image**: Dependencies and browsers pre-installed during build

**Benefits:**

- **Fast startup**: No dependency installation during container startup
- **Reliable deployments**: All dependencies pre-tested and cached
- **Better scaling**: New container instances start immediately
- **Production ready**: Optimized for production deployments

## 🏗️ Architecture

### Backend (FastAPI + UV)

- **Fast dependency management** with UV
- **SQLite database processing** for KOReader statistics
- **Session-based merge operations** with temporary file handling
- **Amazon scraping integration** with Playwright and request deduplication
- **Unified cover storage system** with local image downloading and serving
- **Automated cleanup service** running every 2 hours with session protection
- **SHA256-based book identification** using title+author (no MD5 dependency)
- **Global caching system** with title/author normalization
- **Windows + Python 3.13 compatibility** with proper event loop policies
- **Health checks** and monitoring

### Frontend (React + TypeScript + Tailwind)

- **Library-style grid layout** for book visualization
- **Prominent MD5 display** for merge selection assistance
- **Multi-source cover fetching** from Google Books, OpenLibrary, and Amazon
- **Source-specific badges** (GB, OL, AZ) for cover identification
- **Enhanced loading states** with clear user feedback
- **Responsive design** with mobile support
- **Dark mode** optimized interface

### Docker Configuration

- **Multi-stage builds** for optimized production images
- **Playwright browser support** with all required system dependencies
- **Unraid compatibility** with configurable PUID/PGID
- **Custom server startup** with proper event loop handling
- **Health checks** for service monitoring
- **Volume management** for persistent data
- **Environment-based configuration**

## 📁 Project Structure

```text
Ko-Mergev2/
├── backend/                 # FastAPI backend
│   ├── app/
│   │   ├── main.py         # Main application with all endpoints
│   │   ├── services/
│   │   │   ├── book_metadata.py    # Multi-source metadata service
│   │   │   ├── amazon_scraper.py   # Playwright-based Amazon scraper
│   │   │   └── amazon_cachedb.py   # Global caching system
│   │   └── ...
│   ├── start_server.py     # Custom server startup with event loop fixes
│   ├── Dockerfile          # Production backend container with Playwright
│   ├── entrypoint.sh       # Unraid-compatible entrypoint
│   └── pyproject.toml      # UV dependencies
├── frontend/               # React frontend
│   ├── src/
│   │   ├── components/
│   │   │   ├── BookList.tsx      # Main book grid component
│   │   │   ├── BookCover.tsx     # Book cover fetching component
│   │   │   └── ...
│   │   ├── types/index.ts        # TypeScript interfaces
│   │   └── index.css            # Tailwind CSS with custom styles
│   ├── Dockerfile               # Production frontend container
│   ├── nginx.conf.template      # Nginx configuration template
│   └── tailwind.config.js       # Tailwind CSS configuration
├── docker-compose.yml      # Production deployment
├── .env.example           # Environment configuration template
├── start-dev.bat          # Windows development automation
└── README.md             # This file
```

## 🔧 Configuration

### Environment Variables

#### Flexible Deployment Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PUBLIC_BASE_URL` | - | Base URL for the application (auto-adds https:// if no protocol) |
| `PUBLIC_SUBFOLDER_PATH` | - | Subfolder path (auto-adds leading slash, removes trailing slash) |
| `USE_SUBFOLDER` | `false` | Enable subfolder deployment mode |

#### System Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `PUID` | `99` | User ID (Unraid default) |
| `PGID` | `100` | Group ID (Unraid default) |
| `BACKEND_PORT` | `8000` | Backend service port |
| `FRONTEND_PORT` | `3000` | Frontend service port |
| `DATA_PATH` | `./data` | Data storage path |

#### API Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `GOOGLE_BOOKS_API_KEY` | - | **Highly recommended** - Google Books API key for high-quality covers and rich metadata |
| `CLEANUP_INTERVAL_MINUTES` | `120` | Cleanup service interval (in minutes) |

### Google Books API Setup

1. **Get API Key** (Optional but recommended)
   - Visit [Google Cloud Console](https://console.cloud.google.com/)
   - Create a new project or select existing
   - Enable the "Books API"
   - Create credentials (API Key)
   - Add to `.env` file: `GOOGLE_BOOKS_API_KEY=your_api_key_here`

2. **API Benefits**
   - Rich book metadata (ratings, descriptions, genres)
   - Multiple cover options and sizes
   - Publication details and preview links
   - Higher quality covers compared to OpenLibrary

3. **Usage Limits**
   - **Free Tier**: 1,000 requests/day
   - **Caching**: 24-hour metadata caching minimizes API usage

4. **Automatic Fallback Behavior**
   - **With API Key**: Uses Google Books as primary source, falls back to OpenLibrary if needed
   - **Without API Key**: Uses OpenLibrary as primary source (no API key required)
   - **Smart Detection**: App automatically detects API availability and chooses best source

### Deployment Examples

#### 1. Root Domain Deployment

Deploy Ko-Merge at the root of your domain (<https://mydomain.com>):

```env
# .env configuration
PUBLIC_BASE_URL=https://mydomain.com
USE_SUBFOLDER=false
PUBLIC_SUBFOLDER_PATH=
```

#### 2. Subfolder Deployment

Deploy Ko-Merge in a subfolder (<https://mydomain.com/ko-merge>):

```env
# .env configuration
PUBLIC_BASE_URL=https://mydomain.com
USE_SUBFOLDER=true
PUBLIC_SUBFOLDER_PATH=ko-merge
```

#### 3. Custom Port Deployment

Deploy on a custom port (<http://192.168.1.100:5173>):

```env
# .env configuration
PUBLIC_BASE_URL=http://192.168.1.100:5173
USE_SUBFOLDER=false
PUBLIC_SUBFOLDER_PATH=
```

#### 4. Traefik Proxy Setup (Labels)

For use with Traefik reverse proxy using container labels:

```env
# .env configuration
PUBLIC_BASE_URL=https://example.com
USE_SUBFOLDER=true
PUBLIC_SUBFOLDER_PATH=ko-merge

# Traefik labels (in docker-compose.yml)
labels:
  - "traefik.http.routers.ko-merge.rule=Host(`example.com`) && PathPrefix(`/ko-merge`)"
  - "traefik.http.routers.ko-merge.middlewares=ko-merge-stripprefix"
  - "traefik.http.middlewares.ko-merge-stripprefix.stripprefix.prefixes=/ko-merge"
```

#### 5. Traefik Proxy Setup (Static Configuration)

For use with Traefik static configuration files:

```env
# .env configuration
PUBLIC_BASE_URL=https://example.com
USE_SUBFOLDER=true
PUBLIC_SUBFOLDER_PATH=ko-merge
```

```yaml
# traefik/dynamic/ko-merge.yml
http:
  routers:
    ko-merge:
      rule: "Host(`example.com`) && PathPrefix(`/ko-merge`)"
      service: ko-merge-service
      middlewares:
        - ko-merge-stripprefix
      tls:
        certResolver: letsencrypt

  services:
    ko-merge-service:
      loadBalancer:
        servers:
          - url: "http://192.168.1.100:3000"  # Your Ko-Merge container IP:port

  middlewares:
    ko-merge-stripprefix:
      stripPrefix:
        prefixes:
          - "/ko-merge"
```

#### 6. Development Mode

Default development setup (<http://localhost:8000>):

```env
# .env configuration (or leave empty)
PUBLIC_BASE_URL=
USE_SUBFOLDER=false
PUBLIC_SUBFOLDER_PATH=
```

#### 7. UnRaid Template Variables

For UnRaid users, these variables can be set in the container template:

```xml
<Config Name="Base URL" Target="PUBLIC_BASE_URL" Default="https://mydomain.com" Mode="" Description="Base URL for the application" Type="Variable" Display="always" Required="false" Mask="false"></Config>
<Config Name="Subfolder Path" Target="PUBLIC_SUBFOLDER_PATH" Default="ko-merge" Mode="" Description="Subfolder path (leave empty for root deployment)" Type="Variable" Display="always" Required="false" Mask="false"></Config>
<Config Name="Use Subfolder" Target="USE_SUBFOLDER" Default="true" Mode="" Description="Enable subfolder deployment" Type="Variable" Display="always" Required="false" Mask="false">true</Config>
```

## 📚 API Documentation

### Core Merge Operations

- `POST /api/upload` - Upload KOReader database
- `GET /api/books/{session_id}` - Get books from uploaded database
- `POST /api/merge-groups/{session_id}` - Add merge group
- `POST /api/execute-merge/{session_id}` - Execute all merges
- `GET /api/download/{session_id}` - Download merged database

### Enhanced Book Details & Cover Management

- `GET /api/book-details` - Get rich metadata from Google Books/OpenLibrary/Amazon
- `GET /api/cover-options` - Get multiple cover options from all sources
  - Supports title/author search: `?title=Book&author=Author`
  - Supports ISBN search: `?isbn=9780123456789` (Google Books & OpenLibrary)
  - Supports ASIN search: `?asin=B08N5WRWNW&source=amazon` (Amazon only)
- `POST /api/cover-preference` - Download and store cover images locally with unified storage
- `GET /api/cover-preference` - Retrieve locally stored cover images
- `GET /api/covers/batch` - Batch endpoint for retrieving multiple book covers efficiently
- `GET /api/covers/{image_hash}` - Serve locally stored cover images with caching headers
- `GET /api/preferences-stats` - Get usage statistics

### API Features

- **Multi-Source Integration**: Google Books, OpenLibrary, and Amazon scraping
- **Request Deduplication**: Prevents duplicate concurrent Amazon requests
- **Global Caching System**: Title/author-based caching across all users
- **Smart Fallbacks**: Automatic fallback chain for comprehensive coverage
- **Playwright Integration**: Full browser automation for Amazon scraping
- **Windows Compatibility**: Fixed Python 3.13 + Windows event loop issues
- **Persistent Preferences**: Cover choices saved using book fingerprinting
- **No Authentication**: Stateless design with book-based identification

Full API documentation available at: <http://localhost:8000/docs>

## 🎨 UI Features

### Book Cards

- **Book cover images** with fallback placeholders
- **Prominent MD5 hash** display for merge identification
- **Author and series** information
- **Reading time** and book ID
- **Visual selection states** (Keep/Merge)

### Responsive Design

- **Mobile**: Single column layout
- **Tablet**: 2-3 column grid
- **Desktop**: 4+ column grid
- **Dark mode** optimized throughout

## 🐳 Docker Details

### Unraid Compatibility

- Configurable PUID/PGID for proper file permissions
- Health checks for service monitoring
- Persistent volume management
- Automatic restart policies

### Security Features

- Non-root user execution
- Read-only mounts where appropriate
- Security headers in Nginx
- CORS configuration

## 🔍 Troubleshooting

### Development Issues

1. **UV not found**: Install from <https://docs.astral.sh/uv/getting-started/installation/>
2. **Node.js not found**: Install from <https://nodejs.org/>
3. **Port conflicts**: Check if ports 8000/5173 are available
4. **Permission errors**: Run as administrator if needed
5. **Playwright errors**: Use `start_server.py` instead of direct uvicorn for Windows + Python 3.13

### Docker Issues

1. **Build failures**: Check Docker daemon is running
2. **Permission errors**: Verify PUID/PGID settings
3. **Network issues**: Ensure ports are not blocked
4. **Volume mounting**: Check DATA_PATH exists and is accessible
5. **Playwright issues**: Container includes all required browser dependencies

### Amazon Scraping Issues

1. **NotImplementedError**: Fixed by proper event loop policy in `start_server.py`
2. **Duplicate requests**: Prevented by global request deduplication system
3. **Missing covers**: Amazon now integrated in frontend cover fetching
4. **Slow responses**: Global caching minimizes repeated scraping requests

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Test thoroughly
5. Submit a pull request

## ⚠️ Important Notes

- **Backup your database** before using this tool
- This is a **weekend project** with **heavy AI-generated code**
- **Use at your own risk** - always test with copies first
- Designed for **KOReader statistics databases** only

## 📄 License

This project is provided as-is for educational and personal use.

---

Made with ❤️ by [Jadehawk](https://techy-notes.com/) | Vibe Coding | Use at your own RISK!
