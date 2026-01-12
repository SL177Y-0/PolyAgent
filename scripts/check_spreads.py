#!/usr/bin/env python3
"""Debug script to check actual spreads."""
import requests
import json

GAMMA_API = 'https://gamma-api.polymarket.com'
CLOB_API = 'https://clob.polymarket.com'

def parse_token_ids(token_data):
    if not token_data:
        return []
    if isinstance(token_data, str):
        try:
            return json.loads(token_data)
        except:
            return []
    return token_data

# Get markets
print("Fetching markets...")
r = requests.get(f'{GAMMA_API}/markets?closed=false&limit=100', timeout=15)
markets = r.json()
print(f"Got {len(markets)} markets")

results = []
print("Checking orderbooks...")
for i, m in enumerate(markets[:30]):  # Check first 30
    tokens = parse_token_ids(m.get('clobTokenIds'))
    if not tokens:
        continue
    
    token = tokens[0]
    try:
        r = requests.get(f'{CLOB_API}/book?token_id={token}', timeout=10)
        if r.status_code == 200:
            data = r.json()
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if bids and asks:
                bid = float(bids[0]['price'])
                ask = float(asks[0]['price'])
                mid = (bid + ask) / 2
                spread = ask - bid
                spread_pct = spread / mid * 100 if mid > 0 else 999
                
                results.append({
                    'slug': m.get('slug', 'N/A')[:40],
                    'bid': bid,
                    'ask': ask,
                    'mid': mid,
                    'spread_pct': spread_pct,
                    'liq': float(m.get('liquidity', 0) or 0),
                    'token': token,
                })
    except Exception as e:
        pass
    
    if (i + 1) % 10 == 0:
        print(f"  Checked {i+1}/30...")

# Sort by spread
results.sort(key=lambda x: x['spread_pct'])

print()
print('Markets sorted by spread (tightest first):')
print('=' * 70)
print()
for i, r in enumerate(results[:15], 1):
    print(f"{i}. {r['slug']}")
    print(f"   Bid: {r['bid']:.4f} | Ask: {r['ask']:.4f} | Spread: {r['spread_pct']:.1f}%")
    print(f"   Mid: {r['mid']:.4f} | Liq: ${r['liq']:,.0f}")
    print(f"   Token: {r['token'][:50]}...")
    print()

if results:
    best = results[0]
    print('=' * 70)
    print('BEST MARKET (tightest spread):')
    print(f"  MARKET_SLUG={best['slug']}")
    print(f"  MARKET_TOKEN_ID={best['token']}")
