# OptionSim Design System

A comprehensive guide to the design system, color palette, component classes, and dependencies used in the OptionSim paper trading application.

---

## 📌 Project Overview

**OptionSim** is a gamified options paper trading simulator built with React. It features:
- Real-time option chain with live price updates
- Paper trading with virtual money
- Gamification elements (streaks, badges, P&L animations)
- Dark-themed, professional trading UI

---

## 🎨 Color System

All colors use HSL format in CSS variables defined in `src/index.css`.

### Core Colors

| Token | HSL Value | Usage | Tailwind Class |
|-------|-----------|-------|----------------|
| `--background` | `222 47% 6%` | Main app background | `bg-background` |
| `--foreground` | `210 40% 98%` | Primary text color | `text-foreground` |
| `--card` | `222 47% 8%` | Card backgrounds | `bg-card` |
| `--card-foreground` | `210 40% 98%` | Card text | `text-card-foreground` |
| `--popover` | `222 47% 10%` | Popover backgrounds | `bg-popover` |
| `--popover-foreground` | `210 40% 98%` | Popover text | `text-popover-foreground` |

### Brand Colors

| Token | HSL Value | Usage | Tailwind Class |
|-------|-----------|-------|----------------|
| `--primary` | `174 72% 56%` | Primary actions, CTAs | `bg-primary`, `text-primary` |
| `--primary-foreground` | `222 47% 6%` | Text on primary | `text-primary-foreground` |
| `--secondary` | `222 47% 14%` | Secondary backgrounds | `bg-secondary` |
| `--secondary-foreground` | `210 40% 98%` | Text on secondary | `text-secondary-foreground` |
| `--accent` | `265 89% 66%` | Accent/highlight color (purple) | `bg-accent`, `text-accent` |
| `--accent-foreground` | `210 40% 98%` | Text on accent | `text-accent-foreground` |
| `--muted` | `222 30% 18%` | Muted backgrounds | `bg-muted` |
| `--muted-foreground` | `215 20% 55%` | Muted/secondary text | `text-muted-foreground` |

### Trading Colors

| Token | HSL Value | Usage | Tailwind Class |
|-------|-----------|-------|----------------|
| `--profit` | `160 84% 39%` | Positive P&L, gains | `text-profit`, `bg-profit` |
| `--profit-glow` | `160 84% 50%` | Profit glow effects | - |
| `--loss` | `0 84% 60%` | Negative P&L, losses | `text-loss`, `bg-loss` |
| `--loss-glow` | `0 84% 70%` | Loss glow effects | - |
| `--neutral` | `220 14% 45%` | Neutral state | `text-neutral` |
| `--call` | `174 72% 56%` | Call options (cyan) | `text-call`, `bg-call` |
| `--call-bg` | `174 72% 10%` | Call column background | - |
| `--put` | `330 81% 60%` | Put options (pink) | `text-put`, `bg-put` |
| `--put-bg` | `330 81% 10%` | Put column background | - |
| `--atm` | `45 93% 58%` | ATM strike highlight (gold) | `text-atm`, `bg-atm` |
| `--atm-glow` | `45 93% 68%` | ATM glow effect | - |

### Gamification Colors

| Token | HSL Value | Usage | Tailwind Class |
|-------|-----------|-------|----------------|
| `--streak` | `45 93% 58%` | Win streak indicator | `text-streak` |
| `--xp` | `265 89% 66%` | Experience/XP | `text-xp` |
| `--badge-gold` | `43 96% 56%` | Gold badges | - |
| `--badge-silver` | `210 14% 66%` | Silver badges | - |
| `--badge-bronze` | `25 67% 50%` | Bronze badges | - |

### UI Colors

| Token | HSL Value | Usage | Tailwind Class |
|-------|-----------|-------|----------------|
| `--border` | `222 30% 18%` | Border color | `border-border` |
| `--input` | `222 30% 14%` | Input backgrounds | `bg-input` |
| `--ring` | `174 72% 56%` | Focus ring | `ring-ring` |
| `--destructive` | `0 84% 60%` | Destructive actions | `bg-destructive`, `text-destructive` |
| `--radius` | `0.75rem` | Default border radius | - |

---

## 🎭 Custom CSS Classes

### Trading Card
```css
.trade-card
```
A styled card component with gradient background, shadow, and hover glow effect.
- Border: `border-border`
- Background: gradient from card to darker
- Shadow: `--shadow-card`
- Hover: Gradient glow overlay

### P&L Indicators
```css
.pnl-profit  /* Green text with glow */
.pnl-loss    /* Red text with glow */
```

### Option Chain
```css
.atm-row     /* Gold-highlighted ATM strike row */
.call-column /* Cyan-tinted call column */
.put-column  /* Pink-tinted put column */
```

### Price Flash Animations
```css
.flash-green /* Green flash on price increase */
.flash-red   /* Red flash on price decrease */
```

### Effects
```css
.glass       /* Glassmorphism effect */
.live-pulse  /* Live data indicator with pulsing dot */
.badge-glow  /* Badge with blur glow effect */
.btn-glow-primary /* Button with primary color glow */
```

### Text Gradients
```css
.text-gradient-primary  /* Cyan gradient text */
.text-gradient-profit   /* Green gradient text */
```

---

## 🎬 Animations

### Keyframe Animations (tailwind.config.ts)

