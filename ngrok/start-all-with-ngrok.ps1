# Master script to start EVERYTHING with ngrok tunnels
# Run this to start both backend and frontend with public URLs

Write-Host ""
Write-Host "[*] Starting Full Application Stack with ngrok..." -ForegroundColor Cyan
Write-Host "===============================================" -ForegroundColor Gray
Write-Host ""
Write-Host "This will start:" -ForegroundColor Yellow
Write-Host "  - Backend (FastAPI on port 8000)" -ForegroundColor Gray
Write-Host "  - Frontend (Vite on port 5173)" -ForegroundColor Gray
Write-Host "  - ngrok tunnels for both services" -ForegroundColor Gray
Write-Host ""
Write-Host "===============================================" -ForegroundColor Gray
Write-Host ""

# Change to script directory
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $scriptDir

# Function to cleanup on exit
function Cleanup {
    Write-Host ""
    Write-Host "[!] Shutting down..." -ForegroundColor Yellow
    
    # Kill all child jobs
    Get-Job | Stop-Job
    Get-Job | Remove-Job
    
    # Kill ngrok processes
    Get-Process ngrok -ErrorAction SilentlyContinue | Stop-Process -Force
    
    Write-Host "[✓] Cleanup complete" -ForegroundColor Green
}

# Register cleanup on Ctrl+C
$null = Register-EngineEvent -SourceIdentifier PowerShell.Exiting -Action { Cleanup }

try {
    # Start Backend + ngrok in background
    Write-Host "📦 Starting Backend..." -ForegroundColor Cyan
    $backendJob = Start-Job -ScriptBlock {
        param($dir)
        Set-Location $dir
        & .\start-backend-with-ngrok.ps1
    } -ArgumentList $scriptDir
    
    # Wait a bit for backend to initialize
    Start-Sleep -Seconds 5
    
    # Start Frontend + ngrok
    Write-Host "🎨 Starting Frontend..." -ForegroundColor Cyan
    Write-Host ""
    Set-Location "option-simulator"
    
    # Frontend will run in foreground so we can see the output
    npm run dev
    
}
finally {
    Cleanup
}
