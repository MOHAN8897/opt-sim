# option_simulator — Frontend Specification

## Purpose
Frontend is a **pure UI layer**. It does NOT handle secrets, direct API keys, or database connectivity. All sensitive logic flows through backend REST and WebSocket endpoints.

The frontend will display:
- Option chain with live prices
- Trade placement UI
- Order execution feedback
- Option Greeks (optional)
- Portfolio / open trades / history

Live price updates come via WebSocket from the backend (which collects data from Upstox WebSocket market feed) and forwarded to the frontend.

---

## 1. Authentication & Session Handling (MANDATORY)

### Login System
- Login via **Google OAuth**
- JWT stored in **HttpOnly cookies**
- NO `localStorage`
- NO `sessionStorage`

### Session Rules
- JWT expiration: **1–2 hours**
- If user inactive > **20 minutes**, backend invalidates session
- Frontend must:
  - Detect HTTP 401
  - Detect WebSocket closure
  - Redirect user to `/login`

### Logged-in Check
Before rendering any protected page (e.g., /trade):
- Call `/api/auth/me`
- If 401 → redirect to `/login`

---

## 2. Pages (UPDATED with Upstox Data Flow)

The frontend must call these backend REST endpoints for Upstox data:

Backend REST endpoints:
- `GET /api/upstox/option-chain?symbol=...&expiry=...`  
  - Returns option chain with instruments & strikes array  
  - Calls Upstox API: `GET /v2/option/chain` :contentReference[oaicite:1]{index=1}
- `GET /api/upstox/option-greeks?instrumentKeys=...` (optional)  
  - Calls Upstox `option-greek` endpoint :contentReference[oaicite:2]{index=2}

WebSocket:
- Connect post-login  
- Backend authenticates JWT → opens Upstox Market WebSocket  
- Subscribes to selected instrument keys (option strikes + underlying)  
- Upstox WebSocket (Market Data Feed V3) pushes updates over WS via backend :contentReference[oaicite:3]{index=3}

---

### `/` — Hero Page
- Login button
- Product description
- Footer links:
  - Privacy Policy
  - Terms & Conditions
  - Disclaimer
  - About

---

### `/login`
- Google Login
- Spinner during auth
- Successful login → redirect `/trade`

---

### `/connect-broker`
Upstox connection UI:
- Button: “Connect Upstox”
- Opens OAuth flow
- On success → show connected status

Frontend does not store access token.

---

### `/trade` — MAIN SCREEN

#### Top Bar
- User name
- Broker status
- Logout

#### Option Chain Panel
- Display strikes and instruments from `GET /api/upstox/option-chain`
- For each instrument:
  - Show latest LTP from WebSocket
  - Show bid/ask, IV/greeks if enabled

Live updates via frontend WS client that receives data forwarded from backend Upstox WebSocket.

---

### `/history`
- Past trades
- Filters and export options

---

### `/account`
- Upstox connection status
- Button: “Reconnect Upstox” (if token expired)
- Logout all sessions

---

## 3. Live Data (WebSocket) Handling

WebSocket flow:
- After JWT validation, frontend opens WS with backend
- Backend opens Upstox Market Feed WebSocket (V3)
  - Upstox allows subscription to up to ~2000 instruments per connection (LTPC) and handles option LTP feeds :contentReference[oaicite:4]{index=4}
  - Must decode protobuf messages
- Backend forwards filtered messages in JSON to frontend
- Option chain price changes appear live

---

## 4. UI Design Rules

- Black / Orange theme
- Use color coding for:
  - Green (profit)
  - Red (loss)
  - Neutral (grey)
- Smooth animations, responsive design
