# Start ngrok tunnel for backend (port 8000)
# This exposes your FastAPI backend to the internet

Write-Host "🚀 Starting ngrok tunnel for backend (port 8000)..." -ForegroundColor Cyan
Write-Host ""

# Start ngrok
ngrok http 8000 --log=stdout --log-level=info

# Note: Press Ctrl+C to stop the tunnel
