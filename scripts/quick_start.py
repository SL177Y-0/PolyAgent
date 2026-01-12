#!/usr/bin/env python3
"""Quick Start - One-click launcher for PolyAgent.

This script:
1. Checks if configuration exists
2. Validates the setup
3. Shows current status
4. Starts the bot

Usage:
    python scripts/quick_start.py
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

ENV_FILE = PROJECT_ROOT / ".env"


def run_script(script_name: str, *args) -> int:
    """Run a script and return exit code."""
    script_path = PROJECT_ROOT / "scripts" / script_name
    if not script_path.exists():
        print(f"[X] Script not found: {script_path}")
        return 1
    
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def main():
    print("\n" + "=" * 60)
    print("  POLYAGENT QUICK START")
    print("=" * 60)
    
    # Step 1: Check if .env exists
    if not ENV_FILE.exists():
        print("\n[!] No .env file found. Running setup wizard...")
        input("\nPress Enter to start setup...")
        run_script("easy_setup.py")
        
        if not ENV_FILE.exists():
            print("\n[X] Setup was not completed. Exiting.")
            return 1
    
    print("\n[1/3] Checking configuration...")
    
    # Step 2: Validate setup
    try:
        from src.config import Config
        cfg = Config.from_env()
        print(f"      Market: {cfg.market_slug or cfg.market_token_id[:30] + '...'}")
        print(f"      Dry Run: {cfg.dry_run}")
        print(f"      Trade Size: ${cfg.default_trade_size_usd}")
    except Exception as e:
        print(f"\n[X] Configuration error: {e}")
        print("\nRun: python scripts/easy_setup.py to fix")
        return 1
    
    print("\n[2/3] Checking current status...")
    
    # Step 3: Show status
    run_script("check_status.py")
    
    print("\n[3/3] Ready to start!")
    print("-" * 60)
    
    if cfg.dry_run:
        print("  Mode: DRY RUN (simulated trading)")
    else:
        print("  Mode: LIVE TRADING (real money!)")
    
    print(f"  Strategy: Spike Sam Fade")
    print(f"  Threshold: {cfg.spike_threshold_pct}%")
    print(f"  TP/SL: +{cfg.take_profit_pct}% / -{cfg.stop_loss_pct}%")
    print("-" * 60)
    
    # Confirm start
    print("\nPress Enter to start the bot, or Ctrl+C to cancel...")
    try:
        input()
    except KeyboardInterrupt:
        print("\n\nCancelled.")
        return 0
    
    print("\n" + "=" * 60)
    print("  STARTING BOT...")
    print("  Press Ctrl+C to stop (will close open positions)")
    print("=" * 60 + "\n")
    
    # Start the bot
    bot_script = PROJECT_ROOT / "start_bot.py"
    return subprocess.call([sys.executable, str(bot_script)], cwd=str(PROJECT_ROOT))


if __name__ == "__main__":
    sys.exit(main())
