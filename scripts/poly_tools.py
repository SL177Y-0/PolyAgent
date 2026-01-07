#!/usr/bin/env python3
"""
PolyTools - Polymarket Market Discovery & Analysis Tools
========================================================
A consolidated tool for finding active markets, checking liquidity, and analyzing events.

Usage:
    python scripts/poly_tools.py list-events          # List active sports events
    python scripts/poly_tools.py find-liquid         # Find liquid markets
    python scripts/poly_tools.py check-market SLUG   # Check specific market
    python scripts/poly_tools.py prices SLUG         # Show outcome prices
"""

import sys
import os
import argparse
import json
import requests

GAMMA_API = "https://gamma-api.polymarket.com"
CLOB_API = "https://clob.polymarket.com"


def print_header(title: str):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def list_sports_events(limit: int = 20):
    """List active sports events sorted by liquidity."""
    print_header("Active Sports Events")

    try:
        response = requests.get(f"{GAMMA_API}/events?limit=100", timeout=10)
        events = response.json()
    except Exception as e:
        print(f"Error fetching events: {e}")
        return False

    sports_keywords = ['sports', 'football', 'soccer', 'tennis', 'basketball',
                      'nba', 'nfl', 'mlb', 'nhl', 'cricket', 'combat',
                      'fight', 'match', 'game', 'race', 'tournament',
                      'championship', 'cup', 'league', 'bowl', 'super']

    sports_events = []
    for event in events:
        tags = event.get('tags', [])
        tag_values = []
        for tag in tags:
            if isinstance(tag, dict):
                tag_values.append(tag.get('name', '').lower())
            else:
                tag_values.append(str(tag).lower())

        title = event.get('question', event.get('title', '')).lower()

        is_sports = (
            any(tv in sports_keywords for tv in tag_values) or
            any(kw in title for kw in sports_keywords)
        )

        if is_sports and event.get('active', False):
            markets = event.get('markets', [])
            if markets:
                total_liquidity = sum(float(m.get('liquidity', 0) or 0) for m in markets)
                if total_liquidity > 100:
                    sports_events.append({
                        'slug': event.get('slug', 'N/A'),
                        'title': event.get('question', event.get('title', 'N/A'))[:80],
                        'liquidity': total_liquidity,
                        'markets': len(markets),
                        'end_date': event.get('endDate', 'N/A')
                    })

    sports_events.sort(key=lambda x: x['liquidity'], reverse=True)

    print(f"Found {len(sports_events)} active sports events\n")

    for i, e in enumerate(sports_events[:limit], 1):
        print(f"{i}. {e['slug']}")
        print(f"   {e['title']}")
        print(f"   Liquidity: ${e['liquidity']:,.0f} | Markets: {e['markets']}")

    return True


def find_liquid_markets(min_liquidity: float = 1000):
    """Find markets with high liquidity."""
    print_header(f"High Liquidity Markets (>${min_liquidity:,.0f})")

    try:
        response = requests.get(f"{GAMMA_API}/markets?limit=100", timeout=10)
        markets = response.json()
    except Exception as e:
        print(f"Error fetching markets: {e}")
        return False

    liquid_markets = []
    for m in markets:
        liquidity = float(m.get('liquidity', 0) or 0)
        if liquidity >= min_liquidity and m.get('active', False):
            liquid_markets.append({
                'question': m.get('question', '')[:70],
                'liquidity': liquidity,
                'slug': m.get('slug', 'N/A'),
                'price': m.get('outcomePrices', ['N/A'])
            })

    liquid_markets.sort(key=lambda x: x['liquidity'], reverse=True)

    for i, m in enumerate(liquid_markets[:15], 1):
        print(f"{i}. {m['question']}")
        print(f"   Liquidity: ${m['liquidity']:,.0f}")
        print(f"   Slug: {m['slug']}")
        print(f"   Prices: {m['price']}")
        print()

    return True


def check_market(slug: str):
    """Check a specific market's details."""
    print_header(f"Market: {slug}")

    try:
        response = requests.get(f"{GAMMA_API}/events?slug={slug}", timeout=10)
        data = response.json()
    except Exception as e:
        print(f"Error fetching market: {e}")
        return False

    if not data:
        print(f"Market '{slug}' not found")
        return False

    event = data[0]
    markets = event.get('markets', [])

    print(f"Event: {event.get('question', 'N/A')[:80]}")
    print(f"Active: {event.get('active', False)}")
    print(f"End Date: {event.get('endDate', 'N/A')}")
    print(f"\nMarkets ({len(markets)}):")
    print("-" * 60)

    for i, m in enumerate(markets[:15], 0):
        question = m.get("question", "")[:70]
        outcome_prices = m.get("outcomePrices", [])
        token_ids = m.get("clobTokenIds", [])

        print(f"\n{i}. {question}")
        print(f"   Prices: {outcome_prices}")
        print(f"   CLOB Tokens: {len(token_ids) if token_ids else 0}")

        if token_ids:
            print(f"   Token ID: {token_ids[0][:40]}..." if len(token_ids[0]) > 40 else f"   Token ID: {token_ids[0]}")

    return True


