# GitHub Repository Replacement Guide

This guide will help you completely replace the old GitHub repository with the new Ko-Merge project files.

## 🎯 Goal

Replace the entire contents of <https://github.com/jadehawk/Ko-Merge> with the current project files.

## 📋 Prerequisites

- Git installed on your system
- GitHub account with access to the repository
- Current project files ready (this directory)

## 🔄 Method 1: Complete Repository Replacement (Recommended)

This method completely replaces all files and history:

### Step 1: Clone the Repository

```bash
# Clone the existing repository
git clone https://github.com/jadehawk/Ko-Merge.git
cd Ko-Merge

# Check current status
git status
git log --oneline -5
```

### Step 2: Remove All Old Files

```bash
# Remove all files except .git directory
find . -maxdepth 1 ! -name '.git' ! -name '.' -exec rm -rf {} +

# Or on Windows:
# Remove all files and folders except .git
# (You can do this manually in File Explorer, keeping only the .git folder)
```

### Step 3: Copy New Files

```bash
# Copy all files from your current project directory to the cloned repo
# Replace /path/to/your/current/project with the actual path

# On Linux/Mac:
cp -r /path/to/your/current/project/* .
cp -r /path/to/your/current/project/.* . 2>/dev/null || true

# On Windows (from Command Prompt in the Ko-Merge directory):
# xcopy "D:\OneDrive\GitHubRepos\Ko-Mergev2\*" . /E /H /Y
# This copies all files including hidden ones
```

### Step 4: Prepare Git

```bash
# Add all new files
git add .

# Check what will be committed
git status

# Commit the changes
git commit -m "Complete project overhaul: Modern Ko-Merge with Docker Hub integration

- Updated to use pre-built Docker image (jadehawk/ko-merge:latest)
- Optimized Docker build with pre-installed dependencies
- Enhanced UI with book covers and metadata
- Added comprehensive deployment documentation
- Improved performance and reliability
- Ready for production deployment"
```

### Step 5: Force Push to GitHub

```bash
# Force push to replace everything
git push origin main --force

# If your default branch is 'master':
# git push origin master --force
```

## 🔄 Method 2: Clean Slate Approach

If you want to start completely fresh:

### Step 1: Delete Repository Contents on GitHub

1. Go to <https://github.com/jadehawk/Ko-Merge>
2. Go to Settings → Danger Zone
3. **DO NOT DELETE THE REPOSITORY** - we just want to clear contents

### Step 2: Create New Repository Structure

```bash
# Initialize new git repository in your current project
cd /path/to/your/current/project
git init

# Add GitHub remote
git remote add origin https://github.com/jadehawk/Ko-Merge.git

# Add all files
git add .

# Initial commit
git commit -m "Initial commit: Modern Ko-Merge v2.0

- Complete rewrite with React + TypeScript frontend
- FastAPI + UV backend with enhanced performance
- Docker Hub integration (jadehawk/ko-merge:latest)
- Multi-source book metadata (Google Books, OpenLibrary, Amazon)
- Modern UI with book covers and library-style layout
- Comprehensive deployment documentation
- Production-ready with optimized Docker builds"

# Set main branch and push
git branch -M main
git push -u origin main --force
```

## 🔄 Method 3: Gradual Replacement (If you want to preserve some history)

### Step 1: Create Backup Branch

```bash
git clone https://github.com/jadehawk/Ko-Merge.git
cd Ko-Merge

# Create backup branch
git checkout -b backup-old-version
git push origin backup-old-version

# Return to main
git checkout main
```

### Step 2: Replace Files

```bash
# Remove all files except .git
find . -maxdepth 1 ! -name '.git' ! -name '.' -exec rm -rf {} +

# Copy new files
cp -r /path/to/your/current/project/* .
cp -r /path/to/your/current/project/.* . 2>/dev/null || true

# Commit and push
git add .
git commit -m "Major update: Complete Ko-Merge overhaul"
git push origin main
```

## 📁 Files to Include

Make sure these files are copied to the GitHub repository:

### Essential Files

- `README.md` - Main documentation
- `docker-compose.yml` - Production deployment
- `DEPLOYMENT.md` - Deployment guide
- `DOCKER_HUB_OVERVIEW.md` - Docker Hub documentation
- `.env.example` - Environment template
- `Dockerfile` - For building from source
- `.gitignore` - Git ignore rules
- `.dockerignore` - Docker ignore rules

### Application Code

- `backend/` - Complete backend directory
- `frontend/` - Complete frontend directory
- `requirements.txt` - Python dependencies
- `pyproject.toml` - UV configuration

### Development Files

- `start-dev.bat` - Development script
- `stop-dev.bat` - Development script
- `DOCKER_OPTIMIZATION.md` - Optimization documentation

### Files to Exclude

Create/update `.gitignore` to exclude:

```gitignore
# Environment files
.env

# Python
__pycache__/
*.py[cod]
*$py.class
.venv/
venv/
.Python

# Node.js
node_modules/
npm-debug.log*
yarn-debug.log*
yarn-error.log*

# Build outputs
dist/
build/

# Data directories
data/
*.sqlite3
*.db

# IDE
.vscode/
.idea/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Logs
logs/
*.log

# UV
uv.lock
```

## ✅ Verification Steps

After pushing to GitHub:

1. **Check Repository**: Visit <https://github.com/jadehawk/Ko-Merge>
2. **Verify Files**: Ensure all new files are present
3. **Test README**: Check that README.md displays correctly
4. **Test Deployment**: Try the quick start commands:

   ```bash
   git clone https://github.com/jadehawk/Ko-Merge.git
   cd Ko-Merge
   docker-compose up -d
   ```

5. **Check Documentation**: Verify all links work correctly

## 🚨 Important Notes

1. **Backup First**: Make sure you have a backup of any important data
2. **Force Push Warning**: `--force` will overwrite history permanently
3. **Collaborators**: Inform any collaborators about the major changes
4. **Issues/PRs**: Existing issues and pull requests will remain
5. **Releases**: Consider creating a new release tag after the update

## 🎯 Recommended Approach

I recommend **Method 1** (Complete Repository Replacement) because:

- Clean and straightforward
- Preserves the repository URL and settings
- Maintains issues and discussions
- Creates a clear "before and after" in the commit history

## 🔧 Windows-Specific Commands

If you're on Windows, here are the specific commands:

```cmd
# Clone repository
git clone https://github.com/jadehawk/Ko-Merge.git
cd Ko-Merge

# Remove all files except .git (do this manually in File Explorer)
# Keep only the .git folder, delete everything else

# Copy new files (adjust path as needed)
xcopy "D:\OneDrive\GitHubRepos\Ko-Mergev2\*" . /E /H /Y /EXCLUDE:exclude.txt

# Create exclude.txt file to skip certain directories:
echo .git > exclude.txt
echo .venv >> exclude.txt
echo node_modules >> exclude.txt
echo data >> exclude.txt

# Add and commit
git add .
git commit -m "Complete project overhaul: Modern Ko-Merge with Docker Hub integration"
git push origin main --force
```

## 🎉 After Deployment

Once the repository is updated:

1. **Update Docker Hub**: Ensure the image is built and published
2. **Test Deployment**: Verify the docker-compose.yml works
3. **Update Documentation**: Check all links are working
4. **Create Release**: Consider tagging a new version
5. **Announce**: Share the updated project with the community

---

This will give you a completely fresh GitHub repository with all the new Ko-Merge files!
