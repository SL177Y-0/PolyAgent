#!/usr/bin/env python3
"""Check current status: resolved token, mid price, and P&L from position.json.

Shows the current open position status with unrealized P&L calculation.
"""
from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.config import Config
from src.clob_client import Client

POSITION_FILE = Path(__file__).parent.parent / "data" / "position.json"


def main():
    print("=" * 60)
    print("PolyAgent Status Check")
    print("=" * 60)
    
    # Load config
    try:
        cfg = Config.from_env()
    except Exception as e:
        print(f"\n[X] Config error: {e}")
        print("Run: python scripts/easy_setup.py to configure")
        return
    
    logging.basicConfig(level=logging.WARNING)  # Suppress info logs
    
    # Check position file first (doesn't need API)
    print("\n[Position Status]")
    print("-" * 40)
    
    position_data = None
    if POSITION_FILE.exists():
        try:
            position_data = json.loads(POSITION_FILE.read_text())
            pos = position_data.get("open_position")
            
            if pos:
                print(f"  Side:         {pos.get('side', 'N/A')}")
                print(f"  Entry Price:  ${pos.get('entry_price', 0):.4f}")
                print(f"  Amount:       ${pos.get('amount_usd', 0):.2f}")
                print(f"  Shares:       {pos.get('expected_shares', 0):.4f}")
                print(f"  Entry Time:   {pos.get('entry_time', 'N/A')}")
                order_id = pos.get('entry_order_id', 'N/A')
                if order_id and len(order_id) > 20:
                    print(f"  Order ID:     {order_id[:20]}...")
                else:
                    print(f"  Order ID:     {order_id}")
            else:
                print("  No open position")
            
            print(f"\n  Realized P&L: ${position_data.get('realized_pnl', 0):.4f}")
            print(f"  Total Trades: {position_data.get('total_trades', 0)}")
            print(f"  Winning:      {position_data.get('winning_trades', 0)}")
            inv_status = "[Y] Acquired" if position_data.get('initial_inventory_acquired') else "[N] Not acquired"
            print(f"  Inventory:    {inv_status}")
            
        except Exception as e:
            print(f"  Error reading position file: {e}")
    else:
        print("  No position file found")
    
    # Get live market data
    print("\n[Market Status]")
    print("-" * 40)
    
    try:
        client = Client(cfg)
        token = client.resolve_token_id()
        mid = client.get_mid_price(token)
        
        print(f"  Market:       {cfg.market_slug or 'N/A'}")
        print(f"  Token ID:     {token[:30]}...")
        print(f"  Mid Price:    ${mid:.4f}")
        
        # Calculate unrealized P&L if position exists
        if position_data and position_data.get("open_position"):
            pos = position_data["open_position"]
            entry = pos.get("entry_price", 0)
            side = pos.get("side", "").upper()
            amount = pos.get("amount_usd", 0)
            
            if side and entry > 0:
                if side == "BUY":
                    pnl_pct = (mid - entry) / entry * 100.0
                    pnl_usd = amount * pnl_pct / 100
                else:
                    pnl_pct = (entry - mid) / entry * 100.0
                    pnl_usd = amount * pnl_pct / 100
                
                status = "[+]" if pnl_pct >= 0 else "[-]"
                print(f"\n  {status} Unrealized P&L: {pnl_pct:+.2f}% (${pnl_usd:+.4f})")
                
                # Show TP/SL distances
                tp_price = entry * (1 + cfg.take_profit_pct / 100) if side == "BUY" else entry * (1 - cfg.take_profit_pct / 100)
                sl_price = entry * (1 - cfg.stop_loss_pct / 100) if side == "BUY" else entry * (1 + cfg.stop_loss_pct / 100)
                
                print(f"\n  Take Profit:  ${tp_price:.4f} ({cfg.take_profit_pct:+.1f}%)")
                print(f"  Stop Loss:    ${sl_price:.4f} ({-cfg.stop_loss_pct:.1f}%)")
                
    except Exception as e:
        print(f"  [X] Error fetching market data: {e}")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
