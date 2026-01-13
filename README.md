# PolyAgent - Polymarket Trading Bot

<div align="center">

![Version](https://img.shields.io/badge/version-2.0.0-blue.svg)
![Python](https://img.shields.io/badge/python-3.10+-green.svg)
![Next.js](https://img.shields.io/badge/Next.js-16.0-black.svg)
![License](https://img.shields.io/badge/license-MIT-purple.svg)

**A production-ready, modular trading bot for Polymarket prediction markets with a modern React dashboard and real-time WebSocket updates.**

</div>

---

##  Quick Start

```bash
# 1. Clone and setup Python environment
cd PolyAgent
pip install -r requirements.txt

# 2. Start the backend API server
python -m src.api_server

# 3. In a new terminal, start the frontend dashboard
cd frontend
npm install
npm run dev

# 4. Open http://localhost:3000 and create your first bot!
```

---

## Table of Contents

- [Features](#-features)
- [Architecture](#-architecture)
- [Installation](#-installation)
- [Web Dashboard](#-web-dashboard)
- [Configuration](#-configuration)
- [Trading Strategies](#-trading-strategies)
- [API Reference](#-api-reference)
- [Scripts & Utilities](#-scripts--utilities)
- [Testing](#-testing)
- [Operations Guide](#-operations-guide)
- [Troubleshooting](#-troubleshooting)
- [Security](#-security)

---

##  Features

### Trading Engine

| Feature | Description |
|---------|-------------|
| **Real-Time WebSocket** | Sub-second price updates via Polymarket WebSocket API (`wss://ws-subscriptions-clob.polymarket.com/ws/market`) |
| **Multi-Window Spike Detection** | Analyzes price spikes over configurable 10/30/60 minute windows |
| **Volatility Filtering** | Reduces false signals using coefficient of variation analysis |
| **Spike Sam Strategy** | Fade spikes - BUY on downward spikes, SELL on upward spikes |
| **Train of Trade** | Sequential target-based trading with automatic rebuy after sells |
| **Dual Signature Modes** | Support for EOA (SIGNATURE_TYPE=0) and Gnosis Proxy (SIGNATURE_TYPE=2) |
| **Risk Controls** | Take Profit, Stop Loss, Max Hold Time, Cooldown, Trade Size Limits |
| **P&L Tracking** | Realized P&L with win rate statistics, persisted to disk |
| **State Persistence** | Crash recovery via `data/position.json` and `data/bots/*.json` |
| **Settlement Verification** | Optional User WebSocket for real-time order status confirmation |
| **Polymarket Pricing Logic** | Uses official pricing: midpoint if spread ≤ $0.10, last trade price otherwise |

### Web Dashboard

| Feature | Description |
|---------|-------------|
| **Multi-Bot Management** | Create, start, stop, delete, and monitor multiple independent bots |
| **Real-Time Updates** | WebSocket-powered live price, position, activity, and target updates |
| **Interactive Price Chart** | Recharts-based chart with target lines, entry/exit markers, and live updates |
| **Position Tracking** | Live P&L, entry/exit prices, hold time, TP/SL visualization |
| **Activity Feed** | Filterable real-time feed of spikes, orders, fills, P&L, and system events |
| **Settings Panel** | Global settings, killswitch, slippage, liquidity requirements |
| **Market Metrics** | Spread, liquidity depth, bid/ask visualization |
| **Trading Profiles** | Pre-configured profiles: Normal, Live, Edge, Ultra-Conservative |
| **Dark/Light Themes** | Modern UI with theme toggle support |
| **Responsive Design** | Works on desktop and tablet viewports |

---

## Architecture

PolyAgent uses a **fully decoupled architecture** where the backend API server and frontend dashboard are independent.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              PolyAgent System                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─── Frontend (Next.js 16) ───────────────────────────────────────────┐   │
│  │                                                                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │   Bot       │  │   Price     │  │  Activity   │  │  Settings  │  │   │
│  │  │  Manager    │  │   Chart     │  │    Feed     │  │   Panel    │  │   │
│  │  └──────┬──────┘  └──────┬──────┘  └──────┬──────┘  └─────┬──────┘  │   │
│  │         │                │                │               │         │   │
│  │         └────────────────┴────────────────┴───────────────┘         │   │
│  │                                   │                                  │   │
│  │                    ┌──────────────┴──────────────┐                  │   │
│  │                    │    BotStateContext (React)   │                  │   │
│  │                    │    WebSocket Connection      │                  │   │
│  │                    └──────────────┬──────────────┘                  │   │
│  └───────────────────────────────────┼──────────────────────────────────┘   │
│                                      │                                      │
│                           WebSocket (ws://localhost:8000)                   │
│                           REST API (http://localhost:8000)                  │
│                                      │                                      │
│  ┌─── Backend (FastAPI + Python) ────┼──────────────────────────────────┐   │
│  │                                   │                                   │   │
│  │                    ┌──────────────┴──────────────┐                   │   │
│  │                    │     API Server (FastAPI)    │                   │   │
│  │                    │     - REST Endpoints        │                   │   │
│  │                    │     - WebSocket Broadcast   │                   │   │
│  │                    │     - CORS Handling         │                   │   │
│  │                    └──────────────┬──────────────┘                   │   │
│  │                                   │                                   │   │
│  │         ┌─────────────────────────┼─────────────────────────┐        │   │
│  │         │                         │                         │        │   │
│  │  ┌──────┴──────┐          ┌───────┴───────┐         ┌───────┴──────┐ │   │
│  │  │ BotSession  │          │  BotSession   │         │  BotSession  │ │   │
│  │  │   (Bot 1)   │          │    (Bot 2)    │         │    (Bot N)   │ │   │
│  │  │  ┌───────┐  │          │  ┌───────┐    │         │  ┌───────┐   │ │   │
│  │  │  │ Bot   │  │          │  │ Bot   │    │         │  │ Bot   │   │ │   │
│  │  │  │Engine │  │          │  │Engine │    │         │  │Engine │   │ │   │
│  │  │  └───┬───┘  │          │  └───┬───┘    │         │  └───┬───┘   │ │   │
│  │  │      │      │          │      │        │         │      │       │ │   │
│  │  │  ┌───┴───┐  │          │  ┌───┴───┐    │         │  ┌───┴───┐   │ │   │
│  │  │  │ CLOB  │  │          │  │ CLOB  │    │         │  │ CLOB  │   │ │   │
│  │  │  │Client │  │          │  │Client │    │         │  │Client │   │ │   │
│  │  │  └───────┘  │          │  └───────┘    │         │  └───────┘   │ │   │
│  │  └─────────────┘          └───────────────┘         └──────────────┘ │   │
│  │                                                                       │   │
│  └───────────────────────────────────────────────────────────────────────┘   │
│                                      │                                      │
│                           Polymarket APIs (External)                        │
│                                      │                                      │
│       ┌──────────────────────────────┼──────────────────────────────┐       │
│       │                              │                              │       │
│  ┌────┴─────┐              ┌─────────┴─────────┐            ┌───────┴─────┐ │
│  │ CLOB API │              │ WebSocket Market  │            │  Gamma API  │ │
│  │  (REST)  │              │   Price Updates   │            │  (Markets)  │ │
│  └──────────┘              └───────────────────┘            └─────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Core Components

| Component | File | Purpose |
|-----------|------|---------|
| **API Server** | `src/api_server.py` | FastAPI server exposing REST + WebSocket endpoints |
| **Bot Session** | `src/bot_session.py` | Isolated bot instance with own config, wallet, market |
| **Bot Engine** | `src/bot.py` | Core trading logic, spike detection, strategy execution |
| **CLOB Client** | `src/clob_client.py` | Polymarket py-clob-client wrapper with helpers |
| **Config** | `src/config.py` | Typed configuration with validation and trading profiles |
| **WebSocket Client** | `src/websocket_client.py` | Real-time market data from Polymarket |
| **User WebSocket** | `src/user_websocket_client.py` | Authenticated user channel for order status |
| **Crypto** | `src/crypto.py` | Fernet encryption for sensitive data (private keys) |
| **Multi-Bot Manager** | `src/multi_bot_manager.py` | Legacy multi-bot management (deprecated) |
| **Train Bot** | `src/train_bot.py` | Train-of-trade strategy implementation |

### Frontend Components

| Component | File | Purpose |
|-----------|------|---------|
| **Main Page** | `frontend/app/page.tsx` | Dashboard entry point |
| **BotStateContext** | `frontend/contexts/bot-state-context.tsx` | Global state management with WebSocket |
| **Bot Manager Panel** | `frontend/components/panels/bot-manager-panel.tsx` | Bot CRUD, configuration, and controls |
| **Price Chart** | `frontend/components/panels/price-chart.tsx` | Interactive Recharts price chart |
| **Activity Feed** | `frontend/components/panels/activity-feed.tsx` | Real-time activity log |
| **Position Card** | `frontend/components/panels/position-card.tsx` | Current position details |
| **Settings Panel** | `frontend/components/settings-panel.tsx` | Global settings management |

---

##  Installation

### Prerequisites

- **Python 3.10+** with pip
- **Node.js 18+** with npm
- **Polygon Wallet** with USDC.e and small MATIC for gas
- **Polymarket Account** (optional: generate API keys for User WebSocket)

### Backend Setup

```bash
# Navigate to project root
cd PolyAgent

# Create virtual environment (recommended)
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Linux/Mac

# Install dependencies
pip install -r requirements.txt

# Verify installation
python scripts/check_setup.py
```

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Create local environment (optional, for custom API URL)
cp .env.local.example .env.local
```

### Required Python Packages

```
py-clob-client>=0.18.0   # Polymarket SDK
fastapi>=0.115.0         # API framework
uvicorn>=0.34.0          # ASGI server
websockets>=13.0         # WebSocket client
cryptography>=44.0       # Encryption
python-dotenv>=1.0.0     # Environment variables
pytest>=8.3.0            # Testing
```

---

##  Web Dashboard

### Starting the Dashboard

```bash
# Terminal 1: Start backend API (port 8000)
python -m src.api_server

# Terminal 2: Start frontend (port 3000)
cd frontend && npm run dev

# Open http://localhost:3000
```

### Dashboard Features

#### Bot Manager Panel
- **Create Bot**: Configure wallet, market, strategy, and risk parameters
- **Trading Profiles**: Choose from Normal, Live, Edge, or Ultra-Conservative
- **Start/Stop/Pause**: Control individual bot instances
- **Delete**: Remove bot and its configuration

#### Price Chart
- **Live Price Line**: Real-time price with color-coded movements
- **Target Lines**: Buy/Sell targets for Train of Trade strategy
- **Entry Markers**: Entry price shown with horizontal line
- **Trade Markers**: Visual dots for executed trades
- **Timeframe Selection**: 1H, 4H, 1D views

#### Position Card
- **Entry Price**: Price at which position was opened
- **Current P&L**: Unrealized profit/loss in % and USD
- **Hold Time**: Time since position opened
- **TP/SL Progress**: Visual progress bars to targets

#### Activity Feed
- **Filters**: Spikes, Orders, Fills, Exits, P&L, Errors, System
- **Real-Time Updates**: Instant updates via WebSocket
- **Auto-Scroll**: Optional auto-scroll to latest activity

#### Settings Panel
- **Global Settings**: Slippage, min liquidity, tick interval
- **Killswitch**: Emergency stop all bots
- **Daily Loss Limit**: Auto-pause on reaching limit
- **Persistence**: Settings saved to `data/settings.json`

---

## Configuration

### No More .env Files!

All configuration is now managed through the **frontend UI**. When you create a bot, you configure:

#### Wallet Settings (Per Bot)
| Setting | Description |
|---------|-------------|
| `private_key` | 64-character hex string (without 0x prefix) |
| `signature_type` | 0 = EOA (direct), 2 = Gnosis Proxy |
| `funder_address` | Required only for Proxy mode |

#### Market Settings (Per Bot)
| Setting | Description |
|---------|-------------|
| `market_slug` | URL slug from polymarket.com |
| `market_token_id` | Direct token ID (alternative to slug) |
| `market_index` | Which outcome to trade (0=YES, 1=NO) |

#### Strategy Settings (Per Bot)
| Setting | Default | Description |
|---------|---------|-------------|
| `spike_threshold_pct` | 3.0 | Minimum % change to detect spike |
| `take_profit_pct` | 5.0 | Exit when profit reaches this % |
| `stop_loss_pct` | 3.0 | Exit when loss reaches this % |
| `trade_size_usd` | 5.0 | Amount per trade in USD |
| `max_hold_seconds` | 3600 | Maximum position hold time |
| `cooldown_sec` | 120 | Seconds between trades |
| `dry_run` | true | Simulate trades (no real orders) |

#### Trading Profiles

| Profile | Spike Threshold | Take Profit | Stop Loss | Trade Size |
|---------|-----------------|-------------|-----------|------------|
| **Normal** | 3.0% | 5.0% | 3.0% | $5.00 |
| **Live** | 2.5% | 4.0% | 2.5% | $10.00 |
| **Edge** | 1.5% | 2.5% | 1.5% | $20.00 |
| **Ultra-Conservative** | 5.0% | 10.0% | 5.0% | $1.00 |

### Configuration Storage

```
data/
├── bots/                    # Bot configurations (encrypted)
│   ├── bot_abc123.json
│   └── bot_def456.json
├── settings.json            # Global settings
├── .encryption_key          # Fernet encryption salt
└── position.json            # Legacy position backup
```

---

##  Trading Strategies

### Spike Sam Strategy (Default)

The bot "fades" price spikes - betting they will reverse:

1. **Detect Spike**: Price moves more than `spike_threshold_pct` over time windows
2. **Direction Analysis**: 
   - Downward spike → BUY (expect bounce back up)
   - Upward spike → SELL (expect reversion down)
3. **Risk Controls**: Apply TP/SL/time-based exits

```
Price drops 5% suddenly
  → Bot detects downward spike
  → Places BUY order
  → Sets Take Profit at +5%
  → Either hits TP or SL exits position
```

### Train of Trade Strategy

Sequential target-based trading that runs continuously:

1. **Initial State**: Set BUY target below current price
2. **Buy Trigger**: When price drops to target, BUY
3. **Sell Target**: Set target above entry (entry × (1 + take_profit_pct))
4. **Sell Trigger**: When price rises to target, SELL
5. **Repeat**: Set new BUY target, continue cycle

```python
# Cycle illustration:
# Price: $0.50 → Set BUY target at $0.485 (−3%)
# Price drops to $0.485 → BUY triggered
# Set SELL target at $0.509 (entry × 1.05)
# Price rises to $0.509 → SELL triggered (+5% profit)
# Set new BUY target at $0.494 (−3%)
# Repeat...
```

### Multi-Window Spike Detection

Analyzes price changes over multiple time windows:

```python
# Default windows: 10, 30, 60 minutes
# For each window:
#   1. Get prices from that window
#   2. Calculate % change from oldest to current
#   3. Check coefficient of variation (volatility filter)
#   4. Take maximum spike across all windows
```

---

##  API Reference

### REST Endpoints

All endpoints are served from `http://localhost:8000`.

#### Bot Management

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/bots` | List all bots with status |
| `POST` | `/api/bots` | Create new bot |
| `GET` | `/api/bots/{id}` | Get bot details |
| `PUT` | `/api/bots/{id}` | Update bot config |
| `DELETE` | `/api/bots/{id}` | Delete bot |
| `POST` | `/api/bots/{id}/start` | Start bot |
| `POST` | `/api/bots/{id}/stop` | Stop bot |
| `POST` | `/api/bots/{id}/trade` | Execute manual trade |
| `POST` | `/api/bots/{id}/close` | Close position |
| `GET` | `/api/bots/{id}/activities` | Get activity log |
| `GET` | `/api/bots/{id}/chart-data` | Get price chart data |

#### Market Data

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/markets/{slug}` | Get market info |
| `GET` | `/api/prices/{token_id}` | Get current price |
| `GET` | `/api/orderbook/{token_id}` | Get orderbook |

#### Settings

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/settings` | Get global settings |
| `POST` | `/api/settings` | Update global settings |
| `GET` | `/api/profiles` | List trading profiles |

### WebSocket Events

Connect to `ws://localhost:8000/ws` for real-time updates.

#### Incoming Events (Server → Client)

```typescript
// Price update
{ type: "price", bot_id: "xxx", price: 0.55, timestamp: "..." }

// Position update
{ type: "position", bot_id: "xxx", position: {...} }

// Spike detected
{ type: "spike", bot_id: "xxx", spike_pct: 3.5, direction: "down" }

// Activity
{ type: "activity", bot_id: "xxx", activity_type: "order", message: "..." }

// Target update (Train of Trade)
{ type: "target", bot_id: "xxx", target_price: 0.52, action: "buy" }

// Error
{ type: "error", bot_id: "xxx", error: "..." }
```

---

##  Scripts & Utilities

Located in `scripts/` directory:

| Script | Purpose |
|--------|---------|
| `check_setup.py` | Verify wallet, credentials, and configuration |
| `check_status.py` | Check current positions and balances |
| `check_orderbook.py` | Display orderbook for configured market |
| `check_spreads.py` | Analyze bid-ask spreads |
| `easy_setup.py` | Interactive setup wizard |
| `approve_usdc.py` | Approve USDC.e for EOA trading |
| `approve_usdc_gnosis.py` | Approve USDC.e for Proxy trading |
| `find_best_market.py` | Find markets with good liquidity |
| `find_tradeable_market.py` | Find active tradeable markets |
| `get_market_from_url.py` | Extract token ID from Polymarket URL |
| `compare_prices.py` | Compare prices from different sources |
| `manual_trade.py` | Execute manual test trades |
| `sell_all_positions.py` | Emergency: sell all positions |
| `test_full_cycle.py` | Test complete buy→hold→sell cycle |
| `test_live_trade.py` | Test live trading (small amounts) |
| `poly_tools.py` | Various Polymarket utility functions |

### Usage Examples

```bash
# Check your setup
python scripts/check_setup.py

# Find a liquid market to trade
python scripts/find_best_market.py

# Test a trade cycle
python scripts/test_full_cycle.py

# Emergency: close all positions
python scripts/sell_all_positions.py
```

---

## Testing

### Backend Tests (pytest)

```bash
# Run all tests
pytest tests/ -v

# Run specific test file
pytest tests/test_trading_cycle.py -v

# Run with coverage
pytest tests/ --cov=src --cov-report=html
```

#### Test Files

| Test File | Coverage |
|-----------|----------|
| `test_end_to_end.py` | Full trading flow |
| `test_trading_cycle.py` | Buy→Sell cycle logic |
| `test_midprice_and_spike.py` | Price calculation and spike detection |
| `test_websocket_callbacks.py` | WebSocket event handling |
| `test_rebuy_config.py` | Rebuy strategy configuration |
| `test_runtime_state.py` | State persistence |
| `test_market_endpoints.py` | API endpoint testing |

### Frontend Tests (Playwright)

```bash
cd frontend

# Run all E2E tests
npm run test:e2e

# Run with UI mode
npm run test:e2e:ui

# Run with visible browser
npm run test:e2e:headed
```

---

##  Operations Guide

### Starting Everything

```bash
# 1. Start API server (keep running)
python -m src.api_server

# 2. Start frontend (keep running)
cd frontend && npm run dev

# 3. Access dashboard at http://localhost:3000
```

### Creating Your First Bot

1. Click **"Create Bot"** in the Bot Manager Panel
2. Enter bot name and description
3. Paste your private key (64 hex characters, no 0x prefix)
4. Choose signature type (EOA for most users)
5. Enter market slug from Polymarket URL
6. Select a trading profile or customize settings
7. Enable **Dry Run** for testing
8. Click **Create Bot**

### Going Live

1. Verify setup with dry run trades
2. Monitor bot for expected behavior
3. Edit bot configuration
4. Set `Dry Run: false`
5. Start with small amounts ($1-5)
6. Monitor continuously initially

### Emergency Stop

- **Dashboard**: Click the `Killswitch` button in Settings
- **Individual Bot**: Click `Stop` button for that bot
- **Terminal**: `Ctrl+C` to stop the API server
- **Script**: `python scripts/sell_all_positions.py`

### Monitoring

- **Dashboard**: Real-time activity feed, price chart, P&L
- **API Logs**: Check the terminal running `api_server.py`
- **Position State**: Check `data/bots/*.json`

---

##  Troubleshooting

### Common Issues

| Issue | Solution |
|-------|----------|
| **"No balance/allowance"** | Approve USDC.e: `python scripts/approve_usdc.py` |
| **"Token not found"** | Check market slug or use token ID directly |
| **"Order failed"** | Check spread, liquidity; market might be thin |
| **"WebSocket disconnected"** | Normal reconnection happens automatically |
| **"Encryption error"** | Delete `data/.encryption_key` and recreate bots |
| **"CORS error"** | Ensure API runs on port 8000, frontend on 3000 |
| **"No price available"** | Check if market is active and has trades |

### Checking Setup

```bash
# Full diagnostic
python scripts/check_setup.py

# Check wallet balance
python scripts/check_status.py

# Test market connection
python scripts/check_orderbook.py
```

### Logs

The API server logs to stdout. Key log patterns:

```
INFO:     [BOT_abc123] Price: 0.55 | Target: SELL @ 0.58
INFO:     [TRADE] Executing BUY $5.00
INFO:     [ORDER] Filled: BUY $5.00 @ 0.52
WARNING:  [RISK] Stop loss triggered at -3.2%
```

---

##  Security

### Private Key Protection

- Private keys are **encrypted** using Fernet symmetric encryption
- Encryption key derived from machine-specific data (user + home path)
- Salt stored in `data/.encryption_key`
- Only works on the machine where bot was created

### Best Practices

1. **Use a dedicated trading wallet** - Never use your main wallet
2. **Fund with small amounts** - Only what you're willing to lose
3. **Start with dry run** - Test thoroughly before live trading
4. **Secure data/ folder** - Contains encrypted private keys
5. **Don't commit .env or data/** - Already in .gitignore

### File Permissions

```bash
# Restrict key file (Linux/Mac)
chmod 600 data/.encryption_key

# Restrict bot configs
chmod 600 data/bots/*
```

---

##  Project Structure

```
PolyAgent/
├── src/                       # Python backend
│   ├── api_server.py          # FastAPI server
│   ├── bot.py                 # Bot engine
│   ├── bot_session.py         # Isolated bot sessions
│   ├── clob_client.py         # Polymarket client
│   ├── config.py              # Configuration
│   ├── crypto.py              # Encryption utilities
│   ├── multi_bot_manager.py   # Legacy multi-bot
│   ├── train_bot.py           # Train strategy
│   ├── websocket_client.py    # Market WebSocket
│   └── user_websocket_client.py # User channel
│
├── frontend/                  # Next.js frontend
│   ├── app/                   # Next.js app router
│   ├── components/            # React components
│   │   ├── panels/            # Dashboard panels
│   │   └── ui/                # UI primitives (shadcn)
│   ├── contexts/              # React contexts
│   └── hooks/                 # Custom hooks
│
├── scripts/                   # CLI utilities
├── tests/                     # Python tests
├── data/                      # Runtime data
│   ├── bots/                  # Bot configs
│   └── settings.json          # Global settings
│
├── docs/                      # Documentation
│   ├── ARCHITECTURE.md        # System architecture
│   └── NOOB_GUIDE.md          # Beginner's guide
│
|
├── requirements.txt           # Python dependencies
├── conftest.py                # Pytest configuration
└── README.md                  # This file
```

---

## Additional Documentation

- **[Architecture Guide](docs/ARCHITECTURE.md)** - Deep dive into system design
- **[Beginner's Guide](docs/NOOB_GUIDE.md)** - Step-by-step for new users

---

##  Acknowledgments

- [Polymarket](https://polymarket.com) - The prediction market platform
- [py-clob-client](https://github.com/Polymarket/py-clob-client) - Official Python SDK
- [FastAPI](https://fastapi.tiangolo.com/) - Modern API framework
- [Next.js](https://nextjs.org/) - React framework
- [shadcn/ui](https://ui.shadcn.com/) - UI component library
- [Recharts](https://recharts.org/) - Charting library

---

##  Disclaimer

**Trading on prediction markets involves significant risk. You can lose your entire investment. This software is provided "as is" without warranty. The authors are not responsible for any financial losses incurred. Only trade with funds you can afford to lose.**

---

<div align="center">

**Happy Trading!**

*Made with ❤️ for the Polymarket community*

</div>
