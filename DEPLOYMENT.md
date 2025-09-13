# Ko-Merge Deployment Guide

This guide covers various deployment scenarios for Ko-Merge using the pre-built Docker image from Docker Hub.

## 🚀 Quick Start

The easiest way to get Ko-Merge running is with Docker Compose:

```bash
# Download the docker-compose.yml
curl -O https://raw.githubusercontent.com/jadehawk/Ko-Merge/main/docker-compose.yml

# Create environment file (optional)
cp .env.example .env

# Start the application
docker-compose up -d
```

Access at: <http://localhost:3000>

## 📋 Prerequisites

- Docker and Docker Compose installed
- At least 2GB RAM available
- 5GB disk space for data storage

## 🔧 Environment Configuration

### Basic Configuration

Create a `.env` file with your settings:

```env
# Basic deployment
PUBLIC_BASE_URL=http://localhost:3000
USE_SUBFOLDER=false
PUBLIC_SUBFOLDER_PATH=

# Optional API key for enhanced metadata
GOOGLE_BOOKS_API_KEY=your_api_key_here

# System settings
PUID=99
PGID=100
```

### Advanced Configuration

```env
# Subfolder deployment
PUBLIC_BASE_URL=https://yourdomain.com
USE_SUBFOLDER=true
PUBLIC_SUBFOLDER_PATH=ko-merge

# API settings
GOOGLE_BOOKS_API_KEY=your_google_books_api_key
CLEANUP_INTERVAL_MINUTES=120

# System settings
PUID=1000
PGID=1000
FRONTEND_PORT=3000
DATA_PATH=./data
```

## 🌐 Deployment Scenarios

### 1. Local Development/Testing

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

### 2. Production with Domain

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
      - PUBLIC_BASE_URL=https://ko-merge.yourdomain.com
      - USE_SUBFOLDER=false
      - GOOGLE_BOOKS_API_KEY=${GOOGLE_BOOKS_API_KEY}
    restart: unless-stopped
```

### 3. Subfolder Deployment

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
      - GOOGLE_BOOKS_API_KEY=${GOOGLE_BOOKS_API_KEY}
    restart: unless-stopped
```

### 4. Behind Reverse Proxy (Traefik)

```yaml
version: '3.8'
services:
  ko-merge:
    image: jadehawk/ko-merge:latest
    container_name: ko-merge
    volumes:
      - ./data:/app/data
    environment:
      - PUBLIC_BASE_URL=https://ko-merge.yourdomain.com
      - USE_SUBFOLDER=false
      - GOOGLE_BOOKS_API_KEY=${GOOGLE_BOOKS_API_KEY}
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.ko-merge.rule=Host(`ko-merge.yourdomain.com`)"
      - "traefik.http.routers.ko-merge.tls=true"
      - "traefik.http.routers.ko-merge.tls.certresolver=letsencrypt"
      - "traefik.http.services.ko-merge.loadbalancer.server.port=8000"
    networks:
      - traefik
    restart: unless-stopped

networks:
  traefik:
    external: true
```

### 5. Unraid Template

For Unraid users, use this template:

```xml
<?xml version="1.0"?>
<Container version="2">
  <Name>Ko-Merge</Name>
  <Repository>jadehawk/ko-merge:latest</Repository>
  <Registry>https://hub.docker.com/r/jadehawk/ko-merge</Registry>
  <Network>bridge</Network>
  <MyIP/>
  <Shell>bash</Shell>
  <Privileged>false</Privileged>
  <Support>https://github.com/jadehawk/Ko-Merge</Support>
  <Project>https://github.com/jadehawk/Ko-Merge</Project>
  <Overview>KOReader Statistics Database Merger with modern UI and enhanced book metadata</Overview>
  <Category>Tools:</Category>
  <WebUI>http://[IP]:[PORT:3000]</WebUI>
  <TemplateURL/>
  <Icon>https://raw.githubusercontent.com/jadehawk/IconsBackup/main/Icons/ko-merge.png</Icon>
  <ExtraParams/>
  <PostArgs/>
  <CPUset/>
  <DateInstalled>1694606400</DateInstalled>
  <DonateText/>
  <DonateLink/>
  <Requires/>
  <Config Name="WebUI Port" Target="8000" Default="3000" Mode="tcp" Description="Web interface port" Type="Port" Display="always" Required="true" Mask="false">3000</Config>
  <Config Name="Data Storage" Target="/app/data" Default="/mnt/user/appdata/ko-merge" Mode="rw" Description="Data storage path" Type="Path" Display="always" Required="true" Mask="false">/mnt/user/appdata/ko-merge</Config>
  <Config Name="Base URL" Target="PUBLIC_BASE_URL" Default="http://[IP]:[PORT:3000]" Mode="" Description="Base URL for the application" Type="Variable" Display="always" Required="false" Mask="false">http://[IP]:[PORT:3000]</Config>
  <Config Name="Use Subfolder" Target="USE_SUBFOLDER" Default="false" Mode="" Description="Enable subfolder deployment" Type="Variable" Display="always" Required="false" Mask="false">false</Config>
  <Config Name="Subfolder Path" Target="PUBLIC_SUBFOLDER_PATH" Default="" Mode="" Description="Subfolder path (leave empty for root deployment)" Type="Variable" Display="always" Required="false" Mask="false"></Config>
  <Config Name="Google Books API Key" Target="GOOGLE_BOOKS_API_KEY" Default="" Mode="" Description="Google Books API key for high-quality covers and rich metadata (highly recommended)" Type="Variable" Display="always" Required="false" Mask="true"></Config>
  <Config Name="PUID" Target="PUID" Default="99" Mode="" Description="User ID" Type="Variable" Display="advanced" Required="false" Mask="false">99</Config>
  <Config Name="PGID" Target="PGID" Default="100" Mode="" Description="Group ID" Type="Variable" Display="advanced" Required="false" Mask="false">100</Config>
</Container>
```

