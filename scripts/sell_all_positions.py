#!/usr/bin/env python3
"""Check current positions and sell them."""
import requests
from src.config import Config
from src.clob_client import Client
from py_clob_client.clob_types import MarketOrderArgs, OrderType
from py_clob_client.order_builder.constants import SELL

cfg = Config.from_env()
proxy_wallet = cfg.funder_address

print("=== CHECKING POSITIONS ===")
url = f"https://data-api.polymarket.com/positions?user={proxy_wallet}"
resp = requests.get(url, timeout=30)

if resp.status_code == 200:
    positions = resp.json()
    print(f"Found {len(positions)} positions")
    
    for pos in positions:
        asset = pos.get("asset", "")
        size = float(pos.get("size", 0))
        outcome = pos.get("outcome", "?")
        cur_price = float(pos.get("curPrice", 0))
        
        print(f"  - {outcome}: {size:.2f} shares @ ${cur_price:.4f}")
        
        if size > 0:
            print(f"\n  Selling {size} shares of {outcome}...")
            
            c = Client(cfg)
            args = MarketOrderArgs(
                token_id=str(asset),
                amount=float(size),
                side=SELL,
            )
            signed = c._client.create_market_order(args)
            result = c._client.post_order(signed, OrderType.FOK)
            print(f"  Result: {result}")
else:
    print(f"Error: {resp.status_code}")
