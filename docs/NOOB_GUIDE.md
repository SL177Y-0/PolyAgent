# PolyAgent - Complete Beginner's Guide

**Everything You Need to Know to Set Up and Run Your Polymarket Trading Bot**

**Last Updated:** January 2026 (v2.1 - Added easy setup wizard and CLI tools)

---

## NEW: Quick Start for Complete Beginners

If you want to get started as fast as possible, use our new easy tools:

```bash
# Step 1: Run the setup wizard (interactive, guides you through everything)
python scripts/easy_setup.py

# Step 2: Check your configuration
python poly.py status

# Step 3: Start the bot
python poly.py start
```

That's it! The setup wizard will guide you through:
- Private key configuration
- Market selection (with search)
- Trade size and risk settings
- All in a friendly Q&A format

---

## Part 1: Understanding What You're Getting Into

### What This Bot Does (In Simple Terms)

This is an automated trading bot for Polymarket (a prediction market where people bet on real-world events like sports, politics, etc.).

**The Strategy: "Fade the Spike"**

The bot watches prices constantly. When it sees a sudden price movement (a "spike"), it bets the opposite way:

```
Price suddenly shoots UP → Bot SELLS (betting it will come back down)
Price suddenly drops DOWN → Bot BUYS (betting it will bounce back up)
```

**Why this works:** When people get excited or scared, they often overreact. The bot bets that the price will return to "normal."

**Example:**
- Tennis match is happening
- Player A scores a point
- Everyone rushes to bet on Player A
- Price for Player A jumps from 0.50 to 0.55 (10% spike!)
- Bot thinks: "That's an overreaction"
- Bot SELLS Player A at 0.55
- A minute later, price settles back to 0.52
- Bot buys back at 0.52 and makes a profit

### The Risks You Must Understand

⚠️ **READ THIS BEFORE TRADING WITH REAL MONEY**

| Risk | What It Means |
|------|---------------|
| **You can lose money** | This strategy doesn't always win |
| **Trending markets** | If price keeps going in one direction, bot loses |
| **Illiquid markets** | Hard to enter/exit positions in quiet markets |
| **Technical issues** | Internet, API, or computer problems can cause issues |
| **Market changes** | Polymarket could change their rules |

**Rule of thumb:** Only trade with money you can afford to lose 100%.

---

## Part 2: Getting Ready (Setup Checklist)

### What You Need Before Starting

- [ ] **Computer** - Windows, Mac, or Linux computer
- [ ] **Python** - Version 3.10 or higher installed
- [ ] **Polymarket Account** - Created at polymarket.com
- [ ] **Wallet** - MetaMask or Polymarket's built-in wallet
- [ ] **USDC.e** - Trading money (start with $5-10 minimum)
- [ ] **MATIC** - For gas fees (about $1-2 worth)
- [ ] **Basic computer skills** - Can open terminal, edit text files

---

## Part 3: Step-by-Step Setup Guide

### Step 3.1: Install Python

**Windows:**
```
1. Go to https://python.org/downloads
2. Download Python 3.10 or higher
3. Run the installer
4. ⭐ IMPORTANT: Check "Add Python to PATH"
5. Click "Install Now"
```

**Mac:**
```bash
# Install Homebrew first (if you don't have it)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Then install Python
brew install python@3.11
```

**Linux (Ubuntu/Debian):**
```bash
sudo apt update
sudo apt install python3 python3-pip python3-venv
```

**Verify Python is installed:**
```bash
python --version
# Should say: Python 3.10.x or higher
```

### Step 3.2: Download the Bot

1. Download the PolyAgent folder
2. Extract it if it's zipped
3. Move it to a permanent location (Desktop is fine)
4. Open a terminal in that folder

**Windows - How to open terminal:**
- Hold `Shift` + Right-click in the folder
- Click "Open PowerShell window here" or "Open in Terminal"

**Mac - How to open terminal:**
- Right-click in the folder
- Hold `Option` key
- Click "Open in Terminal"

### Step 3.3: Install Dependencies

In the terminal, type:

```bash
pip install -r requirements.txt
```

**What this does:** Installs all the Python packages the bot needs.

**If this fails:**
```bash
# Try this instead:
python -m pip install -r requirements.txt
```

### Step 3.4: Get Your Private Key

⚠️ **CRITICAL SECURITY WARNING**

Your private key is like your password. Anyone who has it can steal your money.

**DO NOT:**
- ❌ Share it with anyone
- ❌ Post it online
- ❌ Put it in screenshots
- ❌ Email it to yourself

**DO:**
- ✅ Keep it safe and offline
- ✅ Write it on paper and store it securely
- ✅ Only put it in the .env file

**How to find your private key from MetaMask:**

```
1. Open MetaMask extension
2. Click the three dots (...)
3. Select "Account Details"
4. Click "Export Private Key"
5. Enter your MetaMask password
6. Copy the private key (64 characters, letters a-f and numbers 0-9)
7. REMOVE "0x" from the start if it's there
```

**How to find your private key from Polymarket:**

```
1. Go to polymarket.com
2. Connect your wallet
3. Click your address (top right)
4. Go to wallet settings
5. Look for "Export Private Key" option
```

### Step 3.5: Know Your Signature Type

**SIGNATURE_TYPE = 0** (Normal/EOA)
- You have a regular wallet like MetaMask
- You created your own wallet
- Use this if you're not sure

**SIGNATURE_TYPE = 2** (Gnosis Safe Proxy)
- Polymarket created a special wallet for you
- You used Polymarket's "Create Wallet" feature
- You need to set FUNDER_ADDRESS

**How to check which one you have:**

1. Go to Polymarket and connect your wallet
2. Look at your wallet address
3. If it starts with `0x` and you recognize it → SIGNATURE_TYPE=0
4. If you're not sure, try SIGNATURE_TYPE=0 first

**If SIGNATURE_TYPE=2, you need FUNDER_ADDRESS:**

```
1. In Polymarket, go to "Profile"
2. Look for "Deposit Address" or your wallet info
3. Copy that address as FUNDER_ADDRESS
```

### Step 3.6: Create Your Configuration File

```bash
# Copy the template
cp .env.example .env

# Open it for editing
# Windows:
notepad .env

# Mac:
nano .env
```

### Step 3.7: Fill In Your Configuration

**Minimum you MUST fill in:**

```env
# ============================================================
# YOUR WALLET (REQUIRED)
# ============================================================
# Paste your 64-character private key here, no 0x
PRIVATE_KEY=abcdef1234567890abcdef1234567890abcdef1234567890abcdef1234567890

# Usually 0, unless you have a Gnosis Safe wallet
SIGNATURE_TYPE=0

# Leave empty unless SIGNATURE_TYPE=2
FUNDER_ADDRESS=

# ============================================================
# MARKET TO TRADE (REQUIRED)
# ============================================================
# See Part 4 for how to find this
MARKET_SLUG=some-event-name-from-url
MARKET_INDEX=0

# ============================================================
# SAFETY FIRST (REQUIRED)
# ============================================================
# Start with true for testing!
DRY_RUN=true
```

---

## Part 4: Finding and Choosing Markets

### Step 4.1: Understanding Polymarket Markets

Polymarket has "events" and "markets":

```
EVENT: "Will Bitcoin reach $100,000 by end of 2025?"
  → Market 0: "Yes" (token ID: ...)
  → Market 1: "No" (token ID: ...)
```

For sports:
```
EVENT: "Djokovic vs Nadal - Australian Open"
  → Market 0: Handicap betting
  → Market 1: Total games
  → Market 11: Match winner (this is what you usually want!)
```

### Step 4.2: How to Find Market Slug

**Method 1: From URL (Easiest)**

```
1. Go to https://polymarket.com
2. Browse or search for an event
3. Click on the event
4. Look at the URL in your browser

Example URL:
https://polymarket.com/event/wta-mcnally-juvan-2026-01-09
                              ↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑↑
                              This is the slug

Copy everything after /event/ and paste it as MARKET_SLUG
```

**Method 2: Use the Market URL Extractor (NEW)**

```bash
# Get full market info from any Polymarket URL
python scripts/get_market_from_url.py https://polymarket.com/event/some-market

# Or just use the slug directly
python poly.py market some-market-slug
```

This shows you:
- Market title and description
- Token IDs for YES/NO outcomes
- Current prices
- Orderbook status (active or not)
- Ready-to-copy .env settings

**Method 3: Use the Bot's Search Tool**

```bash
# Find tradeable markets with good orderbooks
python scripts/find_tradeable_market.py

# Or use the CLI
python poly.py find
```

