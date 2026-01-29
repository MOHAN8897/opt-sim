# Start Backend with ngrok tunnel
# This script starts the FastAPI backend and creates an ngrok tunnel

Write-Host ""
Write-Host "🚀 Starting Backend + ngrok Tunnel..." -ForegroundColor Cyan
Write-Host "═══════════════════════════════════════════════" -ForegroundColor Gray
Write-Host ""

# Change to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Check if virtual environment exists
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "❌ Virtual environment not found!" -ForegroundColor Red
    Write-Host "Please create it first: python -m venv .venv" -ForegroundColor Yellow
    exit 1
}

# Function to start ngrok and get URL
function Start-NgrokBackend {
    Write-Host "🌐 Starting ngrok tunnel for backend (port 8000)..." -ForegroundColor Cyan
    
    # Start ngrok in background
    $ngrokJob = Start-Job -ScriptBlock {
        $env:Path = [System.Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [System.Environment]::GetEnvironmentVariable("Path", "User")
        ngrok http 8000 --log=stdout
    }
    
    # Wait for ngrok to start
    Start-Sleep -Seconds 3
    
    # Get ngrok URL
    try {
        $response = Invoke-RestMethod -Uri "http://localhost:4040/api/tunnels" -Method Get -ErrorAction Stop
        if ($response.tunnels.Count -gt 0) {
            $publicUrl = $response.tunnels[0].public_url
            Write-Host "✅ ngrok tunnel started!" -ForegroundColor Green
            Write-Host ""
            Write-Host "  📡 Public URL (share this): " -NoNewline -ForegroundColor Yellow
            Write-Host "$publicUrl" -ForegroundColor Green
            Write-Host "  🏠 Local URL:                http://localhost:8000" -ForegroundColor Gray
            Write-Host ""
            
            # Save URL to file
            $publicUrl | Out-File -FilePath ".ngrok-backend-url" -Encoding UTF8
            
            return $publicUrl
        }
    }
    catch {
        Write-Host "⚠️  Could not get ngrok URL (it may still be starting...)" -ForegroundColor Yellow
    }
}

# Start ngrok first
$ngrokUrl = Start-NgrokBackend

Write-Host "═══════════════════════════════════════════════" -ForegroundColor Gray
Write-Host "🐍 Starting FastAPI Backend..." -ForegroundColor Cyan
Write-Host ""

# Activate virtual environment and start backend
& .\.venv\Scripts\Activate.ps1
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Note: This line won't execute until the server is stopped
Write-Host ""
Write-Host "👋 Backend stopped" -ForegroundColor Yellow
