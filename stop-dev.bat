@echo off
echo Stopping Ko-Merge development servers...

echo.
echo Killing processes on port 8000 (Backend)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo Killing process %%a
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo Killing processes on port 5173 (Frontend)...
for /f "tokens=5" %%a in ('netstat -aon ^| find ":5173" ^| find "LISTENING"') do (
    echo Killing process %%a
    taskkill /f /pid %%a >nul 2>&1
)

echo.
echo Closing lingering CLI windows...
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq Administrator: Command Prompt*" >nul 2>&1
taskkill /f /im cmd.exe /fi "WINDOWTITLE eq Command Prompt*" >nul 2>&1
taskkill /f /im powershell.exe /fi "WINDOWTITLE eq *uvicorn*" >nul 2>&1
taskkill /f /im powershell.exe /fi "WINDOWTITLE eq *vite*" >nul 2>&1

echo.
echo Development servers stopped and CLI windows closed.
echo This window will close automatically in 10 seconds...
timeout /t 10 /nobreak >nul