### Step 4.3: Choosing the Right MARKET_INDEX

The MARKET_INDEX selects which specific market within an event.

**Common Index Values:**

| Index | Usually Means | When to Use |
|-------|---------------|-------------|
| 0 | First market found (often handicap) | For testing |
| 10 or 11 | Main winner market | **Use this for sports!** |
| Varies | Depends on event | Check with `check-market` |

**How to find the right index:**

```bash
# Check what markets exist in an event
python scripts/poly_tools.py check-market wta-mcnally-juvan-2026-01-09
```

This shows all markets with their index numbers and prices.

### Step 4.4: What Makes a Good Market?

**Good markets for this bot:**

✅ **Active trading** - Lots of people buying/selling
✅ **Live events** - Sports matches happening now
✅ **Volatile** - Price moves around (creates spikes)
✅ **Liquid** - Easy to enter and exit positions

**Bad markets for this bot:**

❌ **Resolved markets** - Event already finished
❌ **Dead markets** - No trading activity
❌ **Stable markets** - Price never moves
❌ **Very illiquid** - Hard to trade (wide spreads)

**How to check if a market is good:**

```bash
# Scan the market's liquidity
python scripts/poly_tools.py scan-liquidity wta-mcnally-juvan-2026-01-09
```

Look for:
- Bids and asks (shows people are trading)
- Narrow spread (bid and ask prices close together)
- Reasonable liquidity (not $0)

### Step 4.5: Best Market Types for This Strategy

**Ranking from best to worst:**

1. **Live Sports** (Tennis, Basketball, MMA) - ⭐⭐⭐⭐⭐
   - Prices move constantly during the match
   - Lots of emotional overreactions
   - High liquidity

2. **Esports** (DOTA, LoL, CS:GO) - ⭐⭐⭐⭐
   - Very volatile
   - Good liquidity during major tournaments

3. **Political Events** (Elections, debates) - ⭐⭐⭐
   - Spikes during news/events
   - Can be less predictable

4. **Long-term Markets** (Will X happen by date) - ⭐⭐
   - Less volatile
   - Fewer trading opportunities

---

## Part 5: Understanding Every Configuration Option

### Complete Settings Guide

```env
# ============================================================
# WALLET SETTINGS
# ============================================================

PRIVATE_KEY=your_64_char_key_here
# What: Your wallet's secret key
# How: Get from MetaMask (see Part 3)
# Risk: HIGH - Keep this secret!
# Default: (none, required)

SIGNATURE_TYPE=0
# What: Type of wallet you have
# Options: 0 = Normal wallet (MetaMask), 2 = Polymarket proxy
# Default: 0
# When to change: Only if Polymarket created a special wallet for you

FUNDER_ADDRESS=0x...
# What: Your Polymarket deposit address (for SIGNATURE_TYPE=2)
# When to fill: Only if SIGNATURE_TYPE=2
# Default: empty

# ============================================================
# MARKET SELECTION
# ============================================================

MARKET_SLUG=event-name-here
# What: Which event to trade
# How: Copy from Polymarket URL (see Part 4)
# Example: wta-mcnally-juvan-2026-01-09
# Default: (none, required)

MARKET_TOKEN_ID=
# What: Direct token ID (alternative to slug)
# When to use: If you know the exact token ID
# Default: empty (use MARKET_SLUG instead)

MARKET_INDEX=0
# What: Which market within the event
# Options: 0, 10, 11 (varies by event)
# For sports: Usually 11 (main winner market)
# Default: 0

# ============================================================
# WEBSOCKET SETTINGS (Real-time data)
# ============================================================

WSS_ENABLED=true
# What: Use real-time price updates (faster!)
# Options: true = enabled, false = disabled (slower)
# Default: true
# Recommendation: Keep true for better performance

WSS_RECONNECT_DELAY=1.0
# What: How long to wait before reconnecting (seconds)
# Default: 1.0
# When to change: If you get frequent disconnections, increase to 2.0

# ============================================================
# SPIKE DETECTION SETTINGS
# ============================================================

SPIKE_THRESHOLD_PCT=0.3
# What: How much price must move to trigger a trade (%)
# Lower = More trades (but more false signals)
# Higher = Fewer trades (but might miss opportunities)
#
# Conservative: 1.0 (only trade big spikes)
# Moderate: 0.5 (balanced)
# Aggressive: 0.3 (trade more often)
# Very Aggressive: 0.1 (lots of trades)
#
# Default: 0.3
# Recommendation: Start with 0.5-1.0, lower if you want more action

SPIKE_WINDOWS_MINUTES=10,30,60
# What: Time windows to check for spikes
# The bot checks: "Did price change in last 10 min? 30 min? 60 min?"
# It uses the MAXIMUM spike found across all windows
#
# More windows = More chances to find spikes
# Fewer windows = Simpler, maybe fewer signals
#
# Default: 10,30,60
# Examples:
#   10,30,60 (default - checks 3 windows)
#   5,15,30 (faster detection, shorter windows)
#   60 (only checks last hour)

USE_VOLATILITY_FILTER=true
# What: Filter out high-volatility periods (reduces false signals)
# When markets are crazy (lots of random movement), this pauses trading
#
# Options: true = enabled, false = disabled
# Default: true
# Recommendation: Keep true unless you want to trade volatile markets

MAX_VOLATILITY_CV=10.0
# What: How volatile is "too volatile" (Coefficient of Variation)
# Higher = Allow more volatility before pausing
# Lower = Pause trading more easily
#
# Default: 10.0
# Range: 5.0 to 20.0

MIN_SPIKE_STRENGTH=0.2
# What: Minimum spike strength to actually trade
# Even if spike threshold is met, spike must be "strong enough"
#
# Default: 0.2
# Range: 0.1 to 1.0

# ============================================================
# TRADING SETTINGS
# ============================================================

DEFAULT_TRADE_SIZE_USD=1.00
# What: How much money to trade each time
# Minimum: 1.00 (Polymarket's minimum)
# Maximum: 100.00 (safety limit)
#
# Conservative: 1.00 to 2.00
# Moderate: 2.00 to 5.00
# Aggressive: 5.00 to 10.00
#
# Default: 1.00
# Recommendation: Start at 1.00, increase slowly

MIN_TRADE_USD=1.0
# What: Minimum allowed trade size
# Default: 1.0 (Polymarket requirement)
# Don't change this

MAX_TRADE_USD=100.0
# What: Maximum allowed trade size (safety limit)
# Default: 100.0
# Only increase if you know what you're doing!

# ============================================================
# RISK MANAGEMENT (CRITICAL!)
# ============================================================

TAKE_PROFIT_PCT=0.5
# What: Exit with profit when price moves this % in your favor
# Lower = Take profits sooner (more wins, smaller profits)
# Higher = Let profits run (bigger wins, might miss some)
#
# Conservative: 0.3 (quick profits)
# Moderate: 0.5 (balanced)
# Aggressive: 1.0 (hold for bigger moves)
#
# Default: 0.5
# Recommendation: Start with 0.3-0.5

STOP_LOSS_PCT=0.4
# What: Exit with loss when price moves this % against you
# This LIMITES your losses on bad trades
#
# Conservative: 0.3 (tight stop loss)
# Moderate: 0.5 (more room)
# Aggressive: 1.0 (loose stop loss)
#
# Default: 0.4
# Important: Should be slightly LOWER than TAKE_PROFIT

MAX_HOLD_SECONDS=30
# What: Force exit after this many seconds (even at a loss)
# Prevents being stuck in bad positions forever
#
# Quick trading: 30 (default)
# Patient: 60 to 120
# Very patient: 300 to 600
#
# Default: 30
# Recommendation: Start with 30-60

COOLDOWN_SECONDS=30
# What: Wait this long after a trade before trading again
# Prevents overtrading during crazy periods
#
# Default: 30
# Range: 10 (fast) to 300 (slow)

# ============================================================
# PRICE SETTINGS
# ============================================================

PRICE_HISTORY_SIZE=3600
# What: How many price points to remember
# More history = Better spike detection, but uses more memory
#
# Default: 3600 (about 1 hour at 1-second intervals)
# Don't change unless you know what you're doing

PRICE_POLL_INTERVAL_SEC=1.0
# What: How often to check price (seconds) - for REST mode only
# WebSocket is faster (~1 second real-time)
#
# Default: 1.0
# Range: 0.5 to 5.0

USE_GAMMA_PRIMARY=false
# What: Use Gamma API (Polymarket's UI price) as main price source
# Gamma prices are often better for illiquid markets
#
# Options: true = use Gamma, false = use CLOB
# Default: false
# When to change: If CLOB prices seem wrong, try true

# ============================================================
# ORDERBOOK GUARDS (Safety)
# ============================================================

MIN_BID_LIQUIDITY=0.1
# What: Minimum buy orders required to enter a trade
# Prevents trading in dead markets
#
# Default: 0.1
# Higher = Safer (only trade liquid markets)

MIN_ASK_LIQUIDITY=0.1
# What: Minimum sell orders required to enter a trade
#
# Default: 0.1
# Higher = Safer

MAX_SPREAD_PCT=1.0
# What: Maximum price gap between buy and sell orders
# Spread = (Ask - Bid) / Bid × 100
# Wide spread = illiquid market = risky
#
# Default: 1.0
# Lower = Safer (only trade tight markets)

# ============================================================
# LOGGING & DEBUGGING
# ============================================================

LOG_LEVEL=INFO
# What: How much detail in logs
# Options: DEBUG, INFO, WARNING, ERROR
# Default: INFO
# When to change: Use DEBUG if troubleshooting

LOG_FORMAT=PLAIN
# What: Log format
# Options: PLAIN (readable), JSON (for parsing)
# Default: PLAIN

LOG_FILE=logs/bot.log
# What: Where to save all session logs
# Options: Any file path (logs/ directory created automatically)
# Default: logs/bot.log
# Note: ALL sessions are appended to this file for review

# ============================================================
# SAFETY SWITCH
# ============================================================

DRY_RUN=true
# What: Practice mode vs Real trading
# true = Simulate trades (NO real money)
# false = REAL trading with REAL money
#
# ⚠️ ALWAYS START WITH TRUE ⚠️
# Default: true
# Only change to false when you're ready!
```

