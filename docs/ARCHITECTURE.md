# PolyAgent Architecture & Code Decisions

**This document explains why we built the bot the way we did, in simple English.**

---

## Table of Contents

1. [Big Picture: What We're Building](#big-picture)
2. [Overall Architecture](#overall-architecture)
3. [Module-by-Module Explanation](#module-by-module)
4. [Key Design Decisions](#key-design-decisions)
5. [Why These Technologies?](#why-these-technologies)
6. [How Everything Fits Together](#how-everything-fits-together)

---

## Big Picture: What We're Building

We're building a **trading bot** for Polymarket (a prediction market website). The bot:

1. **Watches prices** in real-time
2. **Detects sudden price movements** (spikes)
3. **Makes trades** based on a simple strategy: "fade the spike"
4. **Manages risk** with stop-loss and take-profit
5. **Tracks profits and losses**

The goal is to prove that we can:
- Connect to real market data
- Detect trading opportunities
- Execute real orders safely
- Track performance accurately

---

## Overall Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                        THE BIG FLOW                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│   1. MARKET DATA  ─────►  Price comes in from WebSocket     │
│       (input)          or REST API every second              │
│                                                             │
│   2. EVENT DETECTION  ──►  Compare current price to history │
│          (find)             Did price spike?                 │
│                                                             │
│   3. STRATEGY  ──────────►  Spike Sam: Fade the spike       │
│        (decide)            Up → Sell, Down → Buy              │
│                                                             │
│   4. RISK CHECK  ─────────►  Is this trade safe?            │
│         (validate)        Position limit? Balance ready?     │
│                                                             │
│   5. ORDER EXECUTION  ────►  Place order on Polymarket      │
│          (act)           Real money (or dry run)             │
│                                                             │
│   6. POSITION TRACKING  ─►  Track entry, exit, P&L          │
│           (remember)      Save to file for recovery          │
│                                                             │
│   7. LOGGING  ────────────►  Write everything that happened │
│         (explain)        One log file per session           │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### Why This Architecture?

**Separation of Concerns**: Each part does ONE thing well
- If we need to change the strategy, we only change the strategy module
- If we need to fix order placement, we only fix the order module
- Each module can be tested independently

**Data Flow**: Information moves in ONE direction
```
Price → Detection → Strategy → Risk → Order → Tracking → Log
```

This makes the code predictable and easy to debug.

---

## Module-by-Module Explanation

### 1. Config Module (`src/config.py`)

**What it does**: Loads all settings from the `.env` file

**Why we need it**:
- All configuration in ONE place
- Type-safe (catches errors before bot runs)
- Easy to add new settings

**Key design decisions**:

| Decision | Why |
|----------|-----|
| Use `.env` file | Keeps secrets (private key) out of code |
| `@dataclass` | Clean, readable config object |
| Validation in `validate()` | Fail fast with clear error messages |
| Default values | Bot works with minimal configuration |

**Code example**:
```python
@dataclass
class Config:
    private_key: str              # Required
    signature_type: int = 0        # Default: EOA mode
    spike_threshold_pct: float = 8.0  # Default: 8% spike needed
```

---

### 2. CLOB Client Module (`src/clob_client.py`)

**What it does**: Talks to Polymarket's trading API

**Why we need it**:
- Wraps the complex `py-clob-client` library
- Provides simple functions our bot can call
- Handles both EOA and Proxy wallet types

**Key design decisions**:

| Decision | Why |
|----------|-----|
| Wrapper around `py-clob-client` | Don't reinvent the wheel - use proven library |
| `resolve_token_id()` with caching | Faster - don't fetch same data repeatedly |
| `get_polymarket_price()` | Match prices users see on website |
| Pre-trade checks | Avoid wasting gas on failed orders |

**Intelligent Pre-Trade Validation** (NEW):
```python
def place_market_order(...):
    # 1. Check balance FIRST
    has_bal, msg = has_sufficient_balance(amount)
    if not has_bal:
        return OrderResult(False)  # Don't even try

    # 2. Check orderbook health
    is_healthy, msg = check_orderbook_health(...)
    if not is_healthy:
        return OrderResult(False)  # Market illiquid

    # 3. Now try the order with smart retry
    for attempt in range(4):
        try_to_place_order()
        if balance_error:
            break  # Don't retry - won't fix itself
```

**Why pre-checks?**
- Saves gas fees (don't pay for orders that will fail)
- Faster feedback (know immediately, not after retries)
- Better user experience (clear error messages)

---

### 3. Bot Module (`src/bot.py`)

**What it does**: The main brain that orchestrates everything

**Why we need it**:
- Connects all other modules together
- Implements the trading strategy
- Manages the main loop

**Key design decisions**:

| Decision | Why |
|----------|-----|
| Single `Bot` class | Simple - one object handles everything |
| `Position` dataclass | Clean way to track open trades |
| `deque` for price history | Automatically limits memory usage |
| `decide_action()` function | Strategy is isolated - easy to swap later |

**The Position Dataclass**:
```python
@dataclass
class Position:
    side: str           # "BUY" or "SELL"
    entry_price: float  # Price we entered at
    entry_time: datetime  # When we entered
    amount_usd: float   # How much we traded

    def calculate_pnl(self, current_price):
        # Know our profit/loss at any time
```

**Why a dataclass?**
- Clean, readable code
- Built-in methods for converting to dict
- Easy to save to file for crash recovery

**Price History as Deque**:
```python
self.history: Deque[Tuple[datetime, float]] = deque(maxlen=3600)
```

**Why deque?**
- Automatically removes old prices (maxlen=3600)
- Fast append: O(1) operation
- Keeps memory usage constant

**Why store (timestamp, price) tuples?**
- Need timestamp for multi-window spike detection
- Single data structure = simpler code

---

### 4. WebSocket Client Module (`src/websocket_client.py`)

**What it does**: Real-time connection to Polymarket for instant price updates

**Why we need it**:
- REST API polling is slow (1-2 seconds latency)
- WebSocket gives ~1 second latency
- Real-time = catch spikes faster = better trades

**Key design decisions**:

| Decision | Why |
|----------|-----|
| Async + wrapper | WebSocket needs async, bot is synchronous |
| Callbacks | Simple: "call this function when trade happens" |
| Auto-reconnect | Bot keeps running if connection drops |
| `get_polymarket_price()` | Match website's pricing logic |

**Why the wrapper pattern?**
```python
class WebSocketSyncWrapper:
    """Makes async WebSocket work with sync bot code"""
    def __init__(self, on_trade_callback):
        # Runs WebSocket in background thread
        # Calls on_trade_callback(price) when trades happen
```

The bot code stays simple - it doesn't need to know about async/await.

---

### 5. Entry Point (`start_bot.py`)

**What it does**: Starts the bot and sets up logging

**Why we need it**:
- Clean entry point for running the bot
- Sets up per-session log files
- Configures logging properly

**Key design decisions**:

| Decision | Why |
|----------|-----|
| Per-session log files | Each run = new file = easier debugging |
| `get_session_log_file()` | Auto-generates unique filename |
| Configure logging first | See startup messages in log too |

**Why per-session logs?**
- Old way: All sessions in one file (hard to find)
- New way: `bot_20250110_143052.log` (timestamp = unique)
- Easy to compare different sessions
- Can share specific session when debugging

---

## Key Design Decisions

### Decision 1: Why "Spike Sam" Strategy?

**The strategy**: When price spikes UP, we SELL. When price spikes DOWN, we BUY.

**Why this strategy?**
1. **Simple**: Easy to understand and implement
2. **Proven concept**: "Fade the spike" is a known trading approach
3. **Rule-based**: No machine learning needed (yet!)
4. **Clear signals**: Spike = trade, no spike = wait
5. **Easy to test**: We can verify it works correctly

**Decision function** is isolated:
```python
def decide_action(self, spike_pct, price, stats):
    """One function that decides what to do.

    Later, we can replace this with:
    - Machine learning model
    - LLM-based decision
    - More complex strategy

    Without changing anything else!
    """
```

---

### Decision 2: Why FOK (Fill-Or-Kill) Orders?

**FOK**: Either the entire order fills immediately, or it's cancelled.

**Why FOK?**
1. **Predictable**: We know immediately if it worked
2. **No partial fills**: Get exactly what we asked for
3. **Simpler tracking**: No need to track partial orders
4. **Polymarket default**: Works well with their orderbook

**Trade-off**: Might fail in illiquid markets
- **Solution**: Pre-check orderbook health before ordering

---

### Decision 3: Why Risk Controls Before Everything?

**The flow**:
```
1. Check risk exits FIRST (if position open)
2. THEN check for new entry signals
```

**Why this order?**
1. **Protect capital**: Limit losses before adding new risk
2. **One position max**: Can't enter if already in position
3. **Take profit**: Lock in gains when target hit
4. **Time exit**: Don't get stuck forever

**Risk checks on every loop**:
```python
if open_position:
    # Always check exits first
    if time_limit_exceeded():
        exit_position()
    elif take_profit_hit():
        exit_position()
    elif stop_loss_hit():
        exit_position()

# Only then check for new entries
if no_position and cooldown_done():
    check_for_entry_signal()
```

---

### Decision 4: Why State Persistence to JSON?

**What**: Save position and P&L to `data/position.json`

**Why**:
1. **Crash recovery**: If bot crashes, it knows its state
2. **P&L tracking**: Keep cumulative profit/loss across runs
3. **Simple format**: JSON = human-readable + easy to parse
4. **No database**: Don't need external dependencies

**When do we save?**
- After every exit (position closed)
- Before risky operations

---

### Decision 5: Why Dual Mode (EOA + Proxy)?

**Two wallet types**:
- **EOA** (Externally Owned Account): Regular wallet like MetaMask
- **Proxy** (Gnosis Safe): Smart contract wallet Polymarket creates

**Why support both?**
1. **User choice**: Some users have one, some have the other
2. **Future-proof**: Polymarket might default to Proxy
3. **One setting**: `SIGNATURE_TYPE=0` or `SIGNATURE_TYPE=2`

**How it works**:
```python
if signature_type == 0:
    # Use private key directly
    client = ClobClient(key=key, signature_type=0)
else:
    # Use funder address for Proxy
    client = ClobClient(key=key, signature_type=2, funder=address)
```

Same interface, different authentication under the hood.

---

### Decision 6: Why Multi-Window Spike Detection?

**Instead of**: One time window for spike detection

**We use**: Multiple windows (10 min, 30 min, 60 min)

**Why?**
1. **Catch different spikes**: Short-term vs long-term movements
2. **More signals**: More opportunities to trade
3. **Take the max**: Use the strongest signal across all windows

**How it works**:
```python
for window in [10 min, 30 min, 60 min]:
    spike = (current_price - price_window_start) / price_window_start
    spikes.append(spike)

# Use the biggest spike found
max_spike = max(abs(s) for s in spikes)
```

---

### Decision 7: Why Settlement Delay?

**What**: Wait 2 seconds after exit before allowing new entry

**Why**:
1. **Blockchain delay**: Funds aren't immediately available after exit
2. **Prevents race condition**: Don't try to enter before exit settles
3. **Reduces "insufficient balance" errors**

**How it works**:
```python
def _enough_cooldown(self):
    # Check normal cooldown
    if time_since_last_signal < cooldown_seconds:
        return False

    # Also check settlement delay
    if time_since_exit < 2.0:
        return False  # Too soon after exit

    return True
```

---

### Decision 8: Why Clean [TAG] Log Format?

**Instead of**: Emojis like `✅ Order filled`

**We use**: `[ORDER_FILLED] Order filled`

**Why?**
1. **Professional**: Better for production systems
2. **Parseable**: Easy to filter with `grep`
3. **Universal**: Emojis can cause encoding issues
4. **Clear**: Tags stand out in logs

**Comparison**:
```
Before: ✅ Order filled
After:  [ORDER_FILLED] ID=48239104...

# Easy to filter:
grep "\[ORDER_FILLED\]" logs/bot_*.log
```

---

## Why These Technologies?

### Python

**Why Python for a trading bot?**

| Reason | Explanation |
|--------|-------------|
| **Easy to read** | Simple syntax = fewer bugs |
| **Great libraries** | `py-clob-client`, `websockets`, `dotenv` |
| **Fast enough** | ~1ms per decision, plenty fast |
| **Easy to debug** | Tracebacks show exactly what happened |
| **Widely used** | Lots of examples, help available |

### py-clob-client

**What**: Official Polymarket Python library

**Why use it instead of building our own?**
1. **Tested**: Polymarket uses it themselves
2. **Handles signing**: Complex crypto is done for us
3. **Updated**: New features are added by Polymarket
4. **Less risk**: Fewer bugs in critical code

### WebSocket

**What**: Real-time data connection

**Why not just REST polling?**
| Feature | REST Polling | WebSocket |
|---------|--------------|-----------|
| Speed | 1-2 seconds | ~0.1 seconds |
| Server load | Many requests | One connection |
| Data freshness | Stale between polls | Instant updates |
| Bandwidth | Higher (repeated requests) | Lower |

### Deque (from collections)

**What**: Double-ended queue with max length

**Why use deque for price history?**
```python
# List approach (slow, memory grows)
history = []
if len(history) > 3600:
    history.pop(0)  # O(n) operation!

# Deque approach (fast, fixed memory)
history = deque(maxlen=3600)
history.append(price)  # O(1) operation, auto-removes old
```

---

## How Everything Fits Together

### Data Flow Diagram

```
                    ┌─────────────────────┐
                    │   .env File         │
                    │  (Configuration)    │
                    └──────────┬──────────┘
                               │
                               ▼
┌──────────────┐         ┌─────────────────────┐         ┌──────────────┐
│  start_bot.py│────────▶│   Config.from_env() │         │  Bot Loop    │
│              │         └─────────────────────┘         │              │
└──────────────┘                                            │  - Forever:  │
       │                                                 │    1. Get price│
       │                                                 │    2. Check exit│
       ▼                                                 │    3. Check spike│
┌─────────────────────┐                                  │    4. Decide    │
│  Logging Setup      │◀─────────────────────────────────│    5. Execute  │
│  - Per-session file │                                  │    6. Save state│
└─────────────────────┘                                  └───────┬───────┘
       │                                                      │
       │                      ┌───────────────────────────────┘
       ▼                      ▼
┌─────────────────────┐  ┌─────────────────────┐
│   Log File Output   │  │  position.json      │
│  (bot_*.log)        │  │  (state persistence) │
└─────────────────────┘  └─────────────────────┘
```

### Module Interactions

```
Config ──────▶ Bot ──────────────▶ Client ─────▶ Polymarket API
  │              │                      │
  │              │                      └────▶ WebSocket
  │              │
  │              ▼
  │         Position ───────────────▶ Risk checks
  │
  └──────────▶ start_bot.py ────────▶ Logging
```

### Call Sequence (Trading Example)

```
1. start_bot.py
   └─▶ Config.from_env()           [Load settings]
   └─▶ Bot(config)                  [Create bot]

2. bot.run()
   └─▶ Client.resolve_token_id()   [Find market]
   └─▶ WebSocket.start()            [Connect to data feed]

3. [WebSocket receives price]
   └─▶ bot._on_websocket_trade(price)
       ├─▶ history.append(price)    [Remember price]
       ├─▶ _compute_spike_multi_window()
       │   └─▶ Compare to 10/30/60 min baselines
       ├─▶ _risk_exit(price)        [Check if should exit]
       │   └─▶ If yes: _exit()
       │       ├─▶ client.place_market_order()
       │       └─▶ _save_state()
       └─▶ decide_action()          [Should we enter?]
           └─▶ _enter()             [If yes]
               ├─▶ client.place_market_order()
               └─▶ Create Position object

4. [On every action]
   └─▶ logger.info()               [Write to log file]
```

---

## Design Principles We Followed

### 1. Simplicity Over Complexity

**Rule**: If there's a simple way and a complex way, choose simple.

**Example**:
- Complex: Machine learning spike detection
- Simple: Percentage change from baseline
- **We chose**: Simple (works well enough)

### 2. Fail Fast, Fail Clearly

**Rule**: If something is wrong, stop immediately and say why.

**Example**:
```python
def validate(self):
    if len(self.private_key) != 64:
        raise ValueError("PRIVATE_KEY must be 64 hex characters")
    # Fail at startup, not during trading
```

### 3. Don't Track What You Don't Own

**Rule**: Only track position if order succeeded.

**Old way**:
```python
self.open_position = Position(...)  # Track first
try:
    place_order()
except:
    # Now we have a fake position tracked
```

**New way**:
```python
try:
    result = place_market_order()
    if result.success:
        self.open_position = Position(...)  # Only track if real
except:
    pass  # No position opened
```

### 4. One Responsibility Per Module

**Rule**: Each file does ONE thing.

| Module | Responsibility |
|--------|---------------|
| `config.py` | Load and validate settings |
| `clob_client.py` | Talk to Polymarket API |
| `bot.py` | Run trading strategy |
| `websocket_client.py` | Real-time data |
| `start_bot.py` | Start the bot |

### 5. Testable Code

**Rule**: Every module can be tested independently.

**Example test**:
```python
def test_spike_detection():
    # Can test spike logic without real API
    history = [(now, 0.50), (now, 0.50), (now, 0.50)]
    bot = Bot(config)
    bot.history.extend(history)
    spike_pct, _ = bot._compute_spike_multi_window(0.55)
    assert spike_pct == 10.0  # 10% spike
```

---

## Why This Solution Works

### It Meets All Requirements

From the task brief:

| Requirement | How We Meet It |
|-------------|----------------|
| Market data monitoring | WebSocket + REST polling |
| Event detection | Multi-window spike detection |
| Strategy decision | `decide_action()` function |
| Risk controls | TP/SL/time limits, position limits |
| Real order execution | `place_market_order()` via Polymarket API |
| Position tracking | `Position` dataclass + JSON persistence |
| Clear logs | Per-session files with [TAG] format |

### It's Safe

1. **Pre-trade validation**: Don't waste gas on bad orders
2. **Risk limits**: Stop loss, take profit, time exit
3. **Dry run mode**: Test without real money
4. **State persistence**: Recover from crashes
5. **Only one position**: Can't over-leverage

### It's Maintainable

1. **Clean modules**: Each file has a clear purpose
2. **Type hints**: Know what data goes where
3. **Docstrings**: Every function explains itself
4. **Simple logging**: Easy to debug when something goes wrong

### It's Extensible

Want to add a new feature? Here's where it goes:

| New Feature | Where to Add It |
|-------------|----------------|
| New strategy | Replace `decide_action()` |
| New risk rule | Add to `_risk_exit()` |
| New market type | Add to `clob_client.py` |
| New API endpoint | Add method to `Client` class |
| New log format | Update `start_bot.py` |

---

## Summary: The Architecture in One Sentence

> We built a modular trading bot where each component has one responsibility, data flows in one direction, and every decision is logged clearly, making it safe, testable, and easy to understand.

---

**For questions**: See `README.md` (how to use) or `NOOB_GUIDE.md` (detailed examples)
