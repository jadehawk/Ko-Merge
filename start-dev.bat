@echo off
echo ========================================
echo Ko-Merge v2 Development Environment
echo ========================================
echo.

:: Check if we're in the correct directory
if not exist "backend\pyproject.toml" (
    echo ERROR: Please run this script from the Ko-Merge v2 root directory
    echo Expected to find backend\pyproject.toml
    echo Current directory: %CD%
    echo.
    pause
    exit /b 1
)

:: Kill any processes using ports 8000 and 5173
echo Cleaning up any existing processes on ports 8000 and 5173...
for /f "tokens=5" %%a in ('netstat -ano ^| findstr :8000 2^>nul') do (
    if not "%%a"=="0" (
        echo Killing process %%a using port 8000...
        taskkill /PID %%a /F >nul 2>&1
    )
)

for /f "tokens=5" %%a in ('netstat -ano ^| findstr :5173 2^>nul') do (
    if not "%%a"=="0" (
        echo Killing process %%a using port 5173...
        taskkill /PID %%a /F >nul 2>&1
    )
)

timeout /t 2 /nobreak >nul

echo.
echo Starting backend server...
start "Ko-Merge-Backend" cmd /k "title Ko-Merge Backend Server && cd /d %CD%\backend && echo Backend starting in: %CD% && echo. && uv run python start_server.py"

echo Waiting 3 seconds for backend to start...
timeout /t 3 /nobreak >nul

echo Starting frontend server...
start "Ko-Merge-Frontend" cmd /k "title Ko-Merge Frontend Server && cd /d %CD%\frontend && echo Frontend starting in: %CD% && echo. && npm run dev"

echo.
echo ========================================
echo Ko-Merge v2 Development Environment Started!
echo ========================================
echo.
echo Backend:  http://localhost:8000
echo Frontend: http://localhost:5173
echo API Docs: http://localhost:8000/docs
echo.
echo Both services should now be running in separate windows:
echo - Ko-Merge Backend Server
echo - Ko-Merge Frontend Server
echo.
echo To stop the services, close the respective windows or press Ctrl+C in them.
echo.
echo This window will close automatically in 10 seconds...
timeout /t 10 /nobreak >nul