### Configuration Templates

**For Testing (Super Conservative):**
```env
DEFAULT_TRADE_SIZE_USD=1.00
SPIKE_THRESHOLD_PCT=1.0
TAKE_PROFIT_PCT=0.3
STOP_LOSS_PCT=0.2
MAX_HOLD_SECONDS=30
COOLDOWN_SECONDS=60
DRY_RUN=true
```

**For Active Trading (Moderate):**
```env
DEFAULT_TRADE_SIZE_USD=2.00
SPIKE_THRESHOLD_PCT=0.5
TAKE_PROFIT_PCT=0.5
STOP_LOSS_PCT=0.4
MAX_HOLD_SECONDS=60
COOLDOWN_SECONDS=30
DRY_RUN=true
```

**For Aggressive Trading (More Risk):**
```env
DEFAULT_TRADE_SIZE_USD=3.00
SPIKE_THRESHOLD_PCT=0.3
TAKE_PROFIT_PCT=1.0
STOP_LOSS_PCT=0.5
MAX_HOLD_SECONDS=120
COOLDOWN_SECONDS=15
DRY_RUN=false  # ⚠️ Real money!
```

---

## Part 6: Pre-Flight Checks (Before Trading)

### Step 6.1: Verify Your Setup

```bash
python scripts/check_setup.py
```

**What to look for:**

```
============================================================
  POLYMARKET TRADING AGENT - SETUP VERIFICATION
============================================================

1. Environment Configuration (.env)
  ✅ .env file exists
  ✅ PRIVATE_KEY set: 64 chars
  ✅ SIGNATURE_TYPE: 0 = EOA (direct wallet)

2. Trading Configuration (.env)
  ✅ Market slug: wta-mcnally-juvan-2026-01-09
  ✅ Default trade size: $1.00
  ✅ Spike threshold: 0.3%
  ✅ DRY_RUN: ENABLED  ⬅️ Make sure this says ENABLED!
  ✅ TP / SL / MaxHold: 0.5% / 0.4% / 30s

3. Wallet & Balance Check
  ✅ Polygon RPC connected
  ✅ Wallet address: 0x1234...
  ✅ MATIC for gas: 1.2345 MATIC
  ✅ USDC.e balance: $10.50

4. Polymarket API Check
  ✅ API connection: Found 5000+ markets
  ✅ API credentials: Key: abc123...

5. Contract Allowances
  ✅ CTF Exchange: APPROVED
  ✅ NEG_RISK Exchange: APPROVED

============================================================
SUMMARY
============================================================
  ✅ All checks passed! You're ready to trade.
```

### Step 6.2: What If Checks Fail?

**Problem: `.env file exists` ❌**

```
Solution: Copy the file first
cp .env.example .env
Then edit it with your settings
```

**Problem: `PRIVATE_KEY` ❌**

```
Solution: Check your private key
- Must be exactly 64 characters
- No spaces or quotes
- No "0x" at the start
```

**Problem: `MATIC for gas` ❌**

```
Solution: Add MATIC to your wallet
1. Go to a faucet (like https://faucet.polygon.technology/)
2. Enter your wallet address
3. Get some free MATIC
```

**Problem: `USDC.e balance` ❌**

```
Solution: Add USDC.e to your wallet
1. Buy USDC on an exchange
2. Bridge it to Polygon as USDC.e
3. Send to your wallet
```

**Problem: `NOT APPROVED` for allowances**

```
Solution: Approve the contracts on Polymarket
1. Go to polymarket.com
2. Connect your wallet
3. Try to make a trade (any amount)
4. This will approve the contracts
```

### Step 6.3: Quick Pre-Flight Check

Before starting the bot for real trading:

```bash
python scripts/check_setup.py --pre-flight
```

This does a quick check of:
- Config loaded correctly
- Wallet balance
- Market liquidity (is it active?)

---

## Part 7: Running the Bot

### Step 7.1: Starting the Bot

**Option A: Direct start**
```bash
python start_bot.py
```

**Option B: Quick start with checks (NEW - Recommended for beginners)**
```bash
python scripts/quick_start.py
```

**Option C: Using the CLI (NEW)**
```bash
python poly.py start
```

**What you should see:**

```
INFO - Starting Polymarket Spike Sam Bot
INFO - API credentials ready
INFO - Resolved token id for 'Match Winner': 65825053959363891562...
INFO - ============================================================
INFO - Bot starting...
INFO - ============================================================
INFO - Signature mode: 2
INFO - Token: 65825053959363891562...
INFO - Trade size: $1.00
INFO - Spike threshold: 0.3000%
INFO - Spike windows: [10, 30, 60] min
INFO - Take profit: 0.5% | Stop loss: 0.4%
INFO - Max hold: 30s
INFO - Dry run: True
INFO - ============================================================
INFO - 🔍 WebSocket ENABLED - Real-time spike detection (~1 second)
INFO - WebSocket client started in background thread
INFO - Connecting to wss://ws-subscriptions-clob.polymarket.com/ws/market...
INFO - WebSocket connected!
INFO - Subscribed to market for token 65825053959363891562...
INFO - ✓ WebSocket connected
INFO - 📡 Fetching initial price from REST API...
INFO -    Initial price: 0.8800
```

### Step 7.2: What Happens Next

The bot will:
1. Connect to Polymarket via WebSocket
2. Fetch the initial price
3. Watch for price changes
4. When a spike is detected → Trade!
5. Monitor position → Exit at TP/SL/Time

**Status updates every minute:**
```
INFO - Status: Price=0.8900 | Position=NONE | WSS=✓ | Spikes detected=0
```

### Step 7.3: Stopping the Bot

**Gracefully stop:**
```
Press Ctrl+C
```

The bot will (with Killswitch enabled):
1. Catch the shutdown signal
2. **Close any open positions automatically** (NEW - Killswitch feature)
3. Save your P&L data to position.json
4. Exit cleanly

**Killswitch Configuration:**
```env
KILLSWITCH_ON_SHUTDOWN=true   # Automatically close positions on shutdown
KILLSWITCH_ON_SHUTDOWN=false  # Leave positions open (manual management)
```

### Step 7.4: What 30 Minutes of Real Trading Looks Like

Below is a **realistic log** from a 30-minute trading session. This is what you'll see on your screen when the bot is running with real money.

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                    Polymarket Spike Sam Bot v2.0                            ║
║                  ⚠️  REAL TRADING MODE - REAL MONEY  ⚠️                      ║
╚══════════════════════════════════════════════════════════════════════════════╝

