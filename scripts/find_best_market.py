#!/usr/bin/env python3
"""
Find Best Market for Spike Sam Strategy
========================================
Scores markets based on criteria optimal for the spike fade strategy:
1. Liquidity - Higher is better (more trading volume)
2. Spread - Tighter is better (lower trading costs)
3. Price Range - Mid-range prices (0.30-0.70) are best for volatility
4. Activity - Recent trading activity
5. Time to Expiry - Not too close to resolution

Usage:
    python scripts/find_best_market.py
    python scripts/find_best_market.py --category sports
    python scripts/find_best_market.py --category crypto
    python scripts/find_best_market.py --min-liquidity 5000
"""

import sys
import os
import argparse
import json
import requests
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


def get_events(limit: int = 200) -> List[Dict]:
    """Fetch active events from Gamma API."""
    try:
        response = requests.get(f"{GAMMA_API}/events?limit={limit}&active=true", timeout=15)
        return response.json()
    except Exception as e:
        print(f"Error fetching events: {e}")
        return []


def get_orderbook_metrics(token_id: str) -> Optional[Dict]:
    """Get orderbook metrics for a token."""
    try:
        response = requests.get(f"{CLOB_API}/book?token_id={token_id}", timeout=10)
        if response.status_code == 200:
            data = response.json()
            bids = data.get('bids', [])
            asks = data.get('asks', [])
            
            if bids and asks:
                best_bid = float(bids[0]['price'])
                best_ask = float(asks[0]['price'])
                mid_price = (best_bid + best_ask) / 2
                spread = best_ask - best_bid
                spread_pct = (spread / mid_price * 100) if mid_price > 0 else 100
                
                # Calculate depth (top 5 levels)
                bid_depth = sum(float(b.get('size', 0)) for b in bids[:5])
                ask_depth = sum(float(a.get('size', 0)) for a in asks[:5])
                
                return {
                    'mid_price': mid_price,
                    'best_bid': best_bid,
                    'best_ask': best_ask,
                    'spread': spread,
                    'spread_pct': spread_pct,
                    'bid_depth': bid_depth,
                    'ask_depth': ask_depth,
                    'total_depth': bid_depth + ask_depth,
                    'has_liquidity': True
                }
        return None
    except Exception:
        return None


def score_market(market: Dict, ob_metrics: Optional[Dict]) -> float:
    """
    Score a market for suitability with the spike fade strategy.
    Higher score = better market.
    
    Scoring Criteria:
    - Liquidity (0-30 points): Higher liquidity is better
    - Spread (0-25 points): Tighter spread is better  
    - Price Range (0-20 points): Mid-range prices (0.30-0.70) are ideal
    - Orderbook Depth (0-15 points): More depth = more tradeable
    - Activity (0-10 points): Recent activity
    """
    score = 0.0
    details = {}
    
    # 1. Liquidity Score (0-30 points)
    liquidity = float(market.get('liquidity', 0) or 0)
    if liquidity >= 50000:
        liq_score = 30
    elif liquidity >= 20000:
        liq_score = 25
    elif liquidity >= 10000:
        liq_score = 20
    elif liquidity >= 5000:
        liq_score = 15
    elif liquidity >= 2000:
        liq_score = 10
    elif liquidity >= 1000:
        liq_score = 5
    else:
        liq_score = 0
    score += liq_score
    details['liquidity_score'] = liq_score
    
    # 2. Spread Score (0-25 points) - requires orderbook
    if ob_metrics and ob_metrics.get('has_liquidity'):
        spread_pct = ob_metrics['spread_pct']
        if spread_pct <= 1:
            spread_score = 25
        elif spread_pct <= 2:
            spread_score = 20
        elif spread_pct <= 5:
            spread_score = 15
        elif spread_pct <= 10:
            spread_score = 10
        elif spread_pct <= 20:
            spread_score = 5
        else:
            spread_score = 0
        score += spread_score
        details['spread_score'] = spread_score
        details['spread_pct'] = spread_pct
    else:
        details['spread_score'] = 0
        
    # 3. Price Range Score (0-20 points)
    # Mid-range prices (0.30-0.70) offer best volatility potential
    if ob_metrics and ob_metrics.get('mid_price'):
        price = ob_metrics['mid_price']
    else:
        # Try to get from outcome prices
        prices = market.get('outcomePrices', [])
        if prices:
            try:
                price = float(prices[0]) if isinstance(prices[0], str) else prices[0]
            except:
                price = 0.5
        else:
            price = 0.5
    
    # Optimal range: 0.30-0.70
    if 0.35 <= price <= 0.65:
        price_score = 20  # Perfect range
    elif 0.25 <= price <= 0.75:
        price_score = 15
    elif 0.15 <= price <= 0.85:
        price_score = 10
    elif 0.10 <= price <= 0.90:
        price_score = 5
    else:
        price_score = 0  # Too extreme (likely resolved or nearly certain)
    score += price_score
    details['price_score'] = price_score
    details['current_price'] = price
    
    # 4. Orderbook Depth Score (0-15 points)
    if ob_metrics and ob_metrics.get('total_depth', 0) > 0:
        depth = ob_metrics['total_depth']
        if depth >= 1000:
            depth_score = 15
        elif depth >= 500:
            depth_score = 12
        elif depth >= 200:
            depth_score = 10
        elif depth >= 100:
            depth_score = 7
        elif depth >= 50:
            depth_score = 5
        else:
            depth_score = 2
        score += depth_score
        details['depth_score'] = depth_score
    else:
        details['depth_score'] = 0
        
    # 5. Activity Score (0-10 points)
    # Based on volume and number of outcomes
    volume = float(market.get('volume', 0) or 0)
    if volume >= 100000:
        activity_score = 10
    elif volume >= 50000:
        activity_score = 8
    elif volume >= 20000:
        activity_score = 6
    elif volume >= 10000:
        activity_score = 4
    elif volume >= 5000:
        activity_score = 2
    else:
        activity_score = 0
    score += activity_score
    details['activity_score'] = activity_score
    details['volume'] = volume
    
    return score, details


