# Lovable Frontend Integration & UX Specification
## option_simulator — React + WebSocket Frontend (Gamified Trading UI)

This document is the **final frontend contract** for building a modern, gamified, real-time options paper trading UI using React (Lovable-compatible), integrated with an existing secure Python backend.

The frontend is a **presentation + interaction layer only**.
All identity, permissions, trading logic, and market data ownership remain on the backend.

---

## 0. CORE FRONTEND PRINCIPLES (NON-NEGOTIABLE)

1. Frontend NEVER stores:
   - JWT
   - API keys
   - Upstox tokens
2. Frontend NEVER sends:
   - user_id
   - broker credentials
3. Frontend relies ONLY on:
   - HttpOnly cookies
   - Backend WebSocket push
4. Frontend must survive:
   - Page refresh
   - Token expiry
   - WebSocket reconnects
5. Frontend must feel:
   - Fast
   - Game-like
   - Visually rewarding

---

## 1. Project Dependencies (CONFIRMED + REQUIRED ADDITIONS)

### Core & Build
- `react`
- `react-dom`
- `vite`
- `typescript`

### Routing
- `react-router-dom`

### State & Data
- `@tanstack/react-query` (SERVER STATE)
- `axios`
- `zustand` (CLIENT/UI STATE)

### WebSocket
- native WebSocket API
- optional: `reconnecting-websocket`

### UI / Styling
- `tailwindcss`
- `lucide-react`
- `clsx`
- `tailwind-merge`
- `sonner` OR `react-hot-toast`
- `shadcn/ui` (Button, Card, Badge, Tabs, Table, Tooltip)

### Animation & Gamification (IMPORTANT)
- `framer-motion` (for trade feedback & transitions)
- `tailwindcss-animate`

### Forms & Validation
- `react-hook-form`
- `zod`

---

## 2. App Routing Structure (STRICT)

```text
/login
/signup (optional)
/ → Protected Layout
├── /dashboard
├── /trade
├── /portfolio
├── /account
/privacy-policy
/terms
/disclaimer
```

### Protected Route Rules
- All routes under `/` require authentication
- Use `<ProtectedRoute />` wrapper
- If `/api/auth/me` returns 401 → redirect to `/login`

---

## 3. Global App Providers (REQUIRED)

Lovable MUST generate these wrappers:

```tsx
<QueryClientProvider>
  <AuthProvider>
    <SocketProvider>
      <ThemeProvider>
        <Router />
      </ThemeProvider>
    </SocketProvider>
  </AuthProvider>
</QueryClientProvider>
```

---

## 4. API CLIENT (MANDATORY CONFIG)

```typescript
// src/lib/api.ts
import axios from "axios";

export const api = axios.create({
  baseURL: "/api",
  withCredentials: true, // REQUIRED
  headers: {
    "Content-Type": "application/json",
  },
});
```

**Rules:**
- NEVER attach Authorization header manually
- Cookies only
- Handle 401 globally via Axios interceptor

---

## 5. AUTH FLOW (FRONTEND RESPONSIBILITY)

**Login Flow**
1. User opens `/login`
2. Clicks Login with Google
3. Backend sets HttpOnly JWT
4. Frontend calls `/api/auth/me`
5. Success → redirect `/trade`

**Logout Flow**
1. Call `/api/auth/logout`
2. Clear all Zustand state
3. Close WebSocket
4. Redirect `/login`

---

## 6. 20-MINUTE INACTIVITY HANDLING (CRITICAL)

**Frontend MUST:**
- Track user activity (`mousemove`, `keydown`, `click`)
- Reset inactivity timer on activity

**If backend sends WS message:** `{ "type": "SESSION_EXPIRED" }`

**Frontend must:**
1. Show toast: “Session expired due to inactivity”
2. Close WebSocket
3. Clear all state
4. Redirect `/login`

❌ Do NOT attempt silent refresh
❌ Do NOT keep stale UI visible

---

## 7. WEBSOCKET HANDLING (CORE REAL-TIME LOGIC)

**Connection Rules**
- Connect ONLY after auth success
- One WS connection per user
- URL: `/ws/market`
- Backend authenticates via JWT cookie

**Message Types (MUST HANDLE)**
```typescript
type WSMessage =
  | { type: "LTP"; instrument_key: string; ltp: number }
  | { type: "PNL"; net_pnl: number }
  | { type: "TRADE_UPDATE"; trade: Trade }
  | { type: "SESSION_EXPIRED" }
  | { type: "ENGINE_STATUS"; status: "RUNNING" | "PAUSED" };
```

**Reconnect Rules**
- Auto-reconnect ONLY if: user is authenticated AND token not expired
- If reconnect fails → force logout

---

## 8. FRONTEND STATE MANAGEMENT (ZUSTAND)

**Auth Store**
```typescript
{
  isAuthenticated: boolean
  user: User | null
}
```

**Broker Store**
```typescript
{
  status: "CONNECTED" | "TOKEN_EXPIRED" | "NOT_CONNECTED"
  tokenExpiry: string | null
}
```

**Market Store (WS-driven)**
```typescript
{
  ltpMap: Record<string, number>
  netPnl: number
}
```

**Trade Store**
```typescript
{
  openTrades: Trade[]
  tradeHistory: Trade[]
}
```

**UI Store**
```typescript
{
  sidebarOpen: boolean
  theme: "dark"
}
```

---

## 9. OPTION CHAIN UI (GAME-LIKE DESIGN)

**Requirements**
- ATM strike highlighted
- CE on left, PE on right
- Strike in center
- **Color-coded LTP movement:**
    - Green flash → price up
    - Red flash → price down
- Disable BUY/SELL if: broker not connected OR engine paused

**Interaction**
- Hover shows: strike, instrument_key
- Click BUY / SELL opens **animated Order Modal**

---

## 10. ORDER PLACEMENT UX (GAMIFIED)

**Order Modal**
- Slide-in animation
- Confirm button with pulse effect

**On success:**
- Confetti / glow animation
- Toast: “Trade Opened 🎯”

**On failure:**
- Shake animation
- Error toast

---

## 11. TRADE MANAGER (REAL-TIME)

**Each open trade card:**
- Instrument name
- Entry price
- Live LTP (WS)
- Unrealized PnL (live)
- **Color:** Green = profit, Red = loss
- Exit button (instant feedback)

---

## 12. PORTFOLIO PAGE

**Sections**
- Open Positions (live)
- Trade History (paginated)
- Net PnL summary bar

---

## 13. CHARTING RULE (IMPORTANT DESIGN DECISION)

✅ Show ONLY underlying chart (TradingView embed)
❌ Do NOT build per-option candle charts

**Reason:** Option charts are misleading, heavy data load, and poor UX for retail users.

---

## 14. GAMIFICATION ELEMENTS (REQUIRED)

Lovable should include:
- PnL progress bar
- Daily streak indicator
- “Trades today” counter
- Win-rate badge (optional)
- Smooth micro-animations

*This is a simulator, not a broker terminal.*

---

## 15. ERROR & EDGE CASE HANDLING

**Frontend must gracefully handle:**
- Backend down
- WS disconnect
- Token expiry
- Broker disconnected
- No option data

**Always show:** Clear message + Actionable button

---

## 16. FINAL STRICT DO NOTs

❌ No localStorage JWT
❌ No secrets in frontend
❌ No polling for live prices
❌ No direct Upstox calls
❌ No cross-user data