[2026-01-10 14:30:00] INFO - Starting Polymarket Spike Sam Bot
[2026-01-10 14:30:00] INFO - Loading configuration from .env
[2026-01-10 14:30:00] INFO - ============================================================
[2026-01-10 14:30:01] INFO - MARKET: WTA - McNally vs Juvan
[2026-01-10 14:30:01] INFO - TOKEN ID: 65825053959363891562... (Match Winner)
[2026-01-10 14:30:01] INFO - ============================================================
[2026-01-10 14:30:01] INFO - Trade size: $5.00 USD
[2026-01-10 14:30:01] INFO - Spike threshold: 1.50%
[2026-01-10 14:30:01] INFO - Spike windows: [10, 30, 60] minutes
[2026-01-10 14:30:01] INFO - Take profit: 3.00% | Stop loss: 2.50%
[2026-01-10 14:30:01] INFO - Max hold time: 45 seconds
[2026-01-10 14:30:01] INFO - ============================================================
[2026-01-10 14:30:01] INFO - ⚠️  DRY_RUN: FALSE - TRADING WITH REAL MONEY
[2026-01-10 14:30:01] INFO - ============================================================
[2026-01-10 14:30:01] INFO - 🔍 WebSocket ENABLED - Real-time spike detection
[2026-01-10 14:30:02] INFO - Connecting to wss://ws-subscriptions-clob.polymarket.com/ws/market...
[2026-01-10 14:30:03] INFO - WebSocket connected!
[2026-01-10 14:30:03] INFO - Subscribed to market for token 65825053959363891562...
[2026-01-10 14:30:04] INFO - ✓ WebSocket receiving data
[2026-01-10 14:30:04] INFO - 📊 TRADE: 0.5400 YES size=450
[2026-01-10 14:30:04] INFO - Initial price: 0.5400 (from WebSocket)
[2026-01-10 14:30:04] INFO - Building price history (warmup)...
[2026-01-10 14:30:34] INFO - Price history warmed up (30 prices)
[2026-01-10 14:30:34] INFO - ✓ Bot ready, waiting for spikes...

═══════════════════════════════════════════════════════════════════════════════
                            MINUTE 1 - Watching...
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:31:04] INFO - 📊 TRADE: 0.5420 YES size=120
[2026-01-10 14:31:34] INFO - Status: Price=0.5420 | Position=NONE | WSS=✓ | Spikes=0
[2026-01-10 14:32:04] INFO - 📊 TRADE: 0.5410 YES size=89

═══════════════════════════════════════════════════════════════════════════════
                            MINUTE 3 - Spike Detected!
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:33:12] INFO - 📊 TRADE: 0.5680 YES size=890
[2026-01-10 14:33:12] INFO - ⚡ SPIKE DETECTED!
[2026-01-10 14:33:12] INFO -    Current price: 0.5680
[2026-01-10 14:33:12] INFO -    10-min avg: 0.5415 | 30-min avg: 0.5408
[2026-01-10 14:33:12] INFO -    Spike: +4.89% (10-min window)
[2026-01-10 14:33:12] INFO -    Volatility: 0.018 (normal)
[2026-01-10 14:33:12] INFO - → Signal: SELL (fade the upward spike)
[2026-01-10 14:33:12] INFO - 📈 Executing SELL order...
[2026-01-10 14:33:13] INFO -    Order ID: 48239104719283...
[2026-01-10 14:33:14] INFO - ✅ SELL filled! Price: 0.5660 | Size: 8.83 shares
[2026-01-10 14:33:14] INFO - 💼 Position OPEN: SHORT @ 0.5660
[2026-01-10 14:33:14] INFO -    Entry: $5.00 | Exit targets: TP=0.5830, SL=0.5518
[2026-01-10 14:33:14] INFO -    Max hold: 45s | Elapsed: 0s

═══════════════════════════════════════════════════════════════════════════════
                       MINUTE 4 - Position Active
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:33:44] INFO - 📊 TRADE: 0.5630 YES size=234
[2026-01-10 14:33:44] INFO - 💼 Position: SHORT @ 0.5660 | Current: 0.5630
[2026-01-10 14:33:44] INFO -    Unrealized P&L: +$0.47 (+0.53%)
[2026-01-10 14:33:44] INFO -    Hold time: 30s / 45s max
[2026-01-10 14:33:44] INFO -    Checking exits: TP=False, SL=False, Time=False
[2026-01-10 14:33:52] INFO - 📊 TRADE: 0.5600 YES size=567
[2026-01-10 14:33:52] INFO - 🎯 TAKE PROFIT triggered! (held 38s)
[2026-01-10 14:33:52] INFO -    Entry: 0.5660 → Current: 0.5600
[2026-01-10 14:33:52] INFO -    Expected move: -1.06% | Actual: -1.06%
[2026-01-10 14:33:52] INFO - 📈 Executing BUY to cover...
[2026-01-10 14:33:53] INFO -    Order ID: 48239104719295...
[2026-01-10 14:33:54] INFO - ✅ BUY filled! Price: 0.5600 | Size: 8.83 shares
[2026-01-10 14:33:54] INFO - 💰 Position CLOSED
[2026-01-10 14:33:54] INFO -    Realized P&L: +$0.53 (+1.06%)
[2026-01-10 14:33:54] INFO -    Total P&L: +$0.53 | Wins: 1 | Losses: 0
[2026-01-10 14:33:54] INFO - 💾 Position saved to data/position.json
[2026-01-10 14:34:04] INFO - Status: Price=0.5600 | Position=NONE | WSS=✓ | Spikes=1

═══════════════════════════════════════════════════════════════════════════════
                       MINUTES 5-10 - Quiet Period
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:35:04] INFO - Status: Price=0.5590 | Position=NONE | WSS=✓ | Spikes=1
[2026-01-10 14:35:28] INFO - 📊 TRADE: 0.5570 YES size=145
[2026-01-10 14:36:04] INFO - Status: Price=0.5570 | Position=NONE | WSS=✓ | Spikes=1
[2026-01-10 14:36:42] INFO - 📊 TRADE: 0.5595 YES size=332
[2026-01-10 14:37:04] INFO - Status: Price=0.5595 | Position=NONE | WSS=✓ | Spikes=1
[2026-01-10 14:37:51] INFO - 📊 TRADE: 0.5580 YES size=89
[2026-01-10 14:38:04] INFO - Status: Price=0.5580 | Position=NONE | WSS=✓ | Spikes=1
[2026-01-10 14:38:56] INFO - 📊 TRADE: 0.5565 YES size=201
[2026-01-10 14:39:04] INFO - Status: Price=0.5565 | Position=NONE | WSS=✓ | Spikes=1
[2026-01-10 14:39:48] INFO - 📊 TRADE: 0.5575 YES size=178
[2026-01-10 14:40:04] INFO - Status: Price=0.5575 | Position=NONE | WSS=✓ | Spikes=1

═══════════════════════════════════════════════════════════════════════════════
                            MINUTE 11 - Spike Down!
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:41:18] INFO - 📊 TRADE: 0.5320 YES size=1200
[2026-01-10 14:41:18] INFO - ⚡ SPIKE DETECTED!
[2026-01-10 14:41:18] INFO -    Current price: 0.5320
[2026-01-10 14:41:18] INFO -    10-min avg: 0.5572 | 30-min avg: 0.5540
[2026-01-10 14:41:18] INFO -    Spike: -4.53% (10-min window)
[2026-01-10 14:41:18] INFO -    Volatility: 0.022 (elevated)
[2026-01-10 14:41:18] INFO - → Signal: BUY (fade the downward spike)
[2026-01-10 14:41:18] INFO - 📉 Executing BUY order...
[2026-01-10 14:41:19] INFO -    Order ID: 48239104719301...
[2026-01-10 14:41:20] INFO - ✅ BUY filled! Price: 0.5340 | Size: 9.36 shares
[2026-01-10 14:41:20] INFO - 💼 Position OPEN: LONG @ 0.5340
[2026-01-10 14:41:20] INFO -    Entry: $5.00 | Exit targets: TP=0.5500, SL=0.5187
[2026-01-10 14:41:20] INFO -    Max hold: 45s | Elapsed: 0s

