# Multi-stage build for single container deployment
# cSpell:ignore PYTHONPATH LOGFILE
FROM node:20 AS frontend-builder

# Build frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ ./

# Pass environment variables to frontend build
# These will be available during the Vite build process
ARG VITE_PUBLIC_BASE_URL
ARG VITE_PUBLIC_SUBFOLDER_PATH
ARG VITE_USE_SUBFOLDER

ENV VITE_PUBLIC_BASE_URL=${VITE_PUBLIC_BASE_URL}
ENV VITE_PUBLIC_SUBFOLDER_PATH=${VITE_PUBLIC_SUBFOLDER_PATH}
ENV VITE_USE_SUBFOLDER=${VITE_USE_SUBFOLDER}

# Log build configuration for debugging
RUN echo "=== Frontend Build Configuration ===" && \
    echo "VITE_PUBLIC_BASE_URL: ${VITE_PUBLIC_BASE_URL}" && \
    echo "VITE_PUBLIC_SUBFOLDER_PATH: ${VITE_PUBLIC_SUBFOLDER_PATH}" && \
    echo "VITE_USE_SUBFOLDER: ${VITE_USE_SUBFOLDER}" && \
    echo "===================================="

RUN npm run build

# Post-build: Convert absolute asset paths to relative paths for flexible deployment
# This allows the frontend to work in any subfolder without rebuild
RUN sed -i 's|src="/assets/|src="./assets/|g' dist/index.html && \
    sed -i 's|href="/assets/|href="./assets/|g' dist/index.html && \
    echo "=== Post-build: Converted to relative paths ===" && \
    cat dist/index.html | grep -E "(src=|href=)" && \
    echo "=============================================="

# Download and replace favicon with the proper Ko-Merge logo
RUN curl -L "https://raw.githubusercontent.com/jadehawk/IconsBackup/main/Icons/ko-merge.png" -o dist/favicon.png && \
    echo "=== Downloaded Ko-Merge favicon ===" && \
    ls -la dist/favicon.png && \
    file dist/favicon.png && \
    echo "Favicon file size: $(wc -c < dist/favicon.png) bytes" && \
    echo "=================================="

# Also update the HTML to ensure favicon is properly referenced
RUN sed -i 's|href="favicon.png"|href="./favicon.png"|g' dist/index.html && \
    echo "=== Updated favicon reference in HTML ===" && \
    grep favicon dist/index.html && \
    echo "=========================================="

# Python backend with frontend static files
FROM python:3.11-slim

# Install build dependencies and runtime dependencies in one layer
RUN apt-get update && apt-get install -y \
    # Build dependencies for Python packages
    build-essential \
    gcc \
    g++ \
    # Essential runtime dependencies
    curl \
    wget \
    gnupg \
    ca-certificates \
    bash \
    # Playwright runtime dependencies
    fonts-liberation \
    libasound2 \
    libatk-bridge2.0-0 \
    libatk1.0-0 \
    libatspi2.0-0 \
    libcups2 \
    libdbus-1-3 \
    libdrm2 \
    libgtk-3-0 \
    libnspr4 \
    libnss3 \
    libwayland-client0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxkbcommon0 \
    libxrandr2 \
    xvfb \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python packages during image build
COPY requirements.txt ./

# Install Python packages during image build (includes slow wheel building)
RUN pip install --no-cache-dir -r requirements.txt

# Install Playwright and browsers during image build
RUN playwright install --with-deps firefox