## 🔑 API Keys Setup

### Google Books API (Recommended)

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable the "Books API"
4. Create credentials (API Key)
5. Add to your `.env` file:

   ```env
   GOOGLE_BOOKS_API_KEY=your_api_key_here
   ```

**Benefits:**

- Rich metadata (ratings, descriptions, categories)
- Higher quality covers
- 1,000 free requests/day
- Automatic fallback to OpenLibrary if quota exceeded

## 🔍 Troubleshooting

### Common Issues

1. **Container won't start**
   - Check Docker daemon is running
   - Verify port 3000 is available
   - Check logs: `docker logs ko-merge`

2. **Permission errors**
   - Set correct PUID/PGID for your system
   - Ensure data directory is writable

3. **Can't access web interface**
   - Verify port mapping: `docker ps`
   - Check firewall settings
   - Ensure PUBLIC_BASE_URL matches your access URL

4. **Missing book covers**
   - Check internet connectivity
   - Verify API keys if using Google Books
   - Amazon scraping may be slower (uses browser automation)

### Health Checks

Check container health:

```bash
# Container status
docker ps

# Application logs
docker logs ko-merge

# Health check
curl http://localhost:3000/health
```

### Performance Tuning

For better performance:

```yaml
services:
  ko-merge:
    image: jadehawk/ko-merge:latest
    # ... other config ...
    deploy:
      resources:
        limits:
          memory: 2G
          cpus: '1.0'
        reservations:
          memory: 512M
          cpus: '0.5'
```

## 🔄 Updates

To update to the latest version:

```bash
# Pull latest image
docker pull jadehawk/ko-merge:latest

# Recreate container
docker-compose down
docker-compose up -d
```

## 🗂️ Data Management

### Backup

Important directories to backup:

- `./data/` - All application data
- `./data/covers/` - Downloaded book covers
- `./data/*.sqlite3` - Preference databases

```bash
# Create backup
tar -czf ko-merge-backup-$(date +%Y%m%d).tar.gz data/

# Restore backup
tar -xzf ko-merge-backup-20231201.tar.gz
```

### Cleanup

The application includes automatic cleanup, but you can manually clean:

```bash
# Remove old temporary files
docker exec ko-merge find /app/data -name "*.tmp" -mtime +7 -delete

# Clean unused covers (be careful!)
docker exec ko-merge python -c "
from app.services.cleanup_service import cleanup_unused_covers
cleanup_unused_covers()
"
```

## 🛡️ Security Considerations

1. **Reverse Proxy**: Use HTTPS in production
2. **Firewall**: Restrict access to necessary ports
3. **Updates**: Keep Docker image updated
4. **Backups**: Regular data backups
5. **API Keys**: Keep API keys secure and rotate regularly

## 📊 Monitoring

### Basic Monitoring

```bash
# Resource usage
docker stats ko-merge

# Application logs
docker logs -f ko-merge

# Health status
curl -s http://localhost:3000/health | jq
```

### Advanced Monitoring

For production deployments, consider:

- Prometheus metrics
- Log aggregation (ELK stack)
- Uptime monitoring
- Resource alerts

## 🤝 Support

- **GitHub Issues**: <https://github.com/jadehawk/Ko-Merge/issues>
- **Documentation**: <https://github.com/jadehawk/Ko-Merge#readme>
- **Docker Hub**: <https://hub.docker.com/r/jadehawk/ko-merge>

---

Made with ❤️ by [Jadehawk](https://techy-notes.com/) | Use at your own RISK!