def categorize_market(event: Dict, market: Dict) -> str:
    """Categorize a market by type."""
    title = (market.get('question', '') + ' ' + event.get('title', '')).lower()
    tags = event.get('tags', [])
    tag_values = []
    for tag in tags:
        if isinstance(tag, dict):
            tag_values.append(tag.get('name', '').lower())
        else:
            tag_values.append(str(tag).lower())
    
    sports_keywords = ['sports', 'football', 'soccer', 'tennis', 'basketball', 
                      'nba', 'nfl', 'mlb', 'nhl', 'cricket', 'fight', 'match',
                      'game', 'race', 'tournament', 'championship', 'cup', 
                      'league', 'bowl', 'super', 'ufc', 'boxing', 'atp', 'wta']
    
    crypto_keywords = ['bitcoin', 'btc', 'ethereum', 'eth', 'crypto', 'token',
                      'coin', 'defi', 'blockchain', 'price', 'market cap']
    
    politics_keywords = ['election', 'president', 'congress', 'senate', 'vote',
                        'political', 'government', 'policy', 'trump', 'biden']
    
    all_text = ' '.join(tag_values) + ' ' + title
    
    if any(kw in all_text for kw in sports_keywords):
        return 'sports'
    elif any(kw in all_text for kw in crypto_keywords):
        return 'crypto'
    elif any(kw in all_text for kw in politics_keywords):
        return 'politics'
    else:
        return 'other'


