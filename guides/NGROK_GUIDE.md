# ngrok Integration Guide

## Overview
ngrok is now installed and integrated with your Option Simulator application. It creates secure tunnels to expose your local development servers to the internet.

## Quick Start

### Option 1: Tunnel Individual Services

**Backend Only (Port 8000):**
```powershell
.\start-ngrok-backend.ps1
```

**Frontend Only (Port 5173):**
```powershell
.\start-ngrok-frontend.ps1
```

### Option 2: Tunnel Both Services Simultaneously
```powershell
.\start-ngrok-both.ps1
```

This will create two tunnels:
- **Backend**: Exposes FastAPI on port 8000
- **Frontend**: Exposes Vite/React on port 5173

## Configuration

The ngrok configuration is stored in `ngrok.yml`:
```yaml
version: "2"
authtoken: <your-auth-token>

tunnels:
  backend:
    proto: http
    addr: 8000
    inspect: true
    bind_tls: true
    
  frontend:
    proto: http
    addr: 5173
    inspect: true
    bind_tls: true
```

## How to Use

### Step 1: Start Your Applications
Make sure both your backend and frontend are running:

```powershell
# Terminal 1 - Backend
cd c:\Users\subha\OneDrive\Desktop\simulator
.\.venv\Scripts\activate
python -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

# Terminal 2 - Frontend
cd c:\Users\subha\OneDrive\Desktop\simulator\option-simulator
npm run dev
```

### Step 2: Start ngrok Tunnels
In a new terminal:
```powershell
cd c:\Users\subha\OneDrive\Desktop\simulator
.\start-ngrok-both.ps1
```

### Step 3: Update Configuration
ngrok will display the public URLs. Update your `.env` file with these URLs:

```env
# Example ngrok URLs (these will change each time you restart ngrok)
GOOGLE_REDIRECT_URI=https://abc123.ngrok-free.app/api/auth/google/callback
BACKEND_CORS_ORIGINS=["https://xyz789.ngrok-free.app", "http://localhost:5173"]
```

## ngrok Web Interface

Once ngrok is running, you can access the web interface at:
- **Local**: http://localhost:4040

This interface shows:
- Active tunnels and their public URLs
- Real-time request/response inspection
- Request replay functionality
- Detailed logs

## Important Notes

### 1. Free Plan Limitations
- URLs change on every restart (random subdomain)
- Session timeout after 2 hours
- Limited to 1 ngrok agent running simultaneously (unless using config with multiple tunnels)

### 2. Static Domains (Paid Feature)
To get consistent URLs that don't change, upgrade to a paid plan:
- Reserved domains (e.g., `myapp.ngrok.io`)
- Longer session times
- More concurrent tunnels

### 3. Google OAuth Configuration
Update your Google OAuth settings with the ngrok URL:
1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Navigate to APIs & Services > Credentials
3. Edit your OAuth 2.0 Client ID
4. Add the ngrok URL to "Authorized redirect URIs":
   - Example: `https://abc123.ngrok-free.app/api/auth/google/callback`

### 4. Security Considerations
- ngrok tunnels are publicly accessible
- Anyone with the URL can access your app
- For production, consider:
  - Using ngrok's built-in auth: `ngrok http 8000 --basic-auth="username:password"`
  - IP restrictions (paid plan)
  - Rate limiting

## Troubleshooting

### "command not found: ngrok"
Restart your terminal or manually add ngrok to PATH:
```powershell
$env:Path += ";C:\Program Files\ngrok"
```

### "AUTH_TOKEN not found"
Run the auth command:
```powershell
ngrok config add-authtoken 36i1FLKt92Q24vaLTdehWuatcim_48rdBF3YTosdTRoQMTUhH
```

### Can't access ngrok URL
1. Check if your local app is running
2. Verify firewall isn't blocking ngrok
3. Check ngrok logs for errors

### "Too many connections"
Free plan limits concurrent connections. Wait or upgrade plan.

## Alternative: Using localtunnel (Currently Running)
You already have localtunnel running (`npx localtunnel --port 5173`). 

**Comparison:**
| Feature | ngrok | localtunnel |
|---------|-------|-------------|
| Stability | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ |
| Speed | ⭐⭐⭐⭐⭐ | ⭐⭐⭐⭐ |
| Custom domains | Yes (paid) | No |
| Web UI | Yes | No |
| Setup | Requires install | NPM package |

**Recommendation**: Use ngrok for more reliable, production-like testing. Use localtunnel for quick, temporary sharing.

## Commands Reference

```powershell
# Start single tunnel
ngrok http 8000

# Start with custom subdomain (paid)
ngrok http 8000 --subdomain=myapp

# Start with basic auth
ngrok http 8000 --basic-auth="user:pass"

# Start all configured tunnels
ngrok start --all --config=ngrok.yml

# Check ngrok version
ngrok version

# View config
ngrok config check

# Update auth token
ngrok config add-authtoken <token>
```

## Next Steps

1. **Run the tunnel**: Execute `.\start-ngrok-both.ps1`
2. **Get URLs**: Note the public URLs from ngrok output
3. **Update configs**: Update `.env` and Google OAuth settings
4. **Test**: Access your app via the ngrok URLs
5. **Monitor**: Use http://localhost:4040 to inspect traffic

## Support
- [ngrok Documentation](https://ngrok.com/docs)
- [ngrok Dashboard](https://dashboard.ngrok.com/)