# Clean up build dependencies but keep runtime dependencies
RUN apt-get update && apt-get remove -y build-essential gcc g++ && \
    apt-get autoremove -y && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/* && \
    # Remove unused Playwright browsers to save space (keep only Firefox)
    rm -rf /root/.cache/ms-playwright/webkit* /root/.cache/ms-playwright/chromium* && \
    pip cache purge

# Copy backend application
COPY backend/ ./

# Copy built frontend from previous stage
COPY --from=frontend-builder /app/frontend/dist ./static

# Copy the downloaded Ko-Merge favicon (overrides the default one)
COPY --from=frontend-builder /app/frontend/dist/favicon.png ./static/favicon.png

# Create data and logs directories
RUN mkdir -p data/covers data/uploads data/processed logs
RUN chmod 777 logs data/covers data/uploads data/processed

# Expose port
EXPOSE 8000

# Set environment variables
ENV PYTHONPATH=/app
ENV STATIC_FILES_DIR=/app/static

# Keep as root user to handle volume mount permissions

# Create the optimized startup script (dependencies pre-installed during image build)
RUN echo '#!/bin/bash\n\
\n\
# Ensure logs directory exists and has proper permissions\n\
mkdir -p /app/logs\n\
chmod 777 /app/logs\n\
\n\
# Create log file with timestamp\n\
LOGFILE="/app/logs/startup-$(date +%Y%m%d-%H%M%S).log"\n\
\n\
# Test if we can write to log file\n\
echo "Testing log file creation..." > "$LOGFILE" 2>&1\n\
if [ $? -eq 0 ]; then\n\
  echo "Log file created successfully: $LOGFILE" >> "$LOGFILE"\n\
  # Set up logging for the rest of the script\n\
  exec > >(tee -a "$LOGFILE")\n\
  exec 2>&1\n\
else\n\
  echo "ERROR: Cannot create log file $LOGFILE"\n\
  echo "Continuing without file logging..."\n\
fi\n\
\n\
echo "=== Ko-Merge Container Starting at $(date) ==="\n\
echo "Log file: $LOGFILE"\n\
echo "Python version: $(python --version)"\n\
echo "Working directory: $(pwd)"\n\
echo "User: $(whoami)"\n\
echo "Environment variables:"\n\
echo "  PYTHONPATH=$PYTHONPATH"\n\
echo "  STATIC_FILES_DIR=$STATIC_FILES_DIR"\n\
echo ""\n\
echo "=== OPTIMIZED STARTUP - Dependencies Pre-installed ==="\n\
echo "Python packages and Playwright browsers were installed during image build"\n\
echo "This container will start much faster!"\n\
echo ""\n\
\n\
echo "Directory contents:"\n\
ls -la || echo "Failed to list directory"\n\
echo ""\n\
echo "Static directory check:"\n\
if [ -d "$STATIC_FILES_DIR" ]; then\n\
  echo "  Static directory exists: $STATIC_FILES_DIR"\n\
  echo "  Static files:"\n\
  ls -la "$STATIC_FILES_DIR" 2>/dev/null | head -10 || echo "  Failed to list static files"\n\
else\n\
  echo "  Static directory NOT found: $STATIC_FILES_DIR"\n\
fi\n\
echo ""\n\
echo "Data directory check:"\n\
ls -la data/ 2>/dev/null || echo "Failed to list data directory"\n\
echo ""\n\
echo "Python path check:"\n\
python -c "import sys; print(\"Python path:\"); [print(f\"  {p}\") for p in sys.path]" || echo "Failed to check Python path"\n\
echo ""\n\
echo "Fixing data directory permissions (volume mount may have changed ownership):"\n\
mkdir -p data/covers data/uploads data/processed\n\
chmod 777 data/covers data/uploads data/processed 2>/dev/null || echo "Could not chmod data directories"\n\
echo "Setting database file permissions to 666 for remote access:"\n\
find data -name "*.sqlite3" -exec chmod 666 {} \; 2>/dev/null || echo "No .sqlite3 files found yet"\n\
find data -name "*.db" -exec chmod 666 {} \; 2>/dev/null || echo "No .db files found yet"\n\
echo "Data directory and database file permissions fixed"\n\
echo ""\n\
echo "Testing imports:"\n\
python -c "from app.main import app; print(\"FastAPI app imported successfully\")" || {\n\
  echo "Failed to import FastAPI app - CRITICAL ERROR"\n\
  echo "Sleeping for 300 seconds to prevent restart loop..."\n\
  sleep 300\n\
  exit 1\n\
}\n\
echo ""\n\
echo "Starting FastAPI server at $(date)..."\n\
echo "=== Server Logs ==="\n\
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --log-level info || {\n\
  echo "FastAPI server failed to start - CRITICAL ERROR"\n\
  echo "Sleeping for 300 seconds to prevent restart loop..."\n\
  sleep 300\n\
  exit 1\n\
}\n\
' > /app/start.sh && chmod +x /app/start.sh

# Start command with persistent logging
CMD ["/app/start.sh"]