═══════════════════════════════════════════════════════════════════════════════
                       MINUTE 12 - Position Active
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:42:04] INFO - 📊 TRADE: 0.5360 YES size=445
[2026-01-10 14:42:04] INFO - 💼 Position: LONG @ 0.5340 | Current: 0.5360
[2026-01-10 14:42:04] INFO -    Unrealized P&L: +$0.19 (+0.37%)
[2026-01-10 14:42:04] INFO -    Hold time: 44s / 45s max
[2026-01-10 14:42:04] INFO -    Checking exits: TP=False, SL=False, Time=False
[2026-01-10 14:42:05] INFO - 🕐 TIME EXIT triggered! (held 45s)
[2026-01-10 14:42:05] INFO -    Entry: 0.5340 → Current: 0.5360
[2026-01-10 14:42:05] INFO -    Max hold reached (45s)
[2026-01-10 14:42:05] INFO - 📈 Executing SELL to close...
[2026-01-10 14:42:06] INFO -    Order ID: 48239104719312...
[2026-01-10 14:42:07] INFO - ✅ SELL filled! Price: 0.5350 | Size: 9.36 shares
[2026-01-10 14:42:07] INFO - 💰 Position CLOSED
[2026-01-10 14:42:07] INFO -    Realized P&L: +$0.09 (+0.19%)
[2026-01-10 14:42:07] INFO -    Total P&L: +$0.62 | Wins: 2 | Losses: 0
[2026-01-10 14:42:07] INFO - 💾 Position saved to data/position.json

═══════════════════════════════════════════════════════════════════════════════
                       MINUTES 13-20 - Waiting...
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:43:04] INFO - Status: Price=0.5350 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:43:27] INFO - 📊 TRADE: 0.5370 YES size=89
[2026-01-10 14:44:04] INFO - Status: Price=0.5370 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:44:51] INFO - 📊 TRADE: 0.5385 YES size=156
[2026-01-10 14:45:04] INFO - Status: Price=0.5385 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:45:42] INFO - 📊 TRADE: 0.5375 YES size=234
[2026-01-10 14:46:04] INFO - Status: Price=0.5375 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:46:38] INFO - 📊 TRADE: 0.5390 YES size=312
[2026-01-10 14:47:04] INFO - Status: Price=0.5390 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:47:55] INFO - 📊 TRADE: 0.5405 YES size=445
[2026-01-10 14:48:04] INFO - Status: Price=0.5405 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:48:41] INFO - 📊 TRADE: 0.5395 YES size=178
[2026-01-10 14:49:04] INFO - Status: Price=0.5395 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:49:52] INFO - 📊 TRADE: 0.5410 YES size=201
[2026-01-10 14:50:04] INFO - Status: Price=0.5410 | Position=NONE | WSS=✓ | Spikes=2
[2026-01-10 14:50:33] INFO - 📊 TRADE: 0.5425 YES size=389
[2026-01-10 14:51:04] INFO - Status: Price=0.5425 | Position=NONE | WSS=✓ | Spikes=2

═══════════════════════════════════════════════════════════════════════════════
                            MINUTE 21 - Spike Up!
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:52:16] INFO - 📊 TRADE: 0.5680 YES size=1450
[2026-01-10 14:52:16] INFO - ⚡ SPIKE DETECTED!
[2026-01-10 14:52:16] INFO -    Current price: 0.5680
[2026-01-10 14:52:16] INFO -    10-min avg: 0.5395 | 30-min avg: 0.5450
[2026-01-10 14:52:16] INFO -    Spike: +5.28% (10-min window)
[2026-01-10 14:52:16] INFO -    Volatility: 0.025 (elevated)
[2026-01-10 14:52:16] INFO - → Signal: SELL (fade the upward spike)
[2026-01-10 14:52:16] INFO - 📈 Executing SELL order...
[2026-01-10 14:52:17] INFO -    Order ID: 48239104719328...
[2026-01-10 14:52:18] INFO - ✅ SELL filled! Price: 0.5660 | Size: 8.83 shares
[2026-01-10 14:52:18] INFO - 💼 Position OPEN: SHORT @ 0.5660
[2026-01-10 14:52:18] INFO -    Entry: $5.00 | Exit targets: TP=0.5830, SL=0.5518
[2026-01-10 14:52:18] INFO -    Max hold: 45s | Elapsed: 0s

═══════════════════════════════════════════════════════════════════════════════
                       MINUTE 22 - Position in Trouble
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:53:04] INFO - 📊 TRADE: 0.5720 YES size=890
[2026-01-10 14:53:04] INFO - 💼 Position: SHORT @ 0.5660 | Current: 0.5720
[2026-01-10 14:53:04] INFO -    Unrealized P&L: -$0.53 (-1.06%)
[2026-01-10 14:53:04] INFO -    Hold time: 46s / 45s max
[2026-01-10 14:53:04] INFO -    Checking exits: TP=False, SL=False, Time=True
[2026-01-10 14:53:04] INFO - 🕐 TIME EXIT triggered! (held 46s)
[2026-01-10 14:53:04] INFO -    Entry: 0.5660 → Current: 0.5720
[2026-01-10 14:53:04] INFO -    Max hold reached (45s)
[2026-01-10 14:53:04] INFO - 📈 Executing BUY to cover...
[2026-01-10 14:53:05] INFO -    Order ID: 48239104719335...
[2026-01-10 14:53:06] INFO - ✅ BUY filled! Price: 0.5715 | Size: 8.83 shares
[2026-01-10 14:53:06] INFO - 💰 Position CLOSED
[2026-01-10 14:53:06] INFO -    Realized P&L: -$0.49 (-0.98%)
[2026-01-10 14:53:06] INFO -    Total P&L: +$0.13 | Wins: 2 | Losses: 1
[2026-01-10 14:53:06] INFO - 💾 Position saved to data/position.json

═══════════════════════════════════════════════════════════════════════════════
                       MINUTES 23-29 - Quiet Again
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 14:54:04] INFO - Status: Price=0.5715 | Position=NONE | WSS=✓ | Spikes=3
[2026-01-10 14:54:41] INFO - 📊 TRADE: 0.5700 YES size=234
[2026-01-10 14:55:04] INFO - Status: Price=0.5700 | Position=NONE | WSS=✓ | Spikes=3
[2026-01-10 14:55:38] INFO - 📊 TRADE: 0.5715 YES size=156
[2026-01-10 14:56:04] INFO - Status: Price=0.5715 | Position=NONE | WSS=✓ | Spikes=3
[2026-01-10 14:56:52] INFO - 📊 TRADE: 0.5690 YES size=312
[2026-01-10 14:57:04] INFO - Status: Price=0.5690 | Position=NONE | WSS=✓ | Spikes=3
[2026-01-10 14:57:39] INFO - 📊 TRADE: 0.5705 YES size=445
[2026-01-10 14:58:04] INFO - Status: Price=0.5705 | Position=NONE | WSS=✓ | Spikes=3
[2026-01-10 14:58:51] INFO - 📊 TRADE: 0.5710 YES size=178
[2026-01-10 14:59:04] INFO - Status: Price=0.5710 | Position=NONE | WSS=✓ | Spikes=3

═══════════════════════════════════════════════════════════════════════════════
                            MINUTE 30 - Final Spike!
═══════════════════════════════════════════════════════════════════════════════

[2026-01-10 15:00:13] INFO - 📊 TRADE: 0.5480 YES size=980
[2026-01-10 15:00:13] INFO - ⚡ SPIKE DETECTED!
[2026-01-10 15:00:13] INFO -    Current price: 0.5480
[2026-01-10 15:00:13] INFO -    10-min avg: 0.5705 | 30-min avg: 0.5600
[2026-01-10 15:00:13] INFO -    Spike: -3.95% (10-min window)
[2026-01-10 15:00:13] INFO -    Volatility: 0.020 (elevated)
[2026-01-10 15:00:13] INFO - → Signal: BUY (fade the downward spike)
[2026-01-10 15:00:13] INFO - 📉 Executing BUY order...
[2026-01-10 15:00:14] INFO -    Order ID: 48239104719341...
[2026-01-10 15:00:15] INFO - ✅ BUY filled! Price: 0.5490 | Size: 9.10 shares
[2026-01-10 15:00:15] INFO - 💼 Position OPEN: LONG @ 0.5490
[2026-01-10 15:00:15] INFO -    Entry: $5.00 | Exit targets: TP=0.5655, SL=0.5333
[2026-01-10 15:00:15] INFO -    Max hold: 45s | Elapsed: 0s

[2026-01-10 15:00:51] INFO - 📊 TRADE: 0.5510 YES size=567
[2026-01-10 15:00:51] INFO - 💼 Position: LONG @ 0.5490 | Current: 0.5510
[2026-01-10 15:00:51] INFO -    Unrealized P&L: +$0.18 (+0.36%)
[2026-01-10 15:00:51] INFO -    Hold time: 36s / 45s max
[2026-01-10 15:00:51] INFO -    Checking exits: TP=False, SL=False, Time=False

