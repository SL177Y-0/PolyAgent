#!/usr/bin/env python3
"""PolyAgent CLI - Unified command-line interface for PolyAgent.

This script provides a single entry point for all PolyAgent operations:
  - setup     : Interactive configuration wizard
  - status    : Check current position and market status
  - start     : Start the trading bot
  - market    : Get market info from URL/slug
  - find      : Find tradeable markets
  - trade     : Execute manual trades
  - close     : Close all open positions
  - reset     : Reset position state

Usage:
    python poly.py <command> [options]

Examples:
    python poly.py setup
    python poly.py status
    python poly.py start
    python poly.py market https://polymarket.com/event/some-slug
    python poly.py find --volatile
    python poly.py trade --buy --size 1.0
    python poly.py close
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

PROJECT_ROOT = Path(__file__).parent
if (PROJECT_ROOT / "scripts").exists():
    # Running from project root
    SCRIPTS_DIR = PROJECT_ROOT / "scripts"
else:
    # Running from scripts folder
    PROJECT_ROOT = PROJECT_ROOT.parent
    SCRIPTS_DIR = PROJECT_ROOT / "scripts"

sys.path.insert(0, str(PROJECT_ROOT))


def run_script(script_name: str, *args) -> int:
    """Run a script from the scripts folder."""
    script_path = SCRIPTS_DIR / script_name
    if not script_path.exists():
        print(f"[X] Script not found: {script_path}")
        return 1
    
    cmd = [sys.executable, str(script_path)] + list(args)
    return subprocess.call(cmd, cwd=str(PROJECT_ROOT))


def run_python(code: str) -> int:
    """Run inline Python code."""
    return subprocess.call([sys.executable, "-c", code], cwd=str(PROJECT_ROOT))


def cmd_setup(args):
    """Run the setup wizard."""
    return run_script("easy_setup.py")


def cmd_status(args):
    """Check current status."""
    return run_script("check_status.py")


def cmd_start(args):
    """Start the trading bot."""
    if args.quick:
        return run_script("quick_start.py")
    else:
        bot_path = PROJECT_ROOT / "start_bot.py"
        return subprocess.call([sys.executable, str(bot_path)], cwd=str(PROJECT_ROOT))


def cmd_market(args):
    """Get market information."""
    if args.url:
        return run_script("get_market_from_url.py", args.url)
    else:
        print("Usage: poly.py market <url-or-slug>")
        print("Example: poly.py market https://polymarket.com/event/some-market")
        return 1


def cmd_find(args):
    """Find tradeable markets."""
    if args.volatile:
        return run_script("find_best_market.py")
    else:
        return run_script("find_tradeable_market.py")


def cmd_trade(args):
    """Execute a manual trade."""
    trade_args = []
    if args.buy:
        trade_args.append("--buy")
    elif args.sell:
        trade_args.append("--sell")
    else:
        print("Must specify --buy or --sell")
        return 1
    
    if args.size:
        trade_args.extend(["--size", str(args.size)])
    
    return run_script("manual_trade.py", *trade_args)


def cmd_close(args):
    """Close all open positions."""
    return run_script("sell_all_positions.py")


def cmd_reset(args):
    """Reset position state."""
    position_file = PROJECT_ROOT / "data" / "position.json"
    
    if not position_file.exists():
        print("[!] No position file found.")
        return 0
    
    if not args.force:
        # Show current state
        try:
            data = json.loads(position_file.read_text())
            if data.get("open_position"):
                print("[!] WARNING: You have an open position!")
                print(f"    Side: {data['open_position'].get('side')}")
                print(f"    Amount: ${data['open_position'].get('amount_usd')}")
                print("\nThis will NOT close your position on Polymarket.")
                print("It only resets local tracking state.")
                
                confirm = input("\nType 'RESET' to confirm: ")
                if confirm != "RESET":
                    print("Cancelled.")
                    return 1
        except Exception:
            pass
    
    # Backup and reset
    backup_file = position_file.with_suffix(".json.bak")
    position_file.rename(backup_file)
    
    # Create fresh state
    fresh_state = {
        "open_position": None,
        "realized_pnl": 0.0,
        "total_trades": 0,
        "winning_trades": 0,
        "initial_inventory_acquired": False,
        "token_id": None
    }
    position_file.write_text(json.dumps(fresh_state, indent=2))
    
    print(f"[+] Position state reset. Backup saved to {backup_file}")
    return 0


def cmd_help(args):
    """Show help."""
    print(__doc__)
    return 0


def main():
    parser = argparse.ArgumentParser(
        description="PolyAgent CLI - Unified command-line interface",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Commands:
  setup     Interactive configuration wizard
  status    Check current position and market status
  start     Start the trading bot
  market    Get market info from URL/slug
  find      Find tradeable markets
  trade     Execute manual trades
  close     Close all open positions
  reset     Reset position state

Examples:
  python poly.py setup
  python poly.py status
  python poly.py start --quick
  python poly.py market some-market-slug
  python poly.py find --volatile
  python poly.py trade --buy --size 1.0
"""
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Command to run")
    
    # setup
    subparsers.add_parser("setup", help="Run configuration wizard")
    
    # status
    subparsers.add_parser("status", help="Check current status")
    
    # start
    start_parser = subparsers.add_parser("start", help="Start the bot")
    start_parser.add_argument("--quick", action="store_true", help="Use quick start with prompts")
    
    # market
    market_parser = subparsers.add_parser("market", help="Get market info")
    market_parser.add_argument("url", nargs="?", help="Polymarket URL or slug")
    
    # find
    find_parser = subparsers.add_parser("find", help="Find markets")
    find_parser.add_argument("--volatile", action="store_true", help="Find volatile markets")
    
    # trade
    trade_parser = subparsers.add_parser("trade", help="Manual trade")
    trade_parser.add_argument("--buy", action="store_true", help="Buy/Long")
    trade_parser.add_argument("--sell", action="store_true", help="Sell/Short")
    trade_parser.add_argument("--size", type=float, help="Trade size in USD")
    
    # close
    subparsers.add_parser("close", help="Close all positions")
    
    # reset
    reset_parser = subparsers.add_parser("reset", help="Reset position state")
    reset_parser.add_argument("--force", action="store_true", help="Skip confirmation")
    
    args = parser.parse_args()
    
    if not args.command:
        parser.print_help()
        return 0
    
    commands = {
        "setup": cmd_setup,
        "status": cmd_status,
        "start": cmd_start,
        "market": cmd_market,
        "find": cmd_find,
        "trade": cmd_trade,
        "close": cmd_close,
        "reset": cmd_reset,
    }
    
    if args.command in commands:
        return commands[args.command](args)
    else:
        parser.print_help()
        return 1


if __name__ == "__main__":
    sys.exit(main())