| Animation | Duration | Usage |
|-----------|----------|-------|
| `fade-in` | 0.3s | Element entrance |
| `fade-out` | 0.3s | Element exit |
| `scale-in` | 0.2s | Scale up entrance |
| `slide-in-right` | 0.3s | Sidebar/drawer entrance |
| `slide-in-up` | 0.4s | Bottom sheet entrance |
| `pulse-glow` | 2s infinite | Glowing effect |
| `shake` | 0.5s | Error feedback |
| `bounce-in` | 0.4s | Playful entrance |
| `number-tick` | 0.3s | Number change animation |

### Tailwind Animation Classes
```
animate-fade-in
animate-fade-out
animate-scale-in
animate-slide-in-right
animate-slide-in-up
animate-pulse-glow
animate-shake
animate-bounce-in
animate-number-tick
```

---

## 📦 Dependencies

### Core Framework
| Package | Version | Purpose |
|---------|---------|---------|
| `react` | ^18.3.1 | UI framework |
| `react-dom` | ^18.3.1 | React DOM renderer |
| `react-router-dom` | ^6.30.1 | Client-side routing |
| `typescript` | (via Vite) | Type safety |

### State Management
| Package | Version | Purpose |
|---------|---------|---------|
| `zustand` | ^5.0.10 | Client/UI state |
| `@tanstack/react-query` | ^5.83.0 | Server state & caching |

### Styling
| Package | Version | Purpose |
|---------|---------|---------|
| `tailwindcss` | (via Vite) | Utility-first CSS |
| `tailwindcss-animate` | ^1.0.7 | Animation utilities |
| `tailwind-merge` | ^2.6.0 | Class merging |
| `clsx` | ^2.1.1 | Conditional classes |
| `class-variance-authority` | ^0.7.1 | Component variants |

### UI Components (shadcn/ui)
| Package | Version | Purpose |
|---------|---------|---------|
| `@radix-ui/react-*` | Various | Headless UI primitives |
| `lucide-react` | ^0.462.0 | Icons |
| `cmdk` | ^1.1.1 | Command palette |

### Animation
| Package | Version | Purpose |
|---------|---------|---------|
| `framer-motion` | ^12.26.2 | Advanced animations |

### Data & API
| Package | Version | Purpose |
|---------|---------|---------|
| `axios` | ^1.13.2 | HTTP client |
| `reconnecting-websocket` | ^4.4.0 | Auto-reconnecting WS |

### Forms
| Package | Version | Purpose |
|---------|---------|---------|
| `react-hook-form` | ^7.61.1 | Form handling |
| `@hookform/resolvers` | ^3.10.0 | Form validation |
| `zod` | ^3.25.76 | Schema validation |

### Utilities
| Package | Version | Purpose |
|---------|---------|---------|
| `date-fns` | ^3.6.0 | Date formatting |
| `recharts` | ^2.15.4 | Charts (portfolio) |
| `sonner` | ^1.7.4 | Toast notifications |

---

## 🗂️ Project Structure

```
src/
├── components/
│   ├── layout/
│   │   ├── MainLayout.tsx      # App shell with sidebar
│   │   └── Navbar.tsx          # Top navigation bar
│   ├── trading/
│   │   ├── OptionChain.tsx     # Option chain table
│   │   ├── OrderModal.tsx      # Order placement modal
│   │   ├── TradeManager.tsx    # Open positions panel
│   │   └── RiskCalculator.tsx  # Risk/reward calculator
│   └── ui/                     # shadcn/ui components
├── pages/
│   ├── LandingPage.tsx         # Public hero page
│   ├── DashboardPage.tsx       # User dashboard
│   ├── TradePage.tsx           # Option chain trading
│   ├── PortfolioPage.tsx       # Portfolio & history
│   └── AccountPage.tsx         # Account settings
├── stores/
│   ├── authStore.ts            # Authentication state
│   ├── brokerStore.ts          # Broker connection state
│   ├── marketStore.ts          # Live market data (WS)
│   ├── tradeStore.ts           # Trades & positions
│   └── uiStore.ts              # UI state (modals, sidebar)
├── providers/
│   ├── AuthProvider.tsx        # Auth context & 401 handling
│   └── SocketProvider.tsx      # WebSocket management
├── lib/
│   ├── api.ts                  # Axios instance
│   └── utils.ts                # Utility functions
├── index.css                   # Design system CSS
└── App.tsx                     # App routes & providers
```

---

## 🔐 Security Notes

The frontend follows these security principles:
- **No JWT storage**: Authentication via HttpOnly cookies only
- **No credential handling**: Backend manages all auth tokens
- **Global 401 handling**: Axios interceptor redirects to login
- **20-minute inactivity timeout**: Session expires on inactivity
- **WebSocket auth**: Backend validates JWT cookie on WS connection

---

## 🎮 Gamification Elements

1. **Win Streak**: Consecutive profitable trade counter
2. **Daily Goals**: Progress bar for trades completed
3. **P&L Animations**: Green/red flashes on price changes
4. **Trade Feedback**: Success confetti, error shake
5. **Badges**: Achievement system (planned)

---

## 📱 Responsive Design

- Mobile-first approach
- Collapsible sidebar on mobile
- Responsive option chain with horizontal scroll
- Adaptive card layouts

---

## 🚀 Quick Start

```bash
# Install dependencies
npm install

# Start development server
npm run dev

# Build for production
npm run build
```

---

## 📝 Notes

- All colors must use HSL format
- Use semantic token classes, never raw colors
- Animations should enhance UX, not distract
- Keep components small and focused
- Use Zustand for client state, React Query for server state
