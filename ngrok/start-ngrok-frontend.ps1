# Start ngrok tunnel for frontend (port 5173)
# This exposes your React/Vite frontend to the internet

Write-Host "🚀 Starting ngrok tunnel for frontend (port 5173)..." -ForegroundColor Cyan
Write-Host ""

# Start ngrok
ngrok http 5173 --log=stdout --log-level=info

# Note: Press Ctrl+C to stop the tunnel
