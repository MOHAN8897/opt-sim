@echo off
echo Starting ngrok tunnels...
echo.
echo Backend tunnel (port 8080) - Opening in new window...
start "Ngrok Backend (8080)" cmd /k "call C:\Users\subha\AppData\Roaming\npm\ngrok.cmd http 8080"
timeout /t 3 /nobreak >nul

echo Frontend tunnel (port 5173) - Opening in new window...
start "Ngrok Frontend (5173)" cmd /k "call C:\Users\subha\AppData\Roaming\npm\ngrok.cmd http 5173"
timeout /t 3 /nobreak >nul

echo.
echo ============================================
echo Ngrok tunnels are starting!
echo ============================================
echo.
echo Wait 10 seconds, then open: http://localhost:4040
echo.
echo You'll see BOTH tunnel URLs there.
echo.
pause
