# PolyAgent - Polymarket Trading Bot

A production-ready, modular trading bot for Polymarket prediction markets implementing the **Spike Sam** fade strategy with **real-time WebSocket spike detection**, multi-window analysis, dual signature modes (EOA/Proxy), comprehensive risk controls, and P&L tracking.

---

## Table of Contents

1. [Features](#features)
2. [Quick Start](#quick-start)
3. [Configuration](#configuration)
4. [Project Structure](#project-structure)
5. [How It Works](#how-it-works)
6. [Operations Guide](#operations-guide)
7. [Troubleshooting](#troubleshooting)

---

## Features

| Feature | Description |
|---------|-------------|
| **Real-Time WebSocket** | ~1 second spike detection via Polymarket WebSocket API |
| **Multi-Window Detection** | Analyzes spikes over 10/30/60 minute windows |
| **Volatility Filtering** | Reduces false signals using coefficient of variation |
| **Spike Sam Strategy** | Fade spikes - BUY on downward spikes, SELL on upward spikes |
| **Intelligent Pre-Trade Validation** | Balance checks, orderbook health, smart pricing before orders |
| **Reduced Order Failures** | Settlement delay, smart retry logic, early exit on permanent errors |
| **Dual Signature Modes** | Support for EOA (SIGNATURE_TYPE=0) and Gnosis Proxy (SIGNATURE_TYPE=2) |
| **Risk Controls** | Take Profit, Stop Loss, Max Hold Time, Cooldown, Trade Size Limits |
| **Real Trading** | Live order execution on Polymarket CLOB with full order tracking |
| **P&L Tracking** | Realized P&L with win rate statistics, persisted to disk |
| **State Persistence** | Crash recovery via `data/position.json` |
| **Per-Session Logs** | Unique log file for each bot run (e.g., `bot_20250110_143052.log`) |
| **Clean Log Format** | Professional [TAG] format (no emojis) for easy parsing |
| **Hybrid Pricing** | WebSocket primary + REST fallback for reliability |

---

## Quick Start

### 1. Install Dependencies

```bash
python -m venv venv
# Windows: venv\Scripts\activate
# macOS/Linux: source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure `.env`

```bash
cp .env.example .env
# Edit .env with your values
```

**Minimum required settings:**
```env
PRIVATE_KEY=<64-hex-without-0x>
SIGNATURE_TYPE=0   # 0=EOA, 2=Proxy
MARKET_SLUG=wta-mcnally-juvan-2026-01-09
MARKET_INDEX=0     # Which market within the event
DRY_RUN=true       # Start with simulation!
```

### 3. Run the Bot

```bash
python start_bot.py
```

**Example Output:**
```
INFO - Starting Polymarket Spike Sam Bot
INFO - Session log: logs/bot_20250110_143052.log
INFO - WebSocket ENABLED - Real-time spike detection (~1 second)
INFO - WebSocket connected!
INFO - Subscribed to market for token 65825053959363891562...
INFO - Initial price: 0.8150
INFO - [TRADE] 0.8400 BUY size=14
INFO - [SPIKE_#1] +4.35% -> SELL $1.00 (spike_up_4.35%_window_600s, price=0.8400)
INFO - [BALANCE_OK] $10.50 available
INFO - [ORDERBOOK_HEALTHY] Bid liquidity: $15.20, Spread: 0.8%
INFO - [ENTRY] SELL $1.00 at 0.8400
INFO - [POSITION_OPENED] SELL $1.00 at 0.8400
INFO - [EXIT_TAKE_PROFIT] +4.17% >= 0.5%: BUY $1.00 at 0.8050
INFO - [ORDER_FILLED] ID=48239104719283...
INFO - [POSITION_CLOSED] P&L: $+0.04 (+4.17%) | Hold: 0.3min
INFO - Total P&L: $+0.17 | Win Rate: 3/8
```

---

## Configuration

### Complete `.env` Reference

```env
# ============================================================
# WALLET & AUTHENTICATION
# ============================================================
PRIVATE_KEY=your_64_hex_private_key_without_0x
SIGNATURE_TYPE=0                  # 0=EOA, 2=Gnosis Safe Proxy
FUNDER_ADDRESS=0x...              # Required only if SIGNATURE_TYPE=2

# ============================================================
# MARKET SELECTION
# ============================================================
MARKET_SLUG=event-slug-from-url   # e.g., wta-mcnally-juvan-2026-01-09
MARKET_TOKEN_ID=                  # Optional: direct token ID
MARKET_INDEX=0                    # Which market within event (0=first)

# ============================================================
# WEBSOCKET & REAL-TIME DETECTION (NEW v2)
# ============================================================
WSS_ENABLED=true                  # Enable real-time WebSocket
WSS_RECONNECT_DELAY=1.0           # Seconds between reconnection attempts
WSS_MAX_RECONNECT_DELAY=60.0      # Max reconnection delay

# ============================================================
# MULTI-WINDOW SPIKE DETECTION (NEW v2)
# ============================================================
SPIKE_THRESHOLD_PCT=8.0           # % change to trigger trade
SPIKE_WINDOWS_MINUTES=10,30,60    # Time windows to check (comma-separated)
USE_VOLATILITY_FILTER=true        # Filter high-volatility periods
MAX_VOLATILITY_CV=10.0            # Max coefficient of variation
MIN_SPIKE_STRENGTH=5.0            # Minimum spike strength to trade

# ============================================================
# TRADING PARAMETERS
# ============================================================
DEFAULT_TRADE_SIZE_USD=2.0        # Amount per trade
MIN_TRADE_USD=1.0                 # Polymarket minimum
MAX_TRADE_USD=100.0               # Safety maximum
COOLDOWN_SECONDS=120              # Wait between trades

# ============================================================
# RISK MANAGEMENT
# ============================================================
TAKE_PROFIT_PCT=3.0               # Exit at +3% profit
STOP_LOSS_PCT=2.5                 # Exit at -2.5% loss
MAX_HOLD_SECONDS=3600             # Force exit after 60 minutes
MAX_CONCURRENT_TRADES=1           # Max positions per market

# ============================================================
# PRICE SETTINGS
# ============================================================
PRICE_HISTORY_SIZE=3600           # Max price history samples
PRICE_POLL_INTERVAL_SEC=1.0       # REST polling interval
USE_GAMMA_PRIMARY=false           # Use Gamma API as primary price

# ============================================================
# ORDERBOOK GUARDS
# ============================================================
MIN_BID_LIQUIDITY=5.0              # Minimum bid liquidity
MIN_ASK_LIQUIDITY=5.0              # Minimum ask liquidity
MAX_SPREAD_PCT=1.0                # Maximum spread percentage

# ============================================================
# LOGGING & SAFETY
# ============================================================
LOG_LEVEL=INFO                    # DEBUG, INFO, WARNING, ERROR
LOG_FORMAT=PLAIN                  # PLAIN or JSON
DRY_RUN=true                      # Simulate trades (NO real money)
```

### Finding Markets

1. Browse https://polymarket.com/markets
2. Find an event (e.g., sports match)
3. Copy the slug from the URL
4. Determine the market index:
   - Index 0 = First market (often handicap)
   - Index 10-11 = Main moneyline/series winner

---

## Project Structure

```
PolyAgent/
├── start_bot.py               # Entry point - starts the trading bot
├── requirements.txt            # Python dependencies
├── .env                        # User configuration (create from .env.example)
├── .env.example                # Configuration template
│
├── src/                        # Core source code
│   ├── __init__.py
│   ├── config.py              # Configuration loading & validation
│   ├── clob_client.py         # Polymarket API wrapper (EOA/Proxy)
│   ├── bot.py                 # Main bot loop & Spike Sam strategy
│   ├── risk_manager.py        # Risk management system
│   └── websocket_client.py    # Real-time WebSocket client
│
├── scripts/                    # Operational scripts
│   ├── manual_trade.py        # Execute one-off buy/sell orders
│   ├── check_setup.py         # Verify configuration
│   ├── check_status.py        # Check current positions
│   ├── check_orderbook.py     # Inspect orderbook state
│   ├── compare_prices.py      # Compare Gamma vs CLOB prices
│   ├── pre_flight_check.py    # Quick pre-flight validation
│   ├── sell_all_positions.py  # Emergency exit
│   └── test_full_cycle.py     # End-to-end trade cycle test
│
├── tests/                      # Test suite
│   ├── test_end_to_end.py     # Integration tests
│   └── test_midprice_and_spike.py # Unit tests
│
├── data/                       # Runtime data (created at runtime)
│   └── position.json          # Persistent position state
│
└── logs/                       # Log files (created at runtime)
    └── bot_*.log              # Per-session logs (e.g., bot_20250110_143052.log)
```

---

## How It Works

### Architecture Flow

```
┌─────────────────────────────────────────────────────────────────────┐
│                         PolyAgent Architecture                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐         │
│  │   WebSocket  │    │   REST API   │    │   Config     │         │
│  │   (~1 sec)   │    │   (backup)   │    │   (.env)     │         │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘         │
│         │                    │                    │                 │
│         └────────┬───────────┘                    │                 │
│                  ▼                                │                 │
│         ┌────────────────┐                       │                 │
│         │  Price History │                       │                 │
│         │  (deque)       │                       │                 │
│         └────────┬───────┘                       │                 │
│                  │                                │                 │
│                  ▼                                ▼                 │
│         ┌─────────────────────────────────────────────────┐        │
│         │              Spike Detection Engine             │        │
│         │  ┌─────────────────────────────────────────┐    │        │
│         │  │ Multi-Window Analysis (10/30/60 min)    │    │        │
│         │  │ - Compare current vs window baseline    │    │        │
│         │  │ - Find max spike across all windows     │    │        │
│         │  │ - Apply volatility filter (CV check)    │    │        │
│         │  └─────────────────────────────────────────┘    │        │
│         └────────────────────────┬────────────────────────┘        │
│                  │                │                                 │
│                  ▼                ▼                                 │
│         ┌──────────────┐  ┌──────────────┐                          │
│         │   Risk       │  │  Spike Sam   │                          │
│         │   Manager    │  │  Strategy    │                          │
│         └──────┬───────┘  └──────┬───────┘                          │
│                │                 │                                   │
│                └────────┬────────┘                                   │
│                         ▼                                            │
│              ┌──────────────────┐                                    │
│              │  Order Execution │                                    │
│              │  (Polymarket     │                                    │
│              │   CLOB API)      │                                    │
│              └─────────┬────────┘                                    │
│                        │                                             │
│                        ▼                                             │
│              ┌──────────────────┐                                    │
│              │  Position & P&L  │                                    │
│              │  Tracking        │                                    │
│              └──────────────────┘                                    │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Main Loop

```
┌─────────────────────────────────────────────────────────────────┐
│  1. FETCH PRICE                                                  │
│     → WebSocket: Real-time trade events (~1 sec latency)         │
│     → REST: Fallback every 30 seconds                           │
├─────────────────────────────────────────────────────────────────┤
│  2. UPDATE HISTORY                                              │
│     → Append (timestamp, price) to deque                        │
├─────────────────────────────────────────────────────────────────┤
│  3. CHECK RISK EXITS (if position open)                          │
│     → Take Profit hit? → Exit                                   │
│     → Stop Loss hit? → Exit                                     │
│     → Max hold time? → Exit                                     │
├─────────────────────────────────────────────────────────────────┤
│  4. DETECT SPIKE (Multi-Window)                                  │
│     → For each window (10/30/60 min):                            │
│       - Get baseline price from window start                    │
│       - Calculate: (current - baseline) / baseline × 100         │
│     → Return maximum spike across all windows                    │
│     → Apply volatility filter (CV check)                         │
├─────────────────────────────────────────────────────────────────┤
│  5. STRATEGY DECISION                                            │
│     → Spike Sam (fade spikes):                                  │
│       • spike ≥ +threshold → SELL                               │
│       • spike ≤ -threshold → BUY                                │
│       • else → HOLD                                             │
├─────────────────────────────────────────────────────────────────┤
│  6. PRE-TRADE VALIDATION (NEW)                                  │
│     → Balance check: sufficient USDC.e available?               │
│     → Orderbook health: liquidity and spread acceptable?        │
│     → Smart pricing: calculate execution price with slippage    │
│     → Skip order if validation fails (prevents wasted fees)     │
├─────────────────────────────────────────────────────────────────┤
│  7. EXECUTE TRADE                                               │
│     → Risk check: size, position limit, cooldown                │
│     → Place market order (FOK) via CLOB API                     │
│     → Smart retry: exponential backoff, early exit on errors    │
│     → Track position state ONLY if order succeeds               │
│     → Add settlement delay after exits (prevent race conditions)│
├─────────────────────────────────────────────────────────────────┤
│  8. UPDATE P&L                                                   │
│     → Calculate realized P&L on exit                            │
│     → Save state to position.json                               │
├─────────────────────────────────────────────────────────────────┤
│  9. SLEEP & REPEAT                                               │
│     → Sleep 1 second (configurable)                             │
└─────────────────────────────────────────────────────────────────┘
```

### The Spike Sam Strategy

```
spike_pct = (current_price - baseline_price) / baseline_price × 100

if spike_pct ≥ +threshold:
    → SELL (fade the upward spike - market overreacted)
elif spike_pct ≤ -threshold:
    → BUY (fade the downward spike - market oversold)
else:
    → HOLD (no significant spike)
```

**Example:**
- Price was 0.80, now 0.84
- Spike = (0.84 - 0.80) / 0.80 × 100 = +5%
- If threshold = 3%, trigger SELL (fade the pump)

---

## Operations Guide

### Testing Process

1. **Dry Run First**
   ```env
   DRY_RUN=true
   ```

2. **Verify Setup**
   ```bash
   python scripts/check_setup.py
   ```

3. **Manual Trade Test**
   ```bash
   python scripts/manual_trade.py --buy --size 1.05
   ```

4. **Run Bot (Dry Run)**
   ```bash
   python start_bot.py
   ```

5. **Go Live**
   ```env
   DRY_RUN=false
   ```

### Monitoring Commands

| Command | Purpose |
|---------|---------|
| `python scripts/check_setup.py` | Verify configuration |
| `python scripts/check_status.py` | Show current positions |
| `python scripts/check_orderbook.py` | Inspect orderbook |
| `python scripts/manual_trade.py --buy --size 1.05` | Manual buy |
| `python scripts/manual_trade.py --sell --size 1.05` | Manual sell |
| `python scripts/sell_all_positions.py` | Emergency exit |

### Understanding Log Output

The bot uses a clean [TAG] format for professional, parseable logs (no emojis).

| Log Pattern | Meaning |
|-------------|---------|
| `[TRADE] 0.8400 BUY` | Real-time trade via WebSocket |
| `[SPIKE_#N] +4.35%` | Spike detected |
| `[ENTRY] SELL` | Position opened |
| `[POSITION_OPENED]` | Position successfully opened |
| `[POSITION_CLOSED]` | Position exited |
| `[EXIT_TAKE_PROFIT]` | Profitable exit |
| `[EXIT_STOP_LOSS]` | Loss cut |
| `[EXIT_TIME]` | Max hold reached |
| `[ORDER_FILLED]` | Order successfully executed |
| `[PRE_CHECK_FAILED]` | Pre-trade validation failed (order skipped) |
| `[BALANCE_OK]` | Sufficient balance confirmed |
| `[ORDERBOOK_HEALTHY]` | Orderbook has enough liquidity |
| `Total P&L: $+0.26` | Cumulative profit |
| `Win Rate: 6/11` | Success rate |

### Pre-Check Failures

When you see `[PRE_CHECK_FAILED]`, the bot skipped an order attempt because:

| Error Message | Cause | Solution |
|---------------|-------|----------|
| `Insufficient balance: $X < $Y` | Not enough USDC.e | Add more funds or reduce trade size |
| `Insufficient allowance: $X < $Y` | Contract not approved | Trade once on Polymarket to approve |
| `Low bid liquidity: $X` | Not enough buy orders for SELL | Choose more liquid market |
| `Low ask liquidity: $X` | Not enough sell orders for BUY | Choose more liquid market |
| `Wide spread: X% > Y%` | Bid/ask gap too large | Market illiquid, wait or switch |

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| `PRIVATE_KEY format error` | Must be 64 hex chars, no `0x` prefix |
| `FUNDER_ADDRESS required` | Set it when `SIGNATURE_TYPE=2` |
| `WebSocket error: Event loop is closed` | Normal shutdown message |
| No trades happening | Lower `SPIKE_THRESHOLD_PCT`, wait for history to fill |
| Order not filling | Market illiquid - check orderbook, try smaller size |
| Invalid signature | Check `FUNDER_ADDRESS` matches your proxy wallet |
| Price stuck at 0.01/0.99 | Market resolved or illiquid |
| `No orderbook exists for requested token id` | Market has no CLOB activity - try different market |
| `[PRE_CHECK_FAILED] Insufficient balance` | Add USDC.e to wallet or reduce `DEFAULT_TRADE_SIZE_USD` |
| `[PRE_CHECK_FAILED] Low bid/ask liquidity` | Choose a more liquid market with active trading |
| `[PRE_CHECK_FAILED] Wide spread` | Spread too large - wait or switch to different market |
| `[ENTRY_SKIPPED]` | Order validation failed - check pre-check logs for reason |

### Emergency Exit

```bash
python scripts/sell_all_positions.py
```

---

## Safety Tips

1. **ALWAYS start with `DRY_RUN=true`**
2. **Use small trade sizes** ($1-5 for testing)
3. **Use a dedicated trading wallet** - never your main wallet
4. **Monitor logs closely** when first running
5. **Understand the Spike Sam strategy** - it fades spikes, may lose in trending markets
6. **Keep USDC.e for trading** + **MATIC for gas**
7. **Choose liquid markets** - illiquid markets have wide spreads

---

## Live Trading Test Results

**Market:** WTA Tennis - McNally vs Juvan (2026-01-09)
**Duration:** 3 minutes
**Mode:** Dry Run

| Spike | Entry | Exit | P&L |
|-------|-------|------|-----|
| #1: +4.29% | SELL 0.8400 | BUY 0.8300 | +1.19% |
| #2: +4.29% | SELL 0.8500 | BUY 0.8150 | +4.12% |
| #3: +9.20% | SELL 0.8900 | BUY 0.8550 | +3.93% |

**Total: +$0.26 | Win Rate: 6/11 (54.5%)**

---

## Risk Disclaimer

Trading involves risk. You can lose money. This software is provided as-is with no warranties. Always use `DRY_RUN=true` first and trade responsibly.

---

