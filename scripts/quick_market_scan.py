#!/usr/bin/env python3
"""Quick market scanner to find active tradeable markets."""
import requests
import json
from datetime import datetime

GAMMA_API = "https://gamma-api.polymarket.com"

def parse_token_ids(token_data):
    """Parse token IDs which may be a string or list."""
    if not token_data:
        return []
    if isinstance(token_data, str):
        try:
            return json.loads(token_data)
        except:
            return []
    return token_data

def main():
    print("Fetching markets from Gamma API...")
    
    params = {'closed': 'false', 'limit': 100}
    r = requests.get(f"{GAMMA_API}/markets", params=params, timeout=15)
    markets = r.json()
    
    print(f"Fetched {len(markets)} markets")
    
    # Filter and sort by liquidity
    active_markets = []
    for m in markets:
        if not m.get('closed', False) and m.get('active', False):
            liq = float(m.get('liquidity', 0) or 0)
            vol = float(m.get('volume', 0) or 0)
            tokens = parse_token_ids(m.get('clobTokenIds'))
            if liq > 0 and tokens:
                active_markets.append({
                    'question': m.get('question', 'N/A')[:60],
                    'liquidity': liq,
                    'volume': vol,
                    'token_id': tokens[0] if tokens else 'N/A',
                    'slug': m.get('slug', 'N/A'),
                    'prices': m.get('outcomePrices', []),
                })
    
    active_markets.sort(key=lambda x: x['liquidity'], reverse=True)
    
    print(f"Active with liquidity: {len(active_markets)}")
    print()
    
    for i, m in enumerate(active_markets[:15], 1):
        print(f"{i}. {m['question']}")
        print(f"   Liq: ${m['liquidity']:,.0f} | Vol: ${m['volume']:,.0f}")
        print(f"   Slug: {m['slug']}")
        tid = m['token_id']
        if len(tid) > 50:
            print(f"   Token: {tid[:50]}...")
        else:
            print(f"   Token: {tid}")
        print()
    
    # Test if any have working orderbooks
    print("=" * 60)
    print("Testing orderbooks for top 5 markets...")
    print("=" * 60)
    
    for m in active_markets[:5]:
        token = m['token_id']
        try:
            r = requests.get(f"https://clob.polymarket.com/book?token_id={token}", timeout=10)
            if r.status_code == 200:
                data = r.json()
                bids = data.get('bids', [])
                asks = data.get('asks', [])
                if bids and asks:
                    best_bid = float(bids[0]['price'])
                    best_ask = float(asks[0]['price'])
                    spread = (best_ask - best_bid) * 100
                    print(f"TRADEABLE: {m['slug']}")
                    print(f"  Bid: {best_bid:.4f} | Ask: {best_ask:.4f} | Spread: {spread:.2f}c")
                    print(f"  Token: {token}")
                else:
                    print(f"NO ORDERS: {m['slug']}")
            else:
                print(f"NO ORDERBOOK: {m['slug']} (status {r.status_code})")
        except Exception as e:
            print(f"ERROR: {m['slug']} - {e}")
        print()

if __name__ == "__main__":
    main()
