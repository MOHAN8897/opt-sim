# Helper script to get ngrok URLs from the API
# Run this while ngrok is running to get the public URLs

$apiUrl = "http://localhost:4040/api/tunnels"

try {
    Write-Host "🔍 Fetching ngrok tunnel URLs..." -ForegroundColor Cyan
    Write-Host ""
    
    $response = Invoke-RestMethod -Uri $apiUrl -Method Get -ErrorAction Stop
    
    if ($response.tunnels.Count -eq 0) {
        Write-Host "❌ No active ngrok tunnels found!" -ForegroundColor Red
        Write-Host "Make sure ngrok is running first." -ForegroundColor Yellow
        exit 1
    }
    
    Write-Host "📡 Active ngrok Tunnels:" -ForegroundColor Green
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Gray
    Write-Host ""
    
    foreach ($tunnel in $response.tunnels) {
        $publicUrl = $tunnel.public_url
        $localAddr = $tunnel.config.addr
        
        # Determine service type
        $serviceType = if ($localAddr -match "8000") { "Backend" } elseif ($localAddr -match "5173") { "Frontend" } else { "Unknown" }
        
        Write-Host "  $serviceType" -ForegroundColor Cyan -NoNewline
        Write-Host " ($localAddr)" -ForegroundColor Gray
        Write-Host "  └─ " -NoNewline -ForegroundColor Gray
        Write-Host "$publicUrl" -ForegroundColor Green
        Write-Host ""
    }
    
    Write-Host "═══════════════════════════════════════════════" -ForegroundColor Gray
    Write-Host ""
    Write-Host "💡 Share these URLs with your friends!" -ForegroundColor Yellow
    Write-Host ""
    
}
catch {
    Write-Host "❌ Error: Could not connect to ngrok API" -ForegroundColor Red
    Write-Host "Make sure ngrok is running (it should have a web interface at http://localhost:4040)" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Gray
}