[2026-01-10 15:00:59] INFO - 📊 TRADE: 0.5525 YES size=723
[2026-01-10 15:00:59] INFO - 🎯 TAKE PROFIT triggered! (held 44s)
[2026-01-10 15:00:59] INFO -    Entry: 0.5490 → Current: 0.5525
[2026-01-10 15:00:59] INFO -    Expected move: +1.27% | Actual: +0.64%
[2026-01-10 15:00:59] INFO - 📈 Executing SELL to close...
[2026-01-10 15:01:00] INFO -    Order ID: 48239104719348...
[2026-01-10 15:01:01] INFO - ✅ SELL filled! Price: 0.5520 | Size: 9.10 shares
[2026-01-10 15:01:01] INFO - 💰 Position CLOSED
[2026-01-10 15:01:01] INFO -    Realized P&L: +$0.23 (+0.55%)
[2026-01-10 15:01:01] INFO -    Total P&L: +$0.36 | Wins: 3 | Losses: 1
[2026-01-10 15:01:01] INFO - 💾 Position saved to data/position.json
```

### What Happened in This 30-Minute Session

| Minute | Event | Result |
|--------|-------|--------|
| 0-2 | Bot startup, WebSocket connection | Ready |
| 3 | **Spike UP +4.89%** → SELL | ✅ **+$0.53** (TP hit) |
| 4-10 | Quiet period, normal trading | Waiting |
| 11 | **Spike DOWN -4.53%** → BUY | ✅ **+$0.09** (Time exit) |
| 12-20 | Quiet period | Waiting |
| 21 | **Spike UP +5.28%** → SELL | ❌ **-$0.49** (Price kept rising) |
| 22-29 | Recovery period | Waiting |
| 30 | **Spike DOWN -3.95%** → BUY | ✅ **+$0.23** (TP hit) |

**Session Summary:**
- **Trades:** 4
- **Winning trades:** 3
- **Losing trades:** 1
- **Win rate:** 75%
- **Net profit:** +$0.36 (+0.72%)
- **Total volume:** $20.00 traded

### Key Things to Notice

1. **Most time is waiting** - The bot only trades when there's a genuine spike
2. **Not all trades win** - Trade #3 lost because price kept trending up (this happens!)
3. **Quick trades** - Most positions closed in 30-45 seconds
4. **Multiple exit types** - You saw Take Profit, Time Exit, and even a loss
5. **Real-time updates** - Every trade shows price, position, and unrealized P&L

### What the Log Messages Mean

The bot uses a clean [TAG] format for professional, parseable logs.

| Log Pattern | Meaning |
|-------------|---------|
| `[TRADE] 0.5680` | New trade occurred on Polymarket at this price |
| `[SPIKE_#N] +4.89%` | Bot found a price movement worth trading |
| `Spike: +4.89%` | How much price moved vs. historical average |
| `→ Signal: SELL` | Bot decides to sell (fade upward spike) |
| `[ORDER_FILLED]` | Your order was successfully executed |
| `[POSITION_OPENED]` | You now have an active position |
| `[POSITION_CLOSED]` | Position exited with final P&L |
| `[EXIT_TAKE_PROFIT]` | Price moved in your favor, exited at target |
| `[EXIT_TIME]` | Held too long, exited at time limit |
| `[BALANCE_OK]` | Sufficient funds confirmed for trade |
| `[ORDERBOOK_HEALTHY]` | Orderbook has enough liquidity |
| `[PRE_CHECK_FAILED]` | Order skipped (validation failed) |
| `[ENTRY_SKIPPED]` | Entry not attempted due to pre-check |

### Step 7.5: Viewing and Analyzing Your Logs

All bot sessions are **automatically saved** to unique log files for easy analysis.

**Where logs are saved:**
```
logs/bot_20250110_143052.log
logs/bot_20250110_151230.log
logs/bot_20250110_163045.log
```

Each bot run creates a new file with timestamp: `bot_YYYYMMDD_HHMMSS.log`

**How to view your logs:**

**Windows:**
```bash
# View the entire log file
notepad logs\bot_20250110_143052.log

# View last 50 lines (PowerShell)
Get-Content logs\bot_20250110_143052.log -Tail 50

# Search for all trades in the log
findstr "TRADE" logs\bot_20250110_143052.log

# Search for profits/losses
findstr "P&L" logs\bot_20250110_143052.log

# List all log files
dir logs\bot_*.log /O-D
```

**Mac/Linux:**
```bash
# View the entire log file
cat logs/bot_20250110_143052.log

# View last 50 lines
tail -n 50 logs/bot_20250110_143052.log

# Follow log in real-time (while bot is running)
tail -f logs/bot_*.log

# Search for all trades
grep "TRADE" logs/bot_20250110_143052.log

# Search for profits/losses
grep "P&L\|POSITION_CLOSED" logs/bot_20250110_143052.log

# Count total trades
grep -c "SPIKE_" logs/bot_20250110_143052.log

# List all log files
ls -lt logs/bot_*.log
```

**What's in the log file:**

| Content | Description |
|---------|-------------|
| All console output | Everything you see on screen is saved |
| Session timestamp | Unique file for each bot run |
| Every trade | Entry, exit, P&L for all positions |
| Errors and warnings | Any issues that occurred |
| WebSocket status | Connection/disconnection events |
| Price updates | All price changes seen |
| Pre-check results | Balance and orderbook validation |

**Log file behavior:**
- **Per-session files** - Each run creates a new timestamped log
- **Clean format** - Professional [TAG] style, no emojis
- **Easy to parse** - Structured tags for filtering
- `logs/` directory is created automatically
- Logs are excluded from git (security)

---

## Part 8: Understanding Every Scenario You Might Encounter

### Scenario 8.1: Bot Just Started, Nothing Happening

**What you see:**
```
Status: Price=0.8800 | Position=NONE | WSS=✓ | Spikes detected=0
```

**What's happening:** Normal! The bot is waiting for a spike.

**What to do:** Nothing. Just wait. Spikes don't happen constantly.

**How long to wait:** Depends on the market:
- Live sports: Spikes every few minutes
- Slow markets: Might take hours

### Scenario 8.2: Spike Detected!

**What you see:**
```
INFO - 📊 TRADE: 0.9000 BUY size=10
INFO - 🚨 SPIKE #1: +2.27% → 🔴 SELL $1.00
INFO - 📣 ENTRY SELL $1.00 at 0.9000
INFO - DRY-RUN: Would place SELL $1.00...
INFO - ✓ Position open
```

**What's happening:**
1. Price jumped from 0.88 to 0.90 (+2.27%)
2. Bot triggered (above 0.3% threshold)
3. Bot is SELLING (betting price will drop)

**What to do:** Watch and wait. The bot will manage the position automatically.

### Scenario 8.3: Take Profit Hit!

**What you see:**
```
INFO - 🏆 EXIT via Take profit (+0.5% >= 0.5%): BUY $1.00 at 0.8950
INFO -    P&L: $+0.01 (+0.56%) | Hold: 0.2min
INFO -    Total P&L: $+0.01 | Win Rate: 1/1
```

**What's happening:**
- Bot bought back at 0.8950
- Sold at 0.9000, bought at 0.8950 = profit!
- Position closed with +$0.01 profit

**What to do:** Celebrate! The trade was successful.

### Scenario 8.4: Stop Loss Hit

**What you see:**
```
INFO - 🛑 EXIT via Stop loss (-0.4%): BUY $1.00 at 0.9050
INFO -    P&L: -$0.01 (-0.56%) | Hold: 0.1min
INFO -    Total P&L: -$0.01 | Win Rate: 0/1
```

**What's happening:**
- Price kept going UP instead of down
- Bot hit the stop loss to limit damage
- Small loss instead of potentially bigger loss

**What to do:** This is normal. Not every trade wins.

### Scenario 8.5: Time Exit

**What you see:**
```
INFO - ⏱️ EXIT via Time exit: BUY $1.00 at 0.8980
INFO -    P&L: -$0.00 (-0.22%) | Hold: 0.5min
```

**What's happening:**
- Bot held for MAX_HOLD_SECONDS (30 seconds)
- Price didn't hit TP or SL
- Forced exit to avoid being stuck

**What to do:** Normal. Time limit prevents being stuck forever.

### Scenario 8.6: WebSocket Disconnects

**What you see:**
```
WARNING - WebSocket error: Event loop is closed
WARNING - ⚠ WebSocket disconnected
INFO - Reconnecting in 1.0 seconds... (attempt 1)
INFO - WebSocket connected!
```

**What's happening:** Temporary connection issue, bot reconnecting.

**What to do:** Nothing. Bot reconnects automatically.

**If it keeps disconnecting:**
1. Check your internet connection
2. Try increasing `WSS_RECONNECT_DELAY=2.0`
3. If problem persists, restart the bot

### Scenario 8.7: No Trades for a Long Time

**What you see:**
```
Status: Price=0.8800 | Position=NONE | WSS=✓ | Spikes detected=0
```
...same message for 30 minutes...

**What's happening:** Market is calm, no spikes.

**What to do:**
1. **Option A:** Wait patiently (market might become active)
2. **Option B:** Lower `SPIKE_THRESHOLD_PCT` to 0.2 or 0.1
3. **Option C:** Switch to a more active market

**How to find active markets:**
```bash
python scripts/poly_tools.py list-events
```

### Scenario 8.8: Bot Keeps Losing

**What you see:**
```
Total P&L: -$0.15 | Win Rate: 3/10
```

**What's happening:** Strategy isn't working on this market.

**What to do:**
1. **Stop the bot** (Ctrl+C)
2. **Analyze why:**
   - Is market trending? (fade strategy hates trends)
   - Is threshold too low? (getting false signals)
   - Is market illiquid? (hard to trade)
3. **Try different settings:**
   - Increase `SPIKE_THRESHOLD_PCT` to 1.0
   - Increase `MAX_HOLD_SECONDS` to 60
   - Switch to a different market
4. **Or stop trading** this market

### Scenario 8.9: Pre-Check Failures (Order Skipped)

**What you see:**
```
WARNING - [PRE_CHECK_FAILED] Insufficient balance: $0.50 < $1.00
INFO - [ENTRY_SKIPPED] Balance/allowance issue
```

**What's happening:** The bot is smart - it checks if the trade can succeed BEFORE trying. This saves you gas fees.

**Common pre-check failures:**

| Message | Cause | Solution |
|---------|-------|----------|
| `Insufficient balance: $X < $Y` | Not enough USDC.e | Add funds or reduce `DEFAULT_TRADE_SIZE_USD` |
| `Insufficient allowance` | Contract not approved | Make one trade on Polymarket website |
| `Low bid liquidity: $X` | Not enough buyers for SELL | Choose more liquid market |
| `Low ask liquidity: $X` | Not enough sellers for BUY | Choose more liquid market |
| `Wide spread: X% > Y%` | Bid/ask gap too large | Wait or switch markets |

**What to do:**
1. Check the specific error message
2. Follow the solution in the table above
3. The bot will continue trying - it's protecting you from failed orders

### Scenario 8.10: Bot Crashes

**What you see:**
```
Traceback (most recent call last):
...
ERROR - Something went wrong
```

**What to do:**
1. **Screenshot the error**
2. **Check your position:**
```bash
python scripts/check_status.py
```
3. **Restart the bot:**
```bash
python start_bot.py
```
4. **If it keeps crashing:**
   - Check `DRY_RUN=true` (if not, set it!)
   - Run `python scripts/check_setup.py`
   - Check for typo in `.env` file

### Scenario 8.11: Order Not Filling

**What you see:**
```
ERROR - Order not filled: No matching orders
```

**What's happening:** Market has no buyers/sellers at your price.

**What to do:**
1. Check market liquidity:
```bash
python scripts/check_orderbook.py
```
2. If liquidity is low → switch markets
3. Try lowering `DEFAULT_TRADE_SIZE_USD`

### Scenario 8.12: Computer Crashes / Power Outage

**What happens:** Bot stops suddenly.

**When you restart:**
- Bot reads `data/position.json`
- Recovers your P&L and position state
- Continues from where it left off

**What to do:**
```bash
# Check your position state
python scripts/check_status.py

# Restart bot
python start_bot.py
```

**Note:** If you had an open position during crash, the bot will close it on restart (or manage it based on settings).

### Scenario 8.13: Multiple Positions Open

**What you see:**
```
Position: OPEN | Entry: 0.9000 | P&L: -0.50%
```
...and another trade happens...

**What happens:** Bot respects `MAX_CONCURRENT_TRADES=1`

**If this setting is higher**, bot might open multiple positions.

**What to do:**
- Keep `MAX_CONCURRENT_TRADES=1` for safety
- Emergency exit:
```bash
python scripts/sell_all_positions.py
```

### Scenario 8.14: Market Resolution (Event Finished)

**What you see:**
```
ERROR - Market resolved or closed
```

**What's happening:** The event is over, market is closed.

**What to do:**
1. Stop the bot (Ctrl+C)
2. Pick a new active market
3. Update `MARKET_SLUG` in `.env`
4. Restart

**How to find active markets:**
```bash
python scripts/poly_tools.py list-events
```

### Scenario 8.15: Balance Too Low

**What you see:**
```
ERROR - Insufficient balance
```

**What's happening:** Not enough USDC.e to trade.

**What to do:**
1. Add more USDC.e to your wallet
2. Or lower `DEFAULT_TRADE_SIZE_USD`
3. Restart bot

### Scenario 8.16: Gas Too High

**What you see:**
```
WARNING - Gas price high, trade may be expensive
```

**What's happening:** Polygon network is busy.

**What to do:**
- Let it run (trades will still work, just more expensive)
- Or wait for gas to go down
- Or temporarily stop trading

### Scenario 8.17: Price Stuck at 0.01 or 0.99

**What you see:**
```
Initial price: 0.99
Status: Price=0.99 | Position=NONE
```
...never changes...

**What's happening:** Market is essentially resolved or dead.

**What to do:**
1. This market is done, pick a new one
2. Try `USE_GAMMA_PRIMARY=true` in `.env`
3. Switch to a live event

### Scenario 8.18: Spikes Detected But No Trades

**What you see:**
```
SPIKE #1: +0.5% → 🔴 SELL $1.00
Risk check failed: Cooldown active
```

**What's happening:** Bot is in cooldown after last trade.

**What to do:** Wait for cooldown to expire (`COOLDOWN_SECONDS`).

**If you want to trade more often:** Lower `COOLDOWN_SECONDS`.

### Scenario 8.19: Bot Opens Position You Don't Agree With

**What you see:**
```
SPIKE #1: +0.35% → 🔴 SELL $1.00
```

**What you think:** "That's barely a spike! Don't sell!"

**What's happening:** Bot detected spike across one of the time windows.

**What to do:**
- **Option A:** Trust the bot and let it run
- **Option B:** Stop and adjust `SPIKE_THRESHOLD_PCT` higher
- **Option C:** Emergency exit: `python scripts/sell_all_positions.py`

### Scenario 8.20: Very Fast Price Movement

**What you see:**
```
TRADE: 0.80 BUY
TRADE: 0.82 BUY
TRADE: 0.85 BUY
TRADE: 0.78 BUY
SPIKE #1: +8.5% → 🔴 SELL $1.00
```

**What's happening:** Very volatile market (lots of trades).

**What to do:**
- Bot will handle it (spike detected, trade placed)
- Consider increasing `STOP_LOSS_PCT` for volatile markets
- Or consider this market is too risky

### Scenario 8.21: Bot Makes Money Fast!

**What you see:**
```
EXIT via Take profit: P&L: $+0.03
EXIT via Take profit: P&L: $+0.02
EXIT via Take profit: P&L: $+0.04
Total P&L: $+0.25 | Win Rate: 5/6
```

**What's happening:** Bot is crushing it!

**What to do:**
- Enjoy!
- But **don't** increase trade size too fast
- Market conditions can change quickly
- Stay disciplined

---

## Part 9: Emergency Procedures

### Emergency 9.1: Bot Is Losing Money Fast

**Scenario:** P&L is dropping rapidly.

**IMMEDIATE ACTION:**
```bash
# Stop the bot
Press Ctrl+C

# Emergency exit - sell everything
python scripts/sell_all_positions.py

# Check your final state
python scripts/check_status.py
```

**Then:**
1. Analyze what went wrong
2. Review your settings
3. Either adjust or stop trading this market

### Emergency 9.2: Order Stuck (Can't Exit Position)

**Scenario:** Bot has open position but can't close it.

**Try in order:**
```bash
# 1. Check current status
python scripts/check_status.py

# 2. Try manual exit (opposite side)
# If you're LONG (bought), use:
python scripts/manual_trade.py --sell --size 1.00

# 3. If still stuck, go to Polymarket.com
# and manually close the position there
```

### Emergency 9.3: Unexpected Large Trade

**Scenario:** Bot makes a $100 trade when you set it for $1.

**IMMEDIATE ACTION:**
```bash
# Stop the bot
Press Ctrl+C

# Check what happened
python scripts/check_status.py

# Check .env file for DEFAULT_TRADE_SIZE_USD
```

**What probably happened:** Typo in `.env` file.

### Emergency 9.4: Wallet Compromised

**Scenario:** You suspect someone stole your private key.

**IMMEDIATE ACTION:**
1. **Move your funds** to a new wallet
2. **Revoke Polymarket approvals** in your old wallet
3. **Generate a new private key**
4. **Update .env** with new key
5. **Do NOT reuse the compromised key**

### Emergency 9.5: Internet Goes Down

**Scenario:** Bot running, internet disconnects.

**What happens:**
- Bot will detect connection loss
- Try to reconnect automatically
- If position was open, it's still on Polymarket

**When internet returns:**
- Bot reconnects
- Manages any open positions
- No manual intervention needed usually

**If bot can't reconnect:**
1. Check internet is working
2. Restart bot when connection is back
3. Check positions on Polymarket website

### Emergency 9.6: Polymarket API Down

**Scenario:** Bot shows API errors.

**What you might see:**
```
ERROR - PolyApiException[status_code=503]
ERROR - Failed to fetch REST price
```

**What's happening:** Polymarket's servers are down.

**What to do:**
- Wait for Polymarket to fix
- Check https://status.polymarket.com/
- Bot will reconnect when they're back

**Don't panic:**
- Your open positions are safe on Polymarket
- You can manually manage them on the website if needed

---

## Part 10: Post-Trading Analysis

### Step 10.1: Check Your Performance

**View your saved state:**
```bash
python scripts/check_status.py
```

**What you'll see:**
```
=== CURRENT POSITION ===
Open Position: None

=== PERFORMANCE ===
Realized P&L: $0.26
Total Trades: 11
Winning Trades: 6
Win Rate: 54.5%
```

### Step 10.2: Understanding Your Results

**Win Rate below 40%:**
- Strategy might not suit this market
- Consider:
  - Different market
  - Higher `SPIKE_THRESHOLD_PCT`
  - Longer `MAX_HOLD_SECONDS`

**Win Rate 40-60%:**
- Normal for this strategy
- Can be profitable with good risk management

**Win Rate above 60%:**
- Great! Market suits the strategy
- Consider:
  - Slightly increasing `DEFAULT_TRADE_SIZE_USD`
  - Keep doing what you're doing

### Step 10.3: When to Adjust Settings

**Change market when:**
- Win rate < 40% after 20+ trades
- No spikes for 1+ hour
- Market resolved/finished

**Adjust threshold when:**
- Too many false signals → Increase `SPIKE_THRESHOLD_PCT`
- Missing good trades → Decrease `SPIKE_THRESHOLD_PCT`

**Adjust TP/SL when:**
- Taking profit too early → Increase `TAKE_PROFIT_PCT`
- Letting losses run → Decrease `STOP_LOSS_PCT`
- Holding too long → Decrease `MAX_HOLD_SECONDS`

---

## Part 11: Quick Reference Card

### Common Commands

```bash
# Start bot
python start_bot.py

# Check setup
python scripts/check_setup.py

# Quick pre-flight check
python scripts/check_setup.py --pre-flight

# Check current position
python scripts/check_status.py

# Manual buy
python scripts/manual_trade.py --buy --size 1.05

# Manual sell
python scripts/manual_trade.py --sell --size 1.05

# Emergency exit (sell all)
python scripts/sell_all_positions.py

# List active sports events
python scripts/poly_tools.py list-events

# Find liquid markets
python scripts/poly_tools.py find-liquid

# Check specific market
python scripts/poly_tools.py check-market slug-here

# Scan market liquidity
python scripts/poly_tools.py scan-liquidity slug-here
```

### Stop the Bot
- Press `Ctrl+C`

### Edit Configuration
- Windows: `notepad .env`
- Mac: `nano .env`

### Restart After Changing .env
```bash
# Stop bot (Ctrl+C)
# Make changes to .env
# Restart
python start_bot.py
```

---

## Part 12: Decision Trees

### What To Do When...

**"Bot isn't trading"**
```
Has it been 5+ minutes?
├─ Yes → Check SPIKE_THRESHOLD_PCT (lower it)
├─ No → Wait longer
└─ Still nothing after 30 min → Change market
```

**"Bot keeps losing"**
```
After 10+ trades, check Win Rate:
├─ < 40% → Change market or increase threshold
├─ 40-60% → Normal, keep going
└─ > 60% → Great!
```

**"Got error message"**
```
Read the error:
├─ "No orderbook exists" → Market is dead, change it
├─ "Insufficient balance" → Add more USDC.e
├─ "invalid signature" → Check PRIVATE_KEY and SIGNATURE_TYPE
└─ Other error → Run check_setup.py
```

**"Price seems wrong"**
```
Is it 0.01 or 0.99?
├─ Yes → Market resolved/illiquid
│   └─ Set USE_GAMMA_PRIMARY=true
└─ No → Probably correct
```

**"Want to stop trading"**
```
How quickly do you need to stop?
├─ Immediately → Press Ctrl+C
├─ After current position → Let it finish
└─ Emergency → python scripts/sell_all_positions.py
```

---

## Part 13: Best Practices

### DO's ✅

- ✅ Start with `DRY_RUN=true`
- ✅ Use small amounts ($1-5)
- ✅ Test on one market first
- ✅ Monitor the bot initially
- ✅ Keep records of your trades
- ✅ Understand the risks
- ✅ Have a separate trading wallet
- ✅ Keep some MATIC for gas
- ✅ Read the logs
- ✅ Stop if you don't understand something

### DON'Ts ❌

- ❌ Start with real money
- ❌ Trade more than you can lose
- ❌ Ignore error messages
- ❌ Leave bot unattended for days
- ❌ Share your private key
- ❌ Trade on illiquid markets
- ❌ Expect to always win
- ❌ Increase size too fast
- ❌ Run on markets you don't understand
- ❌ Be greedy

---

## Part 14: Glossary

| Term | Meaning |
|------|---------|
| **Ask** | Lowest price sellers are accepting |
| **Bid** | Highest price buyers are offering |
| **CLOB** | Central Limit Order Book (Polymarket's exchange) |
| **Dry Run** | Practice mode with fake money |
| **Fade** | Bet against (opposite of the trend) |
| **Illiquid** | Not much trading activity |
| **Limit Order** | Order to buy/sell at a specific price |
| **Market Order** | Order to buy/sell immediately at current price |
| **P&L** | Profit and Loss |
| **Private Key** | Secret password for your wallet |
| **Seed Phrase** | 12-24 words to recover wallet (keep secret!) |
| **Signature** | Cryptographic proof of ownership |
| **Slippage** | Price difference between expected and actual |
| **Spread** | Gap between bid and ask prices |
| **Spike** | Sudden price movement |
| **Token ID** | Unique identifier for a market |
| **USDC.e** | Dollar-pegged cryptocurrency on Polygon |
| **Volatility** | How much price moves around |

---

## Part 15: Getting Help

### Step 1: Check the Logs

The bot writes detailed logs. Read them to understand what happened.

### Step 2: Run Diagnostics

```bash
# Check setup
python scripts/check_setup.py

# Check status
python scripts/check_status.py

# Check orderbook
python scripts/check_orderbook.py
```

### Step 3: Review This Guide

Find the scenario that matches your situation and follow the steps.

### Step 4: Read the Full Documentation

```bash
# Main README has more technical details
README.md
```

---

## Final Checklist Before Real Trading

Before setting `DRY_RUN=false`, make sure you:

- [ ] Tested with `DRY_RUN=true` for at least 1 hour
- [ ] Understand all the settings
- [ ] Have funds you can afford to lose
- [ ] Know how to stop the bot (Ctrl+C)
- [ ] Know emergency exit command
- [ ] Have read the risks section
- [ ] Are using a separate trading wallet
- [ ] Have verified your setup
- [ ] Are starting with small amounts ($1-5)
- [ ] Will monitor the bot initially

---

## You're Ready!

If you've read through this guide and followed the steps, you're ready to run your PolyAgent trading bot.

**Remember:**
- Start small
- Stay safe
- Ask for help if needed
- And never trade more than you can afford to lose!

**Good luck and happy trading!** 🚀
