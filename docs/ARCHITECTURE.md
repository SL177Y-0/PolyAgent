# PolyAgent Architecture Guide

<div align="center">

**A comprehensive technical deep-dive into the PolyAgent trading system**

</div>

---

## Table of Contents

1. [Overview](#overview)
2. [System Architecture](#system-architecture)
3. [Backend Components](#backend-components)
4. [Frontend Components](#frontend-components)
5. [Data Flow](#data-flow)
6. [Trading Engine](#trading-engine)
7. [WebSocket Architecture](#websocket-architecture)
8. [State Management](#state-management)
9. [Security Architecture](#security-architecture)
10. [API Design](#api-design)
11. [Configuration System](#configuration-system)
12. [Extension Points](#extension-points)

---

## Overview

PolyAgent is a **modular, production-ready trading bot** for Polymarket prediction markets. The architecture follows these principles:

- **Separation of Concerns**: Backend (Python) handles trading, Frontend (Next.js) handles UI
- **Multi-Bot Isolation**: Each bot runs as an independent session with its own wallet and config
- **Real-Time Communication**: WebSockets provide sub-second updates to the UI
- **State Persistence**: All state is persisted to disk for crash recovery
- **Security First**: Private keys encrypted at rest, never exposed to frontend

---

## System Architecture

### High-Level Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER BROWSER                                  │
│                                                                         │
│  ┌────────────────────────────────────────────────────────────────────┐ │
│  │                      Next.js Frontend (Port 3000)                  │ │
│  │                                                                    │ │
│  │  ┌───────────────┐  ┌───────────────┐  ┌───────────────────────┐   │ │
│  │  │  React App    │  │ BotState      │  │  Component Library    │   │ │
│  │  │  (app/)       │  │ Context       │  │  (components/)        │   │ │
│  │  └───────┬───────┘  └───────┬───────┘  └───────────────────────┘   │ │
│  │          │                  │                                      │ │
│  │          └──────────────────┼──────────────────────────────────────│ │
│  │                             │                                      │ │
│  │                    ┌────────┴────────┐                             │ │
│  │                    │  WebSocket      │                             │ │
│  │                    │  Connection     │                             │ │
│  │                    └────────┬────────┘                             │ │
│  └─────────────────────────────┼──────────────────────────────────────┘ │
└────────────────────────────────┼────────────────────────────────────────┘
                                 │
                    WebSocket + REST (Port 8000)
                                 │
┌────────────────────────────────┼────────────────────────────────────────┐
│                     SERVER PROCESS                                      │
│                                │                                        │
│  ┌─────────────────────────────┼────────────────────────────────────┐   │
│  │                   FastAPI Backend                                │   │
│  │                             │                                    │   │
│  │  ┌──────────────────────────┴──────────────────────────────────┐ │   │
│  │  │                   API Server (api_server.py)                │ │   │
│  │  │                                                             │ │   │
│  │  │  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────┐  │ │   │
│  │  │  │ REST Endpoints  │  │ WS Manager      │  │ Event Loop  │  │ │   │
│  │  │  │                 │  │ (Broadcast)     │  │ (asyncio)   │  │ │   │
│  │  │  └─────────────────┘  └─────────────────┘  └─────────────┘  │ │   │
│  │  └──────────────────────────┬──────────────────────────────────┘ │   │
│  │                             │                                    │   │
│  │  ┌──────────────────────────┼──────────────────────────────────┐ │   │
│  │  │              Bot Session Registry                           │ │   │
│  │  │                          │                                  │ │   │
│  │  │  ┌───────────┐  ┌───────┴───────┐  ┌─────────────────────┐  │ │   │
│  │  │  │ Session 1 │  │  Session 2    │  │    Session N        │  │ │   │
│  │  │  │           │  │               │  │                     │  │ │   │
│  │  │  │ ┌───────┐ │  │ ┌───────────┐ │  │ ┌─────────────────┐ │  │ │   │
│  │  │  │ │ Bot   │ │  │ │   Bot     │ │  │ │      Bot        │ │  │ │   │
│  │  │  │ │Engine │ │  │ │  Engine   │ │  │ │     Engine      │ │  │ │   │
│  │  │  │ └───┬───┘ │  │ └─────┬─────┘ │  │ └───────┬─────────┘ │  │ │   │
│  │  │  │     │     │  │       │       │  │         │           │  │ │   │
│  │  │  │ ┌───┴───┐ │  │ ┌─────┴─────┐ │  │ ┌───────┴─────────┐ │  │ │   │
│  │  │  │ │Client │ │  │ │  Client   │ │  │ │     Client      │ │  │ │   │
│  │  │  │ └───────┘ │  │ └───────────┘ │  │ └─────────────────┘ │  │ │   │
│  │  │  └───────────┘  └───────────────┘  └─────────────────────┘  │ │   │
│  │  └─────────────────────────────────────────────────────────── ─┘ │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
                                 │
                     External Polymarket APIs
                                 │
         ┌───────────────────────┼───────────────────────┐
         │                       │                       │
    ┌────┴────┐          ┌───────┴───────┐       ┌───────┴───────┐
    │CLOB API │          │Market WebSckeT│       │  Gamma API    │
    │ (REST)  │          │(Price Updates)│       │(Market Info)  │
    └─────────┘          └───────────────┘       └───────────────┘
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Frontend** | Next.js 16, React 19, TypeScript | User interface |
| **UI Components** | shadcn/ui, Radix UI, Tailwind CSS | Component library |
| **Charts** | Recharts | Price visualization |
| **Backend** | FastAPI, Python 3.10+ | API server, trading logic |
| **WebSocket** | websockets, uvicorn | Real-time communication |
| **Trading SDK** | py-clob-client | Polymarket integration |
| **Encryption** | cryptography (Fernet) | Secure config storage |
| **Testing** | pytest, Playwright | Backend and E2E tests |

---

## Backend Components

### 1. API Server (`src/api_server.py`)

The central orchestrator that handles all HTTP and WebSocket communication.

```python
# Key responsibilities:
# - REST API endpoints for bot management
# - WebSocket connection manager for real-time updates
# - Bot lifecycle management (start/stop/pause)
# - Session registry maintenance
# - Event broadcasting to connected clients
```

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `ConnectionManager` | Manages WebSocket connections, handles broadcast |
| `BotStatus` | Pydantic model for bot status responses |
| `CreateBotRequest` | Pydantic model for bot creation |
| `UpdateBotRequest` | Pydantic model for bot updates |
| `TradeRequest` | Pydantic model for manual trades |

**Startup Flow:**

```
1. FastAPI app created with CORS middleware
2. On startup:
   - Load all saved bot configurations from data/bots/
   - Create BotSession for each
   - Attach WebSocket callbacks
   - Store in active sessions registry
3. Ready to accept connections
```

### 2. Bot Session (`src/bot_session.py`)

An isolated, independent bot instance with complete encapsulation.

```python
# Each BotSession has:
# - Its own BotConfigData (wallet, market, strategy)
# - Its own Bot engine instance
# - Its own Client instance
# - Its own background thread for execution
# - Its own activity log
# - Its own price history
```

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `BotConfigData` | Serializable configuration with encryption |
| `BotSession` | Complete isolated bot with lifecycle methods |
| `ActivityLog` | In-memory activity store with callbacks |

**Session Lifecycle:**

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Created   │ ──▶│   Stopped   │ ──▶ │   Running   │ ──▶│   Stopped   │
│             │     │             │     │             │     │             │
│ Config only │     │ Ready to    │     │ Trading     │     │ Stopped by  │
│ No thread   │     │ start       │     │ actively    │     │ user/error  │
└─────────────┘     └─────────────┘     └─────────────┘     └─────────────┘
                           │                   ▲
                           └───────────────────┘
                              (re-startable)
```

### 3. Bot Engine (`src/bot.py`)

The core trading logic that implements the Spike Sam strategy.

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `TradeTarget` | Represents current buy/sell target |
| `Position` | Tracks active position with P&L |
| `Bot` | Main orchestrator class |

**Bot State Machine:**

```
┌───────────────────────────────────────────────────────────────┐
│                       Bot Trading Cycle                       │
│                                                               │
│  ┌─────────┐         ┌─────────────┐         ┌─────────────┐  │
│  │ No      │  BUY    │ Have        │  SELL   │ No          │  │
│  │Position │ ──────▶ │ Position    │ ──────▶│ Position    │  │
│  │         │         │             │         │             │  │
│  │Set BUY  │         │Track P&L    │         │Set BUY      │  │
│  │Target   │         │Check TP/SL  │         │Target       │  │
│  └────┬────┘         └──────┬──────┘         └─────────────┘  │
│       │                     │                                 │
│       │                     │ Risk Exit                       │
│       │                     │ (TP/SL/Time)                    │
│       │                     ▼                                 │
│       │              ┌──────────────┐                         │
│       │              │ Force Exit   │                         │
│       │              │ Position     │                         │
│       │              └──────┬───────┘                         │
│       │                     │                                 │
│       └─────────────────────┘                                 │
└───────────────────────────────────────────────────────────────┘
```

**Spike Detection Algorithm:**

```python
def _compute_spike_multi_window(current_price):
    """Multi-window spike detection with volatility filtering."""
    
    windows = [10, 30, 60]  # minutes
    max_spike = 0
    
    for window in windows:
        # Get prices from window
        prices = get_prices_in_window(window)
        
        if len(prices) < min_required:
            continue
            
        # Calculate spike percentage
        oldest_price = prices[0]
        spike_pct = (current_price - oldest_price) / oldest_price * 100
        
        # Volatility filter (coefficient of variation)
        cv = std(prices) / mean(prices)
        if cv > cv_threshold:
            continue  # Too volatile, skip
        
        max_spike = max(max_spike, abs(spike_pct))
    
    return max_spike
```

### 4. CLOB Client (`src/clob_client.py`)

Wrapper around `py-clob-client` with Polymarket-specific helpers.

**Key Methods:**

| Method | Purpose |
|--------|---------|
| `resolve_token_id()` | Resolve market slug to token ID via Gamma API |
| `get_polymarket_price()` | Get price using Polymarket's logic (mid or last) |
| `get_mid_price()` | Simple midpoint of best bid/ask |
| `get_orderbook_metrics()` | Spread, depth, liquidity analysis |
| `place_market_order()` | Execute market order with size |
| `place_limit_order()` | Place limit order at price |
| `has_sufficient_balance()` | Check USDC.e balance and allowance |
| `verify_token_ownership()` | Confirm token settlement before sell |

**Polymarket Price Logic:**

```python
def get_polymarket_price(token_id):
    """
    Polymarket displays prices as:
    - If spread <= $0.10: midpoint of best bid/ask
    - If spread > $0.10: last trade price
    """
    orderbook = get_orderbook(token_id)
    best_bid = orderbook.bids[0].price
    best_ask = orderbook.asks[0].price
    spread = best_ask - best_bid
    
    if spread <= 0.10:
        return (best_bid + best_ask) / 2
    else:
        return get_last_trade_price(token_id)
```

### 5. Config (`src/config.py`)

Typed configuration with validation and trading profiles.

**Key Classes:**

| Class | Purpose |
|-------|---------|
| `Config` | Main configuration dataclass |
| `TradingProfile` | Pre-defined trading parameter sets |

**Configuration Hierarchy:**

```
Default Values (in Config class)
       │
       ▼
Trading Profile (Normal, Live, Edge, etc.)
       │
       ▼
Per-Bot Overrides (from UI)
       │
       ▼
Final Config
```

### 6. WebSocket Clients

**Market WebSocket (`src/websocket_client.py`):**
- Connects to `wss://ws-subscriptions-clob.polymarket.com/ws/market`
- Subscribes to token ID for real-time updates
- Receives: `book`, `price_change`, `last_trade_price`
- Provides thread-safe price access

**User WebSocket (`src/user_websocket_client.py`):**
- Connects to `wss://ws-subscriptions-clob.polymarket.com/ws/user`
- Requires API key authentication
- Receives: order status, trade confirmations
- Tracks pending settlements

### 7. Encryption (`src/crypto.py`)

Secure storage for sensitive configuration data.

```python
# Encryption flow:
1. Generate machine-specific salt (from username + home path)
2. Derive Fernet key using PBKDF2 (480000 iterations)
3. Encrypt private key with Fernet
4. Store encrypted value with "enc:" prefix
5. Decrypt on load using same derived key
```

---

## Frontend Components

### Component Hierarchy

```
App (layout.tsx)
└── BotStateProvider (contexts/bot-state-context.tsx)
    └── Page (page.tsx)
        ├── HeaderBar
        │   ├── Logo
        │   ├── Settings Button
        │   └── Theme Toggle
        │
        ├── DashboardSummary
        │   ├── Total P&L
        │   ├── Active Bots
        │   └── Today's Trades
        │
        ├── BotManagerPanel
        │   ├── Bot List
        │   ├── Bot Cards
        │   └── Create Bot Form
        │
        ├── Selected Bot Details
        │   ├── PriceChart
        │   ├── PositionCard
        │   ├── TargetInfoCard
        │   ├── MarketMetricsCard
        │   └── SessionStats
        │
        ├── ActivityFeed
        │   ├── Filter Buttons
        │   └── Activity Items
        │
        └── SettingsPanel (Modal)
            ├── Global Settings
            ├── Killswitch
            └── Daily Limits
```

### BotStateContext

Central state management using React Context + WebSocket.

```typescript
interface BotState {
  bots: Map<string, Bot>;
  selectedBotId: string | null;
  activities: Activity[];
  settings: GlobalSettings;
  wsConnected: boolean;
}

// Key actions:
type Action =
  | { type: 'SET_BOTS'; bots: Bot[] }
  | { type: 'UPDATE_BOT'; botId: string; updates: Partial<Bot> }
  | { type: 'SELECT_BOT'; botId: string }
  | { type: 'ADD_ACTIVITY'; activity: Activity }
  | { type: 'WS_MESSAGE'; message: WSMessage }
  | { type: 'SET_SETTINGS'; settings: GlobalSettings };
```

**WebSocket Integration:**

```typescript
// WebSocket connection in BotStateContext
useEffect(() => {
  const ws = new WebSocket('ws://localhost:8000/ws');
  
  ws.onmessage = (event) => {
    const message = JSON.parse(event.data);
    
    switch (message.type) {
      case 'price':
        dispatch({ type: 'UPDATE_PRICE', ...message });
        break;
      case 'position':
        dispatch({ type: 'UPDATE_POSITION', ...message });
        break;
      case 'activity':
        dispatch({ type: 'ADD_ACTIVITY', activity: message });
        break;
      case 'target':
        dispatch({ type: 'UPDATE_TARGET', ...message });
        break;
    }
  };
  
  return () => ws.close();
}, []);
```

### Key Panels

#### BotManagerPanel

Bot CRUD operations and configuration:

```
┌─────────────────────────────────────────────────────┐
│ Bot Manager                           [+ Create]    │
├─────────────────────────────────────────────────────┤
│ ┌─────────────────────────────────────────────────┐ │
│ │ 🟢 BTC Election Bot                    [▶][⏸] │ │
│ │    Status: Running | P&L: +$12.50               │ │
│ │    Market: will-trump-win-2024                  │ │
│ └─────────────────────────────────────────────────┘ │
│ ┌─────────────────────────────────────────────────┐ │
│ │ 🔴 ETH Market Bot                      [▶][⏸] │ │
│ │    Status: Stopped | P&L: -$2.30                │ │
│ │    Market: eth-above-4000                       │ │
│ └─────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────┘
```

#### PriceChart

Real-time price visualization:

```
┌─────────────────────────────────────────────────────┐
│ Price Chart                            [1H][4H][1D] │
├─────────────────────────────────────────────────────┤
│                                                     │
│  0.60 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ SELL TARGET ─ ─ ─   │
│       │                                             │
│  0.55 │        ╱╲                                   │
│       │       ╱  ╲     ╱╲                           │
│  0.50 │    ──╱────╲───╱──╲── ENTRY ────────────     │
│       │   ╱         ╲╱                              │
│  0.45 ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ BUY TARGET ─ ─ ─ ─    │
│       │                                             │
│  0.40 └──────────────────────────────────────────── │
│        10:00    11:00    12:00    13:00    14:00    │
└─────────────────────────────────────────────────────┘
```

#### PositionCard

Current position details:

```
┌─────────────────────────────────────────────────────┐
│ Current Position                           [CLOSE]  │
├─────────────────────────────────────────────────────┤
│                                                     │
│  Side: LONG (BUY)          Entry: $0.50             │
│  Amount: $5.00             Current: $0.52           │
│                                                     │
│  ┌────────────────────────────────────────────────┐ │
│  │ Unrealized P&L                                 │ │
│  │                                                │ │
│  │    +$0.20 (+4.00%)                             │ │
│  │    ████████████████░░░░░░░░░░░░░░░░░  80% to TP│ │
│  └────────────────────────────────────────────────┘ │
│                                                     │
│  Hold Time: 15m 32s          Max: 60m               │
│  Take Profit: +5% at $0.525                         │
│  Stop Loss: -3% at $0.485                           │
└─────────────────────────────────────────────────────┘
```

---

## Data Flow

### Price Update Flow

```
┌──────────────────┐
│ Polymarket WS    │
│ (Market Channel) │
└────────┬─────────┘
         │ price_change event
         ▼
┌──────────────────┐
│ WebSocketSync    │
│ Wrapper          │
│ (Thread-safe)    │
└────────┬─────────┘
         │ get_polymarket_price()
         ▼
┌──────────────────┐
│ Bot.tick()       │
│ - Add to history │
│ - Compute spike  │
│ - Check targets  │
└────────┬─────────┘
         │ on_price_update callback
         ▼
┌──────────────────┐
│ BotSession       │
│ - Format message │
│ - Add bot_id     │
└────────┬─────────┘
         │ via API server callback
         ▼
┌──────────────────┐
│ ConnectionManager│
│ .broadcast()     │
└────────┬─────────┘
         │ JSON message
         ▼
┌──────────────────┐
│ Frontend WS      │
│ onmessage        │
└────────┬─────────┘
         │ dispatch action
         ▼
┌──────────────────┐
│ BotStateContext  │
│ reducer          │
└────────┬─────────┘
         │ state update
         ▼
┌──────────────────┐
│ React Components │
│ re-render        │
└──────────────────┘
```

### Trade Execution Flow

```
┌────────────────┐
│ Trade Signal   │
│ (spike/target) │
└───────┬────────┘
        ▼
┌────────────────┐     No      ┌────────────────┐
│ Dry Run Mode?  │───────────▶│ Check Balance  │
└───────┬────────┘             └───────┬────────┘
        │ Yes                          ▼
        ▼                       ┌────────────────┐
┌────────────────┐              │ Check Orderbook│
│ Simulate Trade │              │ Liquidity      │
│ Log Activity   │              └───────┬────────┘
└───────┬────────┘                      ▼
        │                        ┌────────────────┐
        │                        │ Place Order    │
        │                        │ (Market Order) │
        │                        └───────┬────────┘
        │                                ▼
        │                        ┌────────────────┐
        │                        │ Verify Fill    │
        │                        │ or Retry       │
        │                        └───────┬────────┘
        │                                │
        └────────────────────────────────┘
                      │
                      ▼
              ┌────────────────┐
              │ Update Position│
              │ Set Next Target│
              │ Log Activity   │
              └───────┬────────┘
                      │
                      ▼
              ┌────────────────┐
              │ Broadcast via  │
              │ WebSocket      │
              └────────────────┘
```

---

## Trading Engine

### Spike Sam Strategy Details

The core trading strategy "fades" sudden price movements:

```python
class SpikeSamStrategy:
    """
    Philosophy: Large sudden price movements tend to revert.
    
    On downward spike: BUY (expect bounce back up)
    On upward spike: SELL/FADE (expect reversion down)
    """
    
    def analyze(self, spike_pct, direction):
        if abs(spike_pct) < threshold:
            return IGNORE
            
        if direction == DOWN:
            # Price dropped sharply - buy the dip
            return BUY_SIGNAL
        else:
            # Price spiked up - fade the move
            return SELL_SIGNAL
```

### Train of Trade Strategy

Sequential, predictable trading pattern:

```
State: WANT_TO_BUY
│
│ Set BUY target = current_price × (1 - spike_threshold)
│
└─▶ Price reaches target
    │
    │ Execute BUY
    │
    ▼
State: HAVE_BOUGHT (holding position)
│
│ Set SELL target = entry_price × (1 + take_profit)
│
└─▶ Price reaches target OR risk exit (SL/time)
    │
    │ Execute SELL
    │ Calculate P&L
    │
    ▼
State: WANT_TO_BUY (cycle repeats)
```

### Risk Management

```python
def check_risk_exit(position, current_price):
    """Check if position should be force-exited."""
    
    # 1. Take Profit
    pnl_pct = position.calculate_pnl(current_price)
    if pnl_pct >= take_profit_pct:
        return f"take_profit_+{pnl_pct}%"
    
    # 2. Stop Loss
    if pnl_pct <= -stop_loss_pct:
        return f"stop_loss_{pnl_pct}%"
    
    # 3. Time-based exit
    if position.age_seconds >= max_hold_seconds:
        return f"time_exit_{position.age_seconds}s"
    
    return None  # No exit needed
```

---

## WebSocket Architecture

### Backend WebSocket Server

```python
# Connection Manager Pattern
class ConnectionManager:
    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()
    
    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
    
    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            self.active_connections.remove(websocket)
    
    async def broadcast(self, message: dict):
        """Send message to all connected clients."""
        async with self._lock:
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except:
                    await self.disconnect(connection)
```

### Message Types

```typescript
// Server → Client messages
interface WSMessage {
  type: 'price' | 'position' | 'spike' | 'activity' | 'target' | 'error';
  bot_id: string;
  timestamp: string;
  // ... type-specific data
}

// Price update
{
  type: "price",
  bot_id: "bot_abc123",
  price: 0.5234,
  best_bid: 0.52,
  best_ask: 0.53,
  timestamp: "2025-01-18T10:30:00Z"
}

// Position update
{
  type: "position",
  bot_id: "bot_abc123",
  position: {
    side: "BUY",
    entry_price: 0.50,
    amount_usd: 5.00,
    pnl_pct: 4.68,
    pnl_usd: 0.234
  }
}

// Activity
{
  type: "activity",
  bot_id: "bot_abc123",
  activity_type: "order",
  message: "Order filled: BUY $5.00 @ 0.50"
}
```

---

## State Management

### Backend State

```
┌─────────────────────────────────────────────────────────────┐
│                    Backend State                            │
│                                                             │
│  In Memory                          Disk Persistence        │
│  ───────────────                    ────────────────        │
│  ┌──────────────┐                   ┌─────────────────────┐ │
│  │ Active       │                   │ data/bots/*.json    │ │
│  │ Sessions     │◀─── serialize ───▶│ (encrypted configs)│ │
│  │ (Dict)       │                   │                     │ │
│  └──────────────┘                   └─────────────────────┘ │
│                                                             │
│  ┌──────────────┐                   ┌─────────────────────┐ │
│  │ Connection   │                   │ data/settings.json  │ │
│  │ Manager      │                   │ (global settings)   │ │
│  │ (WebSockets) │                   │                     │ │
│  └──────────────┘                   └─────────────────────┘ │
│                                                             │
│  ┌──────────────┐                   ┌─────────────────────┐ │
│  │ Price        │                   │ data/position.json  │ │
│  │ History      │                   │ (legacy backup)     │ │
│  │ (per bot)    │                   │                     │ │
│  └──────────────┘                   └─────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
```

### Frontend State

```typescript
// BotStateContext state shape
interface AppState {
  // Bot data
  bots: Map<string, BotState>;
  selectedBotId: string | null;
  
  // Real-time data
  activities: Activity[];
  priceHistory: Map<string, PricePoint[]>;
  
  // Settings
  settings: GlobalSettings;
  
  // Connection status
  wsConnected: boolean;
  lastUpdate: Date;
}

// Per-bot state
interface BotState {
  id: string;
  name: string;
  status: 'running' | 'stopped' | 'paused' | 'error';
  config: BotConfig;
  
  // Live data
  currentPrice: number;
  position: Position | null;
  target: TradeTarget | null;
  
  // Statistics
  realizedPnl: number;
  totalTrades: number;
  winRate: number;
}
```

---

## Security Architecture

### Threat Model

| Threat | Mitigation |
|--------|------------|
| Private key exposure | Fernet encryption at rest |
| Network interception | HTTPS for production, local-only development |
| Unauthorized access | No auth currently (local deployment assumed) |
| Configuration tampering | Encrypted storage, machine-specific key |
| Replay attacks | Polymarket nonce handling |

### Encryption Details

```python
# Key derivation
def derive_key():
    # Machine-specific identifier
    machine_id = f"{username}:{home_path}:polyagent-v1"
    
    # Load or generate salt
    salt = load_or_create_salt("data/.encryption_key")
    
    # Derive key with PBKDF2
    kdf = PBKDF2HMAC(
        algorithm=SHA256(),
        length=32,
        salt=salt,
        iterations=480000,  # High iteration count
    )
    
    return Fernet(base64.urlsafe_b64encode(kdf.derive(machine_id)))
```

### Data at Rest

```
data/
├── .encryption_key     # Salt only (32 bytes)
├── bots/
│   └── bot_abc123.json # Encrypted private key inside
│                       # {
│                       #   "private_key": "enc:gAAA...",
│                       #   "name": "My Bot",
│                       #   ...
│                       # }
└── settings.json       # Not encrypted (no sensitive data)
```

---

## API Design

### RESTful Principles

```
GET    /api/bots              # List all bots
POST   /api/bots              # Create new bot
GET    /api/bots/{id}         # Get specific bot
PUT    /api/bots/{id}         # Update bot
DELETE /api/bots/{id}         # Delete bot
POST   /api/bots/{id}/start   # Start bot
POST   /api/bots/{id}/stop    # Stop bot
POST   /api/bots/{id}/trade   # Manual trade
GET    /api/bots/{id}/activities  # Get activities
```

### Response Format

```json
// Success response
{
  "status": "success",
  "data": { ... }
}

// Error response
{
  "status": "error",
  "error": {
    "code": "BOT_NOT_FOUND",
    "message": "Bot with ID xyz not found"
  }
}
```

---

## Configuration System

### Configuration Hierarchy

```
1. Hardcoded Defaults (config.py)
   │
   ▼
2. Trading Profile (Normal/Live/Edge)
   │
   ▼
3. Per-Bot Overrides (from UI)
   │
   ▼
4. Final Merged Config
```

### Trading Profiles

```python
PROFILES = {
    "normal": TradingProfile(
        spike_threshold_pct=3.0,
        take_profit_pct=5.0,
        stop_loss_pct=3.0,
        trade_size_usd=5.0,
        max_hold_seconds=3600,
        cooldown_sec=120,
        dry_run=True,
    ),
    "live": TradingProfile(
        spike_threshold_pct=2.5,
        take_profit_pct=4.0,
        stop_loss_pct=2.5,
        trade_size_usd=10.0,
        max_hold_seconds=1800,
        cooldown_sec=60,
        dry_run=False,
    ),
    # ... more profiles
}
```

---

## Extension Points

### Adding a New Strategy

1. Create strategy class in `src/strategies/`:

```python
class MyStrategy:
    def analyze(self, price_history, current_price, config):
        """Return trade signal or None."""
        # Your logic here
        return {"action": "buy", "size_usd": 5.0, "reason": "..."}
```

2. Register in Bot class:

```python
# In bot.py
self.strategy = MyStrategy() if config.strategy == "my_strategy" else SpikeSam()
```

### Adding a New Panel

1. Create component in `frontend/components/panels/`:

```tsx
export function MyPanel({ botId }: { botId: string }) {
  const { bots } = useBotState();
  const bot = bots.get(botId);
  
  return (
    <Card>
      <CardHeader>My Panel</CardHeader>
      <CardContent>{/* Your UI */}</CardContent>
    </Card>
  );
}
```

2. Add to page layout in `app/page.tsx`

### Adding New API Endpoints

1. Add endpoint in `api_server.py`:

```python
@app.get("/api/my-endpoint")
async def my_endpoint():
    return {"data": "..."}
```

2. Add frontend fetch in component:

```typescript
const response = await fetch('http://localhost:8000/api/my-endpoint');
const data = await response.json();
```

---

## Performance Considerations

### Backend Optimization

- **Thread per bot**: Each bot runs in its own thread for isolation
- **Asyncio for WebSocket**: Non-blocking broadcast to all clients
- **Price deduplication**: Skip updates if price unchanged
- **Lazy client initialization**: CLOB client created on first use

### Frontend Optimization

- **React.memo**: Heavy components memoized
- **Debounced updates**: Chart updates throttled
- **Virtual scrolling**: Activity feed uses windowing for large lists
- **WebSocket reconnection**: Automatic reconnection with backoff

---

## Deployment Considerations

### Development (Current)

```
localhost:3000 (Frontend) ──▶ localhost:8000 (Backend)
```

### Production (Future)

```
                    ┌─────────────┐
                    │   Nginx     │
                    │   Reverse   │
                    │   Proxy     │
                    └──────┬──────┘
                           │
           ┌───────────────┼───────────────┐
           │               │               │
      ┌────▼────┐    ┌─────▼─────┐   ┌─────▼─────┐
      │ Static  │    │  API      │   │  WebSocket│
      │ Next.js │    │  Server   │   │  Server   │
      │ Build   │    │(uvicorn)  │   │  (uvicorn)│
      └─────────┘    └───────────┘   └───────────┘
```

---

## Conclusion

PolyAgent's architecture emphasizes:

1. **Modularity**: Each component has a single responsibility
2. **Isolation**: Bots are completely independent
3. **Real-time**: WebSocket provides instant updates
4. **Resilience**: State persisted, crash recovery supported
5. **Security**: Private keys encrypted, never exposed
6. **Extensibility**: Clear extension points for customization

For questions or contributions, see the main README.md.