def show_outcome_prices(slug: str):
    """Show outcome prices for a market."""
    print_header(f"Outcome Prices: {slug}")

    try:
        response = requests.get(f"{GAMMA_API}/events?slug={slug}", timeout=10)
        data = response.json()
    except Exception as e:
        print(f"Error: {e}")
        return False

    if not data:
        print("Market not found")
        return False

    event = data[0]
    markets = event.get('markets', [])

    for i, m in enumerate(markets[:15], 0):
        question = m.get("question", "")[:60]
        outcome_prices = m.get("outcomePrices", [])
        price_strings = m.get("priceStrings", None)

        print(f"{i}. {question}")
        print(f"   outcomePrices: {outcome_prices}")
        print(f"   priceStrings: {price_strings}")

        token_ids = m.get("clobTokenIds", [])
        print(f"   CLOB tokens: {len(token_ids) if token_ids else 0}")
        print()

    return True


def scan_liquidity(slug: str):
    """Scan liquidity for all tokens in a market."""
    print_header(f"Liquidity Scan: {slug}")

    # Import client for orderbook checks
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    try:
        from src.config import Config
        from src.clob_client import Client

        cfg = Config.from_env()
        client = Client(cfg)
    except Exception as e:
        print(f"Warning: Could not import client: {e}")
        print("Showing basic liquidity only...")
        client = None

    try:
        response = requests.get(f"{GAMMA_API}/events?slug={slug}", timeout=10)
        data = response.json()
    except Exception as e:
        print(f"Error: {e}")
        return False

    if not data:
        print("Market not found")
        return False

    event = data[0]
    markets = event.get('markets', [])

    for m in markets:
        token_ids = m.get("clobTokenIds", [])
        if not token_ids:
            continue

        question = m.get("question", "")[:60]
        print(f"\n{question}")

        if client:
            for token_id in token_ids[:3]:  # Check first 3 tokens
                try:
                    orderbook = client.get_orderbook(token_id)
                    bids = orderbook.bids if hasattr(orderbook, 'bids') else []
                    asks = orderbook.asks if hasattr(orderbook, 'asks') else []

                    if bids and asks:
                        best_bid = float(bids[0].price) if bids else 0
                        best_ask = float(asks[0].price) if asks else 0
                        spread = ((best_ask - best_bid) / best_bid * 100) if best_bid > 0 else 0
                        bid_liq = sum(float(b.size) if hasattr(b, 'size') else 0 for b in bids[:5])
                        ask_liq = sum(float(a.size) if hasattr(a, 'size') else 0 for a in asks[:5])

                        print(f"  Token {token_id[:30]}...")
                        print(f"  Bid: {best_bid:.4f} | Ask: {best_ask:.4f} | Spread: {spread:.2f}%")
                        print(f"  Liq - Bid: {bid_liq:.0f} | Ask: {ask_liq:.0f}")
                except Exception as e:
                    print(f"  Token error: {e}")
        else:
            print(f"  Tokens: {len(token_ids)} (no orderbook data)")

    return True


def main():
    parser = argparse.ArgumentParser(
        description="Polymarket Market Discovery & Analysis Tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python scripts/poly_tools.py list-events
  python scripts/poly_tools.py find-liquid --min-liquidity 5000
  python scripts/poly_tools.py check-market wta-mcnally-juvan-2026-01-09
  python scripts/poly_tools.py prices wta-mcnally-juvan-2026-01-09
  python scripts/poly_tools.py scan-liquidity wta-mcnally-juvan-2026-01-09
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='Command to run')

    # list-events
    subparsers.add_parser('list-events', help='List active sports events')

    # find-liquid
    liquid_parser = subparsers.add_parser('find-liquid', help='Find liquid markets')
    liquid_parser.add_argument('--min-liquidity', type=float, default=1000,
                              help='Minimum liquidity (default: 1000)')

    # check-market
    market_parser = subparsers.add_parser('check-market', help='Check specific market')
    market_parser.add_argument('slug', help='Market slug')

    # prices
    prices_parser = subparsers.add_parser('prices', help='Show outcome prices')
    prices_parser.add_argument('slug', help='Market slug')

    # scan-liquidity
    scan_parser = subparsers.add_parser('scan-liquidity', help='Scan market liquidity with CLOB')
    scan_parser.add_argument('slug', help='Market slug')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 1

    # Route to appropriate function
    if args.command == 'list-events':
        return 0 if list_sports_events() else 1
    elif args.command == 'find-liquid':
        return 0 if find_liquid_markets(args.min_liquidity) else 1
    elif args.command == 'check-market':
        return 0 if check_market(args.slug) else 1
    elif args.command == 'prices':
        return 0 if show_outcome_prices(args.slug) else 1
    elif args.command == 'scan-liquidity':
        return 0 if scan_liquidity(args.slug) else 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
