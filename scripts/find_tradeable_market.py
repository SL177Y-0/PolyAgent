#!/usr/bin/env python3
"""
Find Active Tradeable Market
============================
Finds markets suitable for the Spike Sam strategy:
- Has orderbook with actual orders
- Reasonable spread (< 10%)
- Mid-range price (0.20-0.80 for volatility potential)
- Good liquidity
"""
import requests
import json
import sys
from datetime import datetime

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"

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

def check_orderbook(token_id):
    """Check if token has a tradeable orderbook."""
    try:
        r = requests.get(f"{CLOB_API}/book?token_id={token_id}", timeout=10)
        if r.status_code != 200:
            return None
        
        data = r.json()
        bids = data.get('bids', [])
        asks = data.get('asks', [])
        
        if not bids or not asks:
            return None
        
        best_bid = float(bids[0]['price'])
        best_ask = float(asks[0]['price'])
        mid_price = (best_bid + best_ask) / 2
        spread = best_ask - best_bid
        spread_pct = (spread / mid_price * 100) if mid_price > 0 else 999
        
        # Calculate depth
        bid_depth = sum(float(b.get('size', 0)) for b in bids[:5])
        ask_depth = sum(float(a.get('size', 0)) for a in asks[:5])
        
        return {
            'best_bid': best_bid,
            'best_ask': best_ask,
            'mid_price': mid_price,
            'spread': spread,
            'spread_pct': spread_pct,
            'bid_depth': bid_depth,
            'ask_depth': ask_depth,
            'total_depth': bid_depth + ask_depth,
        }
    except Exception as e:
        return None

def score_market(m, ob):
    """Score a market for suitability."""
    score = 0
    
    # Spread score (0-30) - tighter is better
    spread_pct = ob['spread_pct']
    if spread_pct <= 2:
        score += 30
    elif spread_pct <= 5:
        score += 25
    elif spread_pct <= 10:
        score += 20
    elif spread_pct <= 20:
        score += 10
    elif spread_pct <= 30:
        score += 5
    
    # Price range score (0-25) - mid-range is best
    price = ob['mid_price']
    if 0.35 <= price <= 0.65:
        score += 25
    elif 0.25 <= price <= 0.75:
        score += 20
    elif 0.15 <= price <= 0.85:
        score += 15
    elif 0.10 <= price <= 0.90:
        score += 10
    
    # Liquidity score (0-25)
    liq = m.get('liquidity', 0)
    if liq >= 50000:
        score += 25
    elif liq >= 20000:
        score += 20
    elif liq >= 10000:
        score += 15
    elif liq >= 5000:
        score += 10
    elif liq >= 2000:
        score += 5
    
    # Depth score (0-20)
    depth = ob['total_depth']
    if depth >= 500:
        score += 20
    elif depth >= 200:
        score += 15
    elif depth >= 100:
        score += 10
    elif depth >= 50:
        score += 5
    
    return score

def main():
    print("=" * 70)
    print("  POLYMARKET - FIND TRADEABLE MARKET FOR SPIKE SAM STRATEGY")
    print("=" * 70)
    print()
    print("Fetching markets from Gamma API...")
    
    params = {'closed': 'false', 'limit': 200}
    r = requests.get(f"{GAMMA_API}/markets", params=params, timeout=20)
    markets = r.json()
    
    print(f"Fetched {len(markets)} markets")
    
    # Filter active markets with tokens
    candidates = []
    for m in markets:
        if not m.get('closed', False) and m.get('active', False):
            liq = float(m.get('liquidity', 0) or 0)
            tokens = parse_token_ids(m.get('clobTokenIds'))
            if liq > 0 and tokens:
                candidates.append({
                    'question': m.get('question', 'N/A')[:60],
                    'liquidity': liq,
                    'volume': float(m.get('volume', 0) or 0),
                    'token_id': tokens[0],
                    'slug': m.get('slug', 'N/A'),
                    'market': m,
                })
    
    # Sort by liquidity first
    candidates.sort(key=lambda x: x['liquidity'], reverse=True)
    
    print(f"Found {len(candidates)} active markets with tokens")
    print()
    print("Checking orderbooks (top 50 by liquidity)...")
    print()
    
    tradeable = []
    for i, c in enumerate(candidates[:50]):
        ob = check_orderbook(c['token_id'])
        
        if ob and ob['spread_pct'] < 50:  # Only markets with reasonable spread
            score = score_market(c['market'], ob)
            c['orderbook'] = ob
            c['score'] = score
            tradeable.append(c)
            print(f"  [{i+1}] FOUND: {c['slug'][:40]}... Score={score}")
        
        if (i + 1) % 10 == 0:
            print(f"  Checked {i+1}/50...")
    
    if not tradeable:
        print("\nNo tradeable markets found!")
        print("All markets either have no orderbook or very wide spreads.")
        return 1
    
    # Sort by score
    tradeable.sort(key=lambda x: x['score'], reverse=True)
    
    print()
    print("=" * 70)
    print("  TOP TRADEABLE MARKETS (Best for Spike Sam Strategy)")
    print("=" * 70)
    print()
    
    for i, t in enumerate(tradeable[:10], 1):
        ob = t['orderbook']
        print(f"{i}. {t['question']}")
        print(f"   Score: {t['score']}/100 | Slug: {t['slug']}")
        print(f"   Liquidity: ${t['liquidity']:,.0f} | Volume: ${t['volume']:,.0f}")
        print(f"   Price: {ob['mid_price']:.4f} | Spread: {ob['spread_pct']:.1f}%")
        print(f"   Bid: {ob['best_bid']:.4f} | Ask: {ob['best_ask']:.4f}")
        print(f"   Depth: Bid={ob['bid_depth']:.0f} Ask={ob['ask_depth']:.0f}")
        print(f"   Token: {t['token_id']}")
        print()
    
    # Recommend best market
    if tradeable:
        best = tradeable[0]
        print("=" * 70)
        print("  RECOMMENDED MARKET")
        print("=" * 70)
        print()
        print(f"  Market: {best['slug']}")
        print(f"  Token:  {best['token_id']}")
        print(f"  Score:  {best['score']}/100")
        print()
        print("  To use this market, run:")
        print(f"    # Update .env file:")
        print(f"    MARKET_SLUG={best['slug']}")
        print(f"    # OR")
        print(f"    MARKET_TOKEN_ID={best['token_id']}")
        print()
    
    return 0

if __name__ == "__main__":
    sys.exit(main())
