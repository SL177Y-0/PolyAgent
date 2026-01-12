#!/usr/bin/env python3
"""Test script for live trading on Illinois vs Iowa O/U market."""
import os
import sys
import time

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Set the O/U 142.5 market token ID
os.environ['MARKET_TOKEN_ID'] = '78543011273612766654431905698923276764474658742257175480081075155982597352339'
os.environ['DEFAULT_TRADE_SIZE_USD'] = '1.0'

from src.config import Config
from src.clob_client import Client

def main():
    cfg = Config.from_env()
    print('=== PolyAgent Real Trading Test ===')
    print(f'Trade size: ${cfg.default_trade_size_usd}')
    print(f'Dry run: {cfg.dry_run}')
    print(f'Token ID: {cfg.market_token_id[:50]}...')
    print()
    
    client = Client(cfg)
    print('=== Orderbook Check ===')
    
    # Get orderbook
    try:
        ob = client._clob.get_order_book(cfg.market_token_id)
        print(f'Best Bid: {ob.bids[0].price if ob.bids else "N/A"}')
        print(f'Best Ask: {ob.asks[0].price if ob.asks else "N/A"}')
    except Exception as e:
        print(f'Orderbook error: {e}')
    
    # Get price
    try:
        price = client.get_polymarket_price(cfg.market_token_id)
        print(f'Current Price: {price}')
    except Exception as e:
        print(f'Price error: {e}')
    
    # Check if we can trade
    print()
    print('=== Pre-trade Check ===')
    try:
        can_trade, reason = client._can_place_order(cfg.market_token_id, 'BUY', cfg.default_trade_size_usd)
        print(f'Can place order: {can_trade}')
        print(f'Reason: {reason}')
    except Exception as e:
        print(f'Pre-trade check error: {e}')
    
    print()
    print('=== Ready for Real Test ===')
    if not cfg.dry_run:
        print('WARNING: DRY_RUN is False - real trades will be executed!')
    else:
        print('Safe mode: DRY_RUN is True')

if __name__ == '__main__':
    main()