def find_best_markets(
    category: Optional[str] = None,
    min_liquidity: float = 1000,
    top_n: int = 10,
    check_orderbook: bool = True
) -> List[Dict]:
    """Find and rank the best markets for trading."""
    
    print("\n" + "=" * 70)
    print("  POLYMARKET - BEST MARKET FINDER FOR SPIKE SAM STRATEGY")
    print("=" * 70)
    print(f"\nFilters: category={category or 'all'}, min_liquidity=${min_liquidity:,.0f}")
    print("Fetching markets...")
    
    events = get_events(200)
    if not events:
        print("No events found!")
        return []
    
    # Collect all active markets with their event context
    candidates = []
    for event in events:
        if not event.get('active', False):
            continue
            
        markets = event.get('markets', [])
        for market in markets:
            if not market.get('active', False):
                continue
                
            liquidity = float(market.get('liquidity', 0) or 0)
            if liquidity < min_liquidity:
                continue
            
            # Check category filter
            mkt_category = categorize_market(event, market)
            if category and mkt_category != category:
                continue
            
            # Get token IDs
            token_ids = market.get('clobTokenIds', [])
            if not token_ids:
                continue
            
            candidates.append({
                'event_slug': event.get('slug', ''),
                'event_title': event.get('title', event.get('question', ''))[:60],
                'market_question': market.get('question', '')[:70],
                'token_id': token_ids[0],  # Use first token (YES outcome)
                'liquidity': liquidity,
                'volume': float(market.get('volume', 0) or 0),
                'category': mkt_category,
                'outcome_prices': market.get('outcomePrices', []),
                'market': market
            })
    
    print(f"Found {len(candidates)} candidate markets")
    
    # Score each market
    scored_markets = []
    if check_orderbook:
        print("Checking orderbooks (this may take a moment)...")
    
    for i, candidate in enumerate(candidates[:50]):  # Limit to top 50 by liquidity
        ob_metrics = None
        if check_orderbook:
            ob_metrics = get_orderbook_metrics(candidate['token_id'])
            if (i + 1) % 10 == 0:
                print(f"  Checked {i + 1}/{min(50, len(candidates))} orderbooks...")
        
        score, details = score_market(candidate['market'], ob_metrics)
        
        if ob_metrics is None and check_orderbook:
            continue  # Skip markets with no orderbook
        
        candidate['score'] = score
        candidate['score_details'] = details
        candidate['ob_metrics'] = ob_metrics
        scored_markets.append(candidate)
    
    # Sort by score (highest first)
    scored_markets.sort(key=lambda x: x['score'], reverse=True)
    
    return scored_markets[:top_n]


def print_results(markets: List[Dict]):
    """Print the results in a nice format."""
    if not markets:
        print("\nNo suitable markets found!")
        return
    
    print("\n" + "=" * 70)
    print("  TOP MARKETS FOR SPIKE SAM STRATEGY")
    print("=" * 70)
    print(f"\n{'Rank':<5} {'Score':<7} {'Category':<10} {'Slug/Question':<50}")
    print("-" * 70)
    
    for i, m in enumerate(markets, 1):
        # Print header row
        print(f"\n{i:<5} {m['score']:<7.1f} {m['category']:<10} {m['event_slug'][:48]}")
        print(f"      {m['market_question'][:65]}")
        
        # Print metrics
        details = m.get('score_details', {})
        ob = m.get('ob_metrics', {}) or {}
        
        price = ob.get('mid_price', details.get('current_price', 0))
        spread = ob.get('spread_pct', 0)
        depth = ob.get('total_depth', 0)
        
        print(f"      Liquidity: ${m['liquidity']:,.0f} | Volume: ${details.get('volume', 0):,.0f}")
        print(f"      Price: {price:.4f} | Spread: {spread:.2f}% | Depth: {depth:.0f}")
        print(f"      Scores: Liq={details.get('liquidity_score',0)} Spread={details.get('spread_score',0)} "
              f"Price={details.get('price_score',0)} Depth={details.get('depth_score',0)} "
              f"Activity={details.get('activity_score',0)}")
        print(f"      Token: {m['token_id'][:50]}...")
    
    print("\n" + "=" * 70)
    
    # Recommend the best one
    if markets:
        best = markets[0]
        print("\nRECOMMENDED MARKET:")
        print(f"  Slug: {best['event_slug']}")
        print(f"  Token ID: {best['token_id']}")
        print(f"\nTo use this market, update your .env:")
        print(f"  MARKET_SLUG={best['event_slug']}")
        print(f"  # OR")
        print(f"  MARKET_TOKEN_ID={best['token_id']}")
    
    print()


def main():
    parser = argparse.ArgumentParser(
        description="Find best markets for the Spike Sam trading strategy"
    )
    parser.add_argument('--category', choices=['sports', 'crypto', 'politics', 'other'],
                       help='Filter by category')
    parser.add_argument('--min-liquidity', type=float, default=1000,
                       help='Minimum liquidity (default: 1000)')
    parser.add_argument('--top', type=int, default=10,
                       help='Number of top markets to show (default: 10)')
    parser.add_argument('--fast', action='store_true',
                       help='Skip orderbook checks (faster but less accurate)')
    
    args = parser.parse_args()
    
    markets = find_best_markets(
        category=args.category,
        min_liquidity=args.min_liquidity,
        top_n=args.top,
        check_orderbook=not args.fast
    )
    
    print_results(markets)
    
    return 0 if markets else 1


if __name__ == "__main__":
    sys.exit(main())
