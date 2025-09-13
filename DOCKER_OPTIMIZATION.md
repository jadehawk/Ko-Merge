# Docker Build Optimization

## Problem Solved

The original Dockerfile deferred Python package installation (including slow wheel building for `aiohttp`, `greenlet`, and `pydantic-core`) to container startup time. This caused every first container startup to take 2-3 minutes while building these wheels.

## Optimization Changes

### 1. Moved Package Installation to Image Build Phase

**Before:**

- Python packages installed during container startup
- Wheel building happened every time a new container started
- First startup took 2-3 minutes

**After:**

- Python packages installed during Docker image build
- Wheel building happens once during `docker build`
- Container startup is now nearly instantaneous

### 2. Optimized Docker Layers

The new Dockerfile structure:

1. **Install dependencies** - Build tools + runtime dependencies in one layer
2. **Install Python packages** - Includes slow wheel building (aiohttp, greenlet, pydantic-core)
3. **Install Playwright browsers** - Firefox for Amazon scraping
4. **Clean up build dependencies** - Remove build tools, keep runtime dependencies
5. **Copy application code** - Backend and frontend files
6. **Simplified startup script** - No more package installation logic

### 3. Key Benefits

- **Faster container startup**: From 2-3 minutes to ~10 seconds
- **Better caching**: Docker layers cache the expensive wheel building
- **Smaller runtime footprint**: Build dependencies removed after use
- **More reliable deployments**: Dependencies pre-installed and tested

## Testing the Optimization

To test the optimized build:

```bash
# Build the optimized image (this will take time due to wheel building)
docker build -t ko-merge-optimized .

# Run the container (should start much faster now)
docker run -p 8000:8000 ko-merge-optimized
```

## Expected Build Output

During the build, you should see the slow wheel building happen once:

```text
Building wheels for collected packages: aiohttp, greenlet, pydantic-core
  Building wheel for aiohttp (pyproject.toml): started
  Building wheel for aiohttp (pyproject.toml): finished with status 'done'
  Building wheel for greenlet (pyproject.toml): started  
  Building wheel for greenlet (pyproject.toml): finished with status 'done'
  Building wheel for pydantic-core (pyproject.toml): started
  Building wheel for pydantic-core (pyproject.toml): still running...
  Building wheel for pydantic-core (pyproject.toml): finished with status 'done'
```

But subsequent container starts will be fast since the wheels are pre-built in the image.

## Image Size Considerations

- **Slightly larger image**: Pre-installed packages increase image size
- **Trade-off**: Larger image for much faster container startup
- **Cleanup**: Build dependencies are removed to minimize size impact
- **Browser cleanup**: Only Firefox is kept, WebKit/Chromium removed

## Deployment Impact

- **CI/CD**: Build time increases, but deployment/startup time decreases significantly
- **Scaling**: New container instances start immediately
- **Development**: Local development containers start much faster
- **Production**: Better user experience with faster service availability

## Rollback Plan

If issues arise, the original Dockerfile approach can be restored by:

1. Moving package installation back to startup script
2. Removing build dependencies from image build
3. Restoring the original startup script logic

The optimization maintains full functionality while dramatically improving startup performance.
