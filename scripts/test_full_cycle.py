#!/usr/bin/env python3
"""Complete Trade Cycle Test - Demonstrates full BUY → P&L → SELL flow.

This script:
1. Places a BUY order
2. Tracks the open position
3. Monitors P&L for a few seconds
4. Places a SELL order to close
5. Logs realized P&L

Usage:
  python scripts/test_full_cycle.py
"""
from __future__ import annotations

import time
import logging
from datetime import datetime

from src.config import Config
from src.clob_client import Client

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


def main():
    print("\n" + "="*60)
    print("🔄 COMPLETE TRADE CYCLE TEST")
    print("="*60 + "\n")
    
    # Load config
    cfg = Config.from_env()
    client = Client(cfg)
    token_id = client.resolve_token_id()
    
    trade_size = cfg.default_trade_size_usd
    print(f"📊 Token ID: {token_id[:40]}...")
    print(f"💰 Trade Size: ${trade_size:.2f}")
    print(f"🔒 DRY_RUN: {cfg.dry_run}")
    print()
    
    # Step 1: Get initial price
    print("="*60)
    print("STEP 1: GET INITIAL PRICE")
    print("="*60)
    entry_price = client.get_mid_price(token_id)
    print(f"📈 Current mid price: {entry_price:.4f}")
    print()
    
    # Step 2: Place BUY order
    print("="*60)
    print("STEP 2: PLACE BUY ORDER (Entry)")
    print("="*60)
    entry_time = datetime.now()
    print(f"⏳ Placing BUY order for ${trade_size:.2f}...")
    
    try:
        buy_result = client.place_market_order(side="BUY", amount_usd=trade_size, token_id=token_id)
        if buy_result.success:
            print(f"✅ BUY order filled!")
            print(f"   Order ID: {buy_result.response.get('orderID', 'N/A')}")
            print(f"   Entry Price: {entry_price:.4f}")
            print(f"   Entry Time: {entry_time.strftime('%H:%M:%S')}")
        else:
            print(f"❌ BUY order failed: {buy_result.response}")
            return
    except Exception as e:
        print(f"❌ BUY order error: {e}")
        return
    print()
    
    # Step 3: Track P&L for a few seconds
    print("="*60)
    print("STEP 3: TRACK POSITION & P&L")
    print("="*60)
    print("Monitoring position for 10 seconds...\n")
    
    for i in range(5):
        time.sleep(2)
        current_price = client.get_mid_price(token_id)
        
        # Calculate unrealized P&L
        pnl_pct = (current_price - entry_price) / entry_price * 100.0
        pnl_usd = (current_price - entry_price) * (trade_size / entry_price)
        hold_time = (datetime.now() - entry_time).total_seconds()
        
        status = "🟢 PROFIT" if pnl_usd > 0 else ("🔴 LOSS" if pnl_usd < 0 else "⚪ FLAT")
        print(f"   [{i+1}/5] Price: {current_price:.4f} | "
              f"P&L: ${pnl_usd:+.4f} ({pnl_pct:+.2f}%) | "
              f"Hold: {hold_time:.0f}s | {status}")
    
    print()
    
    # Step 4: Place SELL order (close position)
    print("="*60)
    print("STEP 4: PLACE SELL ORDER (Exit)")
    print("="*60)
    exit_price = client.get_mid_price(token_id)
    print(f"⏳ Placing SELL order for ${trade_size:.2f}...")
    
    try:
        sell_result = client.place_market_order(side="SELL", amount_usd=trade_size, token_id=token_id)
        if sell_result.success:
            print(f"✅ SELL order filled!")
            print(f"   Order ID: {sell_result.response.get('orderID', 'N/A')}")
            print(f"   Exit Price: {exit_price:.4f}")
        else:
            print(f"❌ SELL order failed: {sell_result.response}")
    except Exception as e:
        print(f"❌ SELL order error: {e}")
    print()
    
    # Step 5: Calculate realized P&L
    print("="*60)
    print("STEP 5: REALIZED P&L SUMMARY")
    print("="*60)
    
    final_pnl_pct = (exit_price - entry_price) / entry_price * 100.0
    final_pnl_usd = (exit_price - entry_price) * (trade_size / entry_price)
    total_hold = (datetime.now() - entry_time).total_seconds()
    
    print(f"📊 Entry Price:    {entry_price:.4f}")
    print(f"📊 Exit Price:     {exit_price:.4f}")
    print(f"📊 Hold Duration:  {total_hold:.0f} seconds")
    print()
    print(f"💰 Realized P&L:   ${final_pnl_usd:+.4f} ({final_pnl_pct:+.2f}%)")
    
    if final_pnl_usd > 0:
        print("🎉 WINNING TRADE!")
    elif final_pnl_usd < 0:
        print("📉 Losing trade")
    else:
        print("➖ Break-even trade")
    
    print()
    print("="*60)
    print("✅ COMPLETE TRADE CYCLE FINISHED!")
    print("="*60)
    print()


if __name__ == "__main__":
    main()
