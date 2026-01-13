# PolyAgent Beginner's Guide (NOOB GUIDE)

<div align="center">

# 🎯 Welcome to PolyAgent!

**Your friendly guide to automated Polymarket trading**

*No coding experience required!*

</div>

---

## 📋 Table of Contents

- [What is PolyAgent?](#-what-is-polyagent)
- [What You Need Before Starting](#-what-you-need-before-starting)
- [Installation (Step by Step)](#-installation-step-by-step)
- [Creating Your First Bot](#-creating-your-first-bot)
- [Understanding the Dashboard](#-understanding-the-dashboard)
- [Your First Test Run](#-your-first-test-run)
- [Going Live (Real Trading)](#-going-live-real-trading)
- [Common Scenarios & Solutions](#-common-scenarios--solutions)
- [Frequently Asked Questions](#-frequently-asked-questions)
- [Glossary](#-glossary)
- [Safety Checklist](#-safety-checklist)

---

## 🤔 What is PolyAgent?

PolyAgent is an **automated trading bot** for [Polymarket](https://polymarket.com), a prediction market platform. Think of it as a robot assistant that watches market prices 24/7 and makes trades on your behalf based on rules you define.

### What Can It Do?

| Feature | Description |
|---------|-------------|
| 🔍 **Watch Prices** | Monitors market prices in real-time |
| 📊 **Detect Spikes** | Notices sudden price movements |
| 🎯 **Trade Automatically** | Buys low, sells high based on your rules |
| 💰 **Track Profits** | Shows your wins, losses, and total P&L |
| 🛡️ **Manage Risk** | Automatically exits trades to limit losses |
| 🖥️ **Beautiful Dashboard** | Shows everything in an easy-to-use web interface |

### How Does It Work?

```
1. You pick a market to trade (e.g., "Will Bitcoin reach $100k?")
2. You set your rules (e.g., "Buy if price drops 5% suddenly")
3. The bot watches the market 24/7
4. When conditions match, it trades automatically
5. You sit back and monitor via the dashboard
```

---

## 📦 What You Need Before Starting

### 1. Computer Requirements

- **Operating System**: Windows 10/11, macOS, or Linux
- **Python**: Version 3.10 or newer ([Download here](https://www.python.org/downloads/))
- **Node.js**: Version 18 or newer ([Download here](https://nodejs.org/))
- **Web Browser**: Chrome, Firefox, or Edge (latest version)

### 2. Wallet & Funds

You'll need a **crypto wallet** on the Polygon network with:

| Item | Minimum | Recommended |
|------|---------|-------------|
| **USDC.e** | $10 | $50-100 |
| **MATIC** | 0.5 | 1-2 |

> 💡 **Why MATIC?** It's used to pay transaction fees (gas) on Polygon.

### 3. Your Private Key

⚠️ **IMPORTANT**: You need your wallet's **private key** (not seed phrase).

**How to get it:**
- **MetaMask**: Settings → Security & Privacy → Reveal Private Key
- **Other Wallets**: Check your wallet's export/backup options

> 🔒 **Security Tip**: Create a NEW wallet just for trading. Never use your main wallet!

---

## 💻 Installation (Step by Step)

### Step 1: Download Python

1. Go to [python.org/downloads](https://www.python.org/downloads/)
2. Click the big yellow "Download Python" button
3. Run the installer
4. **IMPORTANT**: Check the box that says "Add Python to PATH"
5. Click "Install Now"

**Verify installation:**
```bash
# Open Command Prompt (Windows) or Terminal (Mac/Linux)
python --version
# Should show: Python 3.10.x or higher
```

### Step 2: Download Node.js

1. Go to [nodejs.org](https://nodejs.org/)
2. Download the "LTS" version (left button)
3. Run the installer, accept all defaults

**Verify installation:**
```bash
node --version
# Should show: v18.x.x or higher

npm --version
# Should show: 9.x.x or higher
```

### Step 3: Download PolyAgent

**Option A: If you have the ZIP file:**
1. Extract the ZIP file to a location like `C:\Users\YourName\PolyAgent`

**Option B: Using Git (if you have it):**
```bash
git clone https://github.com/your-repo/PolyAgent.git
cd PolyAgent
```

### Step 4: Install Python Dependencies

```bash
# Open Command Prompt/Terminal
# Navigate to the PolyAgent folder
cd C:\Users\YourName\PolyAgent

# Install dependencies
pip install -r requirements.txt
```

**Expected output:**
```
Successfully installed py-clob-client-0.18.0 fastapi-0.115.0 ...
```

> ⚠️ **If you see errors**: Try `pip3 install -r requirements.txt` instead

### Step 5: Install Frontend Dependencies

```bash
# Navigate to the frontend folder
cd frontend

# Install dependencies
npm install
```

**Expected output:**
```
added 350 packages in 45s
```

### Step 6: Verify Installation

```bash
# Go back to main folder
cd ..

# Run setup check
python scripts/check_setup.py
```

**Good output:**
```
✅ Python version OK
✅ Required packages installed
✅ Frontend ready
⚠️ No bots configured yet (this is expected!)
```

---

## 🤖 Creating Your First Bot

### Step 1: Start the Backend Server

Open a **new terminal/command prompt** and run:

```bash
cd C:\Users\YourName\PolyAgent
python -m src.api_server
```

**You should see:**
```
INFO:     Uvicorn running on http://0.0.0.0:8000
INFO:     Started server process
INFO:     Application startup complete.
```

> ⚠️ **Keep this terminal open!** This needs to run while you use the bot.

### Step 2: Start the Frontend Dashboard

Open a **second terminal/command prompt** and run:

```bash
cd C:\Users\YourName\PolyAgent\frontend
npm run dev
```

**You should see:**
```
▲ Next.js 16.0.10
- Local: http://localhost:3000
```

### Step 3: Open the Dashboard

1. Open your web browser
2. Go to: **http://localhost:3000**
3. You should see the PolyAgent dashboard!

### Step 4: Create Your First Bot

1. Click the **"+ Create Bot"** button in the Bot Manager panel

2. Fill in the form:

   | Field | What to Enter |
   |-------|---------------|
   | **Bot Name** | My First Bot |
   | **Description** | Testing the waters |
   | **Private Key** | Your 64-character key (without 0x) |
   | **Signature Type** | EOA (most common) |
   | **Market Slug** | Copy from Polymarket URL (see below) |
   | **Trading Profile** | Normal (recommended for beginners) |
   | **Dry Run** | ✅ ON (very important for testing!) |

3. Click **"Create Bot"**

### Step 5: Find a Market Slug

1. Go to [polymarket.com](https://polymarket.com)
2. Find a market you want to trade
3. Look at the URL, for example:
   ```
   https://polymarket.com/event/will-trump-win-2024
   ```
4. The **slug** is: `will-trump-win-2024`

> 💡 **Tip**: Start with active, high-volume markets for better liquidity.

---

## 📊 Understanding the Dashboard

Here's what each part of the dashboard shows:

```
┌─────────────────────────────────────────────────────────────────────┐
│  🟢 PolyAgent Dashboard                        [Settings] [🌙]     │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│  SUMMARY BAR                                                         │
│  ┌────────────────┬────────────────┬────────────────┐               │
│  │ Total P&L      │ Active Bots    │ Today's Trades │               │
│  │ +$12.50        │ 2              │ 15             │               │
│  └────────────────┴────────────────┴────────────────┘               │
│                                                                      │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐   │
│  │ BOT MANAGER          │  │ PRICE CHART                        │   │
│  │                      │  │                                    │   │
│  │ [+ Create Bot]       │  │    0.60 ─────── SELL TARGET ───── │   │
│  │                      │  │         ╱╲                         │   │
│  │ 🟢 My First Bot      │  │    0.55 ╱  ╲    Current            │   │
│  │    Running           │  │        ╱    ╲                      │   │
│  │    +$5.20            │  │    0.50 ──────── ENTRY ─────────── │   │
│  │                      │  │                                    │   │
│  │ 🔴 Test Bot          │  │    0.45 ─────── BUY TARGET ──────  │   │
│  │    Stopped           │  │                                    │   │
│  │                      │  │    10am   11am   12pm   1pm        │   │
│  └──────────────────────┘  └────────────────────────────────────┘   │
│                                                                      │
│  ┌──────────────────────┐  ┌────────────────────────────────────┐   │
│  │ CURRENT POSITION     │  │ ACTIVITY FEED                      │   │
│  │                      │  │                                    │   │
│  │ Side: LONG (BUY)     │  │ 🔵 10:15 - Spike detected -3.5%    │   │
│  │ Entry: $0.50         │  │ 🟢 10:15 - Order: BUY $5.00        │   │
│  │ Current: $0.52       │  │ 🟢 10:15 - Filled @ $0.495         │   │
│  │ P&L: +$0.10 (+4%)    │  │ 💰 10:45 - P&L: +$0.23 (+4.6%)     │   │
│  │                      │  │ 🔵 11:00 - Target set: SELL $0.52  │   │
│  │ TP: 5% ████████░░    │  │                                    │   │
│  │ SL: -3% ░░░░░░░░░░   │  │ [Spikes] [Orders] [P&L] [All]      │   │
│  └──────────────────────┘  └────────────────────────────────────┘   │
│                                                                      │
└─────────────────────────────────────────────────────────────────────┘
```

### Panel Descriptions

| Panel | What It Shows |
|-------|---------------|
| **Summary Bar** | Quick overview of all your bots' performance |
| **Bot Manager** | List of your bots, create/start/stop controls |
| **Price Chart** | Live price with your targets and entry points |
| **Current Position** | Details of your active trade (if any) |
| **Activity Feed** | Real-time log of everything happening |
| **Settings** | Global settings, emergency killswitch |

### Status Icons

| Icon | Meaning |
|------|---------|
| 🟢 | Bot is running |
| 🔴 | Bot is stopped |
| 🟡 | Bot is paused |
| ⚠️ | Bot has an error |

---

## 🧪 Your First Test Run

### Step 1: Make Sure Dry Run is ON

Before doing anything else, verify your bot has **Dry Run: ON**.

This means the bot will:
- ✅ Watch prices in real-time
- ✅ Detect spikes
- ✅ Log what it would do
- ❌ NOT actually place trades
- ❌ NOT use your real money

### Step 2: Start the Bot

1. Find your bot in the Bot Manager
2. Click the **Play (▶)** button
3. Status should change from 🔴 to 🟢

### Step 3: Watch the Activity Feed

You should start seeing:
```
🔵 Price update: 0.523
🔵 Price update: 0.521
🔵 Price update: 0.520
⚠️ Spike detected: -2.1% over 10 minutes
🟡 [DRY RUN] Would BUY $5.00 @ 0.520
```

### Step 4: Understand What's Happening

With the default "Normal" profile, the bot is looking for:
- Price drops of **3% or more** (to BUY)
- Price rises of **3% or more** (to SELL/FADE)

When it sees a qualifying spike:
1. Logs the detection
2. Simulates placing an order
3. Sets a target for exit

### Step 5: Run for at Least 1 Hour

Let the bot run in dry mode for at least an hour to:
- See how often spikes occur
- Understand the trading patterns
- Verify everything works correctly

---

## 💰 Going Live (Real Trading)

> ⚠️ **WARNING**: Real trading uses real money. Only proceed when you're confident!

### Pre-Flight Checklist

Before going live, make sure you:

- [ ] Tested in dry run mode for at least 1 hour
- [ ] Understand all the settings
- [ ] Have funded your trading wallet
- [ ] Started with small amounts ($5-10)
- [ ] Know how to stop the bot quickly
- [ ] Accept you might lose money

### Step 1: Approve USDC.e for Trading

The bot needs permission to use your USDC.e for trades.

```bash
# Run this command (make sure API server is stopped first)
python scripts/approve_usdc.py
```

Follow the prompts to approve USDC.e spending.

### Step 2: Edit Your Bot Configuration

1. Click on your bot in the Bot Manager
2. Click the **Edit (✏️)** button
3. Change these settings:

   | Setting | Change To |
   |---------|-----------|
   | **Dry Run** | OFF |
   | **Trade Size** | $1 (start small!) |
   | **Profile** | Ultra-Conservative (safest) |

4. Click **Save**

### Step 3: Start Trading

1. Click the **Play (▶)** button
2. Watch the Activity Feed closely
3. Real trades will now execute!

### Step 4: Monitor Continuously

For your first real session:
- Stay at your computer
- Watch every trade
- Be ready to stop if something seems wrong

---

## 🔧 Common Scenarios & Solutions

### Scenario 1: "No Balance/Allowance" Error

**What it means**: The bot can't trade because USDC.e isn't approved.

**Solution**:
```bash
python scripts/approve_usdc.py
```

### Scenario 2: Bot Says "No Price Available"

**What it means**: Can't get price data from Polymarket.

**Solutions**:
1. Check if the market is still active on polymarket.com
2. Try a different market
3. Check your internet connection
4. Restart the backend server

### Scenario 3: "Token Not Found" Error

**What it means**: The market slug is incorrect.

**Solution**:
1. Go to the market on polymarket.com
2. Copy the exact slug from the URL
3. Update your bot configuration

### Scenario 4: Orders Keep Failing

**What it means**: Market conditions aren't suitable.

**Possible causes**:
- Spread too wide (market is illiquid)
- Price moved while ordering
- Not enough liquidity

**Solutions**:
1. Try a more active market
2. Increase your slippage tolerance
3. Use smaller trade sizes

### Scenario 5: Bot Made a Bad Trade

**What it means**: The strategy didn't work as expected.

**What to do**:
1. Don't panic!
2. Check if stop loss will trigger
3. If needed, manually close: Click **"Close Position"** button
4. Review what happened in the Activity Feed

### Scenario 6: Need to Stop Everything NOW

**Emergency stop options**:

1. **Dashboard Killswitch**: Settings → Click "Emergency Stop All"
2. **Stop Individual Bot**: Click the Stop (⏹) button on the bot
3. **Terminal**: Press `Ctrl+C` in the backend terminal
4. **Script**: Run `python scripts/sell_all_positions.py`

---

## ❓ Frequently Asked Questions

### General Questions

**Q: Is this legal?**
A: Trading on Polymarket is legal in most jurisdictions. Check your local laws.

**Q: How much money do I need?**
A: Minimum $10-20, but $50-100 recommended to start.

**Q: Can I run multiple bots?**
A: Yes! Each bot can trade a different market with different settings.

**Q: Does it work 24/7?**
A: Yes, as long as your computer (and the servers) are running.

### Trading Questions

**Q: What's a good market to start with?**
A: Choose markets with:
- High trading volume (check the 24h volume on Polymarket)
- Active orderbook (small spread between buy/sell)
- Topics you understand

**Q: How do spikes work?**
A: The bot compares current price to prices from 10/30/60 minutes ago. If the change exceeds your threshold (e.g., 3%), it's a "spike."

**Q: What's the "Train of Trade" strategy?**
A: It's a cycle: Buy at target → Hold → Sell at target → Repeat. More predictable than just trading spikes.

**Q: Why isn't the bot trading?**
A: Common reasons:
- No spikes occurred (price is stable)
- Dry run mode is on
- Position cooldown active
- Not enough balance

### Technical Questions

**Q: What are the terminals for?**
A: You need two terminals running:
1. Backend (Python): Handles trading logic
2. Frontend (Next.js): The dashboard you see

**Q: Do I need to keep my computer on?**
A: Yes. The bot only runs when the servers are running.

**Q: What happens if I close the terminal?**
A: The bot stops. Open positions remain open until you restart.

**Q: Is my private key safe?**
A: Yes, it's encrypted with machine-specific encryption. Never share the `data/bots/` folder.

---

## 📖 Glossary

| Term | Definition |
|------|------------|
| **API** | Application Programming Interface - how programs talk to each other |
| **Ask** | The lowest price someone is willing to sell at |
| **Bid** | The highest price someone is willing to buy at |
| **CLOB** | Central Limit Order Book - where orders are matched |
| **Cooldown** | Waiting period between trades |
| **Dry Run** | Test mode that simulates trades without using real money |
| **EOA** | Externally Owned Account - a regular wallet you control |
| **Fernet** | Encryption method used to protect your private key |
| **Gas** | Transaction fees paid in MATIC |
| **Limit Order** | Order to buy/sell at a specific price |
| **Liquidity** | How easily you can trade without moving the price |
| **Market Order** | Order to buy/sell immediately at best available price |
| **MATIC** | The gas token for Polygon network |
| **P&L** | Profit and Loss |
| **Polygon** | The blockchain network Polymarket uses |
| **Private Key** | Secret code that controls your wallet (never share!) |
| **Proxy** | A smart contract wallet (like Gnosis Safe) |
| **Seed Phrase** | 12-24 words to recover wallet (never share!) |
| **Slippage** | Difference between expected and actual trade price |
| **Spike** | Sudden price movement |
| **Spread** | Difference between bid and ask prices |
| **Stop Loss** | Automatic exit when losing too much |
| **Take Profit** | Automatic exit when gaining enough |
| **Token ID** | Unique identifier for a market outcome |
| **USDC.e** | US Dollar stablecoin on Polygon |
| **WebSocket** | Technology for real-time communication |

---

## ✅ Safety Checklist

### Before You Start

- [ ] Created a separate wallet just for trading
- [ ] Only funded with money I can afford to lose
- [ ] Wrote down my private key in a safe place
- [ ] Understand the basics of Polymarket
- [ ] Read through this entire guide

### Before Going Live

- [ ] Tested with dry run for at least 1 hour
- [ ] Approved USDC.e for trading
- [ ] Started with the smallest trade size ($1-5)
- [ ] Using Ultra-Conservative or Normal profile
- [ ] Know how to use the emergency stop

### During Live Trading

- [ ] Monitoring the dashboard regularly
- [ ] Checking P&L at least once per hour
- [ ] Ready to stop if something seems wrong
- [ ] Not risking more than I can lose

### Regular Maintenance

- [ ] Review trades daily
- [ ] Check for software updates
- [ ] Backup important settings
- [ ] Review and adjust strategy as needed

---

## 🆘 Getting Help

### Step 1: Check This Guide

Most common issues are covered in:
- [Common Scenarios & Solutions](#-common-scenarios--solutions)
- [Frequently Asked Questions](#-frequently-asked-questions)

### Step 2: Check the Logs

The backend terminal shows detailed logs. Look for:
```
ERROR: Something went wrong
WARNING: Something might be wrong
INFO: Normal operation
```

### Step 3: Run Diagnostic Scripts

```bash
# Check overall setup
python scripts/check_setup.py

# Check wallet status
python scripts/check_status.py

# Check market orderbook
python scripts/check_orderbook.py
```

### Step 4: Read Technical Documentation

For more details:
- [README.md](../README.md) - Main documentation
- [ARCHITECTURE.md](ARCHITECTURE.md) - Technical deep-dive

---

## 🎯 Quick Reference Card

### Starting the Bot

```bash
# Terminal 1 - Backend
cd PolyAgent
python -m src.api_server

# Terminal 2 - Frontend
cd PolyAgent/frontend
npm run dev

# Open browser to http://localhost:3000
```

### Emergency Commands

```bash
# Stop all trading
Ctrl+C (in backend terminal)

# Sell all positions immediately
python scripts/sell_all_positions.py
```

### Important Folders

```
PolyAgent/
├── data/bots/       # Your bot configurations (encrypted)
├── data/settings.json  # Global settings
├── scripts/         # Helpful utility scripts
├── frontend/        # Dashboard files
└── src/             # Bot engine files
```

---

## 🎉 You're Ready!

Congratulations on making it through the guide! Here's a summary of what to do next:

1. **Start Small**: Begin with dry run mode
2. **Learn the Dashboard**: Spend time understanding each panel
3. **Test Thoroughly**: Run dry mode for hours before going live
4. **Go Slow**: Start with $1 trades and work up gradually
5. **Stay Safe**: Never risk more than you can afford to lose

---

<div align="center">

**Good luck and happy trading! 🚀**

*Remember: Start small, stay safe, and have fun!*

---

*Need help? Check the [troubleshooting section](#-common-scenarios--solutions) first!*

</div>
