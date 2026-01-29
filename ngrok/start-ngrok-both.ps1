# Start ngrok tunnels for both backend and frontend
# Uses ngrok configuration file for multiple tunnels

Write-Host "🚀 Starting ngrok tunnels for both backend (8000) and frontend (5173)..." -ForegroundColor Cyan
Write-Host ""
Write-Host "📝 Make sure you have updated ngrok.yml configuration file" -ForegroundColor Yellow
Write-Host ""

# Check if ngrok.yml exists
$ngrokConfigPath = Join-Path $PSScriptRoot "ngrok.yml"
if (-not (Test-Path $ngrokConfigPath)) {
    Write-Host "❌ Error: ngrok.yml not found!" -ForegroundColor Red
    Write-Host "Creating ngrok.yml with default configuration..." -ForegroundColor Yellow
    
    # Create default ngrok.yml
    @"
version: "2"
authtoken: 36i1FLKt92Q24vaLTdehWuatcim_48rdBF3YTosdTRoQMTUhH

tunnels:
  backend:
    proto: http
    addr: 8000
    inspect: true
    
  frontend:
    proto: http
    addr: 5173
    inspect: true
"@ | Out-File -FilePath $ngrokConfigPath -Encoding UTF8
    
    Write-Host "✅ Created ngrok.yml" -ForegroundColor Green
}

# Start ngrok with config file
Write-Host "🌐 Starting tunnels..." -ForegroundColor Cyan
ngrok start --all --config=$ngrokConfigPath --log=stdout

# Note: Press Ctrl+C to stop all tunnels
