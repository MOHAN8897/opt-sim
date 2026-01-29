@echo off
echo ===================================================
echo   Running Option Simulator (Local Dev Mode)
echo ===================================================
echo.

echo 0. Starting Redis (Docker)...
docker-compose up -d redis
echo.

echo 1. Starting Backend (Port 5173)...
start "Backend Server" cmd /k "call .venv\Scripts\activate && uvicorn backend.main:app --reload --port 8000"

echo 2. Starting Frontend (Port 8080)...
cd option-simulator
start "Frontend Server" cmd /k "npm run dev"

echo.
echo ===================================================
echo   Servers launched in new windows!
echo   Frontend: http://localhost:8080
echo   Backend:  http://localhost:8000
echo ===================================================
echo.
pause
