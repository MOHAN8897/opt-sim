@echo off
echo ===================================================
echo   FULL RESTART: Option Simulator
echo   (Stops ports, Fixes Redis, Starts Servers)
echo ===================================================
echo.

echo [1/4] Stopping running processes on ports 8000 (Backend) and 8080 (Frontend)...
REM Kill process on port 8000
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8000" ^| find "LISTENING"') do (
    echo Killing PID %%a on port 8000...
    taskkill /f /pid %%a >nul 2>&1
)

REM Kill process on port 8080
for /f "tokens=5" %%a in ('netstat -aon ^| find ":8080" ^| find "LISTENING"') do (
    echo Killing PID %%a on port 8080...
    taskkill /f /pid %%a >nul 2>&1
)
echo Ports freed.
echo.

echo [2/4] Ensuring Redis is HEALTHY (Force Recreate)...
REM Check if Docker is running
docker info >nul 2>&1
if %ERRORLEVEL% EQU 0 goto :DockerRunning

echo Docker is NOT running. Attempting to start Docker Desktop...
start "" "C:\Program Files\Docker\Docker\Docker Desktop.exe"

echo Waiting for Docker to start (this may take a minute)...
:WaitDocker
timeout /t 5 /nobreak >nul
docker info >nul 2>&1
if %ERRORLEVEL% NEQ 0 (
    echo Docker still starting...
    goto WaitDocker
)
echo Docker is now RUNNING!

:DockerRunning
REM Force recreate Redis to ensure it works "by any means"
echo Stopping old Redis container...
docker-compose down redis 2>nul
echo Starting fresh Redis container...
docker-compose up -d --force-recreate redis

echo Waiting for Redis to be ready...
timeout /t 3 /nobreak >nul

echo Verifying Redis connection...
docker exec redis-simulator redis-cli ping
docker exec redis-simulator redis-cli ping
if %ERRORLEVEL% NEQ 0 (
    echo [WARNING] Redis did not respond to PING. Retrying in 2 seconds...
    timeout /t 2 /nobreak >nul
    docker exec redis-simulator redis-cli ping
)
if %ERRORLEVEL% EQU 0 (
    echo Redis is successfully running (PONG).
)
echo.

echo [3/4] Starting Backend (Port 8000)...
start "Backend Server" cmd /k "call .venv\Scripts\activate && uvicorn backend.main:app --reload --port 8000"

echo [4/4] Starting Frontend (Port 8080)...
cd option-simulator
start "Frontend Server" cmd /k "npm run dev"

echo.
echo ===================================================
echo   System Restarted Successfully!
echo   ----------------------------------------
echo   Frontend: http://localhost:8080
echo   Backend:  http://localhost:8000
echo   Redis:    Running (Docker)
echo ===================================================
echo.
pause
