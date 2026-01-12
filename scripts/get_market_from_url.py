#!/usr/bin/env python3
"""Extract market data from a Polymarket URL.

This script takes a Polymarket event URL and extracts:
- Market slug
- Token IDs for YES/NO outcomes
- Current prices
- Orderbook status

Usage:
    python scripts/get_market_from_url.py https://polymarket.com/event/some-market
    python scripts/get_market_from_url.py some-market-slug
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from urllib.parse import urlparse

# Fix Windows console encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

try:
    import requests
except ImportError:
    print("[X] requests library not found. Install with: pip install requests")
    sys.exit(1)


GAMMA_API = "https://gamma-api.polymarket.com"


def extract_slug_from_url(url_or_slug: str) -> str:
    """Extract market slug from Polymarket URL or return as-is if already a slug."""
    # If it's already a slug (no slashes or http)
    if not url_or_slug.startswith("http") and "/" not in url_or_slug:
        return url_or_slug
    
    # Parse URL
    parsed = urlparse(url_or_slug)
    path = parsed.path.strip("/")
    
    # Handle different URL formats:
    # /event/slug
    # /event/slug?tid=xxx
    # /markets/slug
    parts = path.split("/")
    
    if len(parts) >= 2 and parts[0] in ("event", "markets"):
        return parts[1]
    elif len(parts) == 1:
        return parts[0]
    
    return path


def get_market_by_slug(slug: str) -> dict | None:
    """Fetch market data from Gamma API using slug."""
    try:
        # Try events endpoint first
        resp = requests.get(f"{GAMMA_API}/events", params={"slug": slug}, timeout=10)
        if resp.status_code == 200:
            events = resp.json()
            if events and len(events) > 0:
                return events[0]
        
        # Try markets endpoint
        resp = requests.get(f"{GAMMA_API}/markets", params={"slug": slug}, timeout=10)
        if resp.status_code == 200:
            markets = resp.json()
            if markets and len(markets) > 0:
                return markets[0]
        
        # Search by partial match
        resp = requests.get(f"{GAMMA_API}/events", params={"slug_contains": slug, "limit": 5}, timeout=10)
        if resp.status_code == 200:
            events = resp.json()
            if events:
                print(f"\n[!] Exact slug not found. Similar matches:")
                for i, e in enumerate(events[:5], 1):
                    print(f"  {i}. {e.get('slug', 'N/A')} - {e.get('title', 'N/A')[:50]}")
                return events[0]
                
    except Exception as e:
        print(f"[X] API error: {e}")
    
    return None


def get_orderbook_status(token_id: str) -> dict:
    """Check if token has active orderbook."""
    try:
        resp = requests.get(
            "https://clob.polymarket.com/book",
            params={"token_id": token_id},
            timeout=10
        )
        if resp.status_code == 200:
            book = resp.json()
            bids = book.get("bids", [])
            asks = book.get("asks", [])
            
            best_bid = float(bids[0]["price"]) if bids else 0
            best_ask = float(asks[0]["price"]) if asks else 0
            
            return {
                "has_orderbook": bool(bids and asks),
                "best_bid": best_bid,
                "best_ask": best_ask,
                "spread": best_ask - best_bid if best_bid and best_ask else 0,
                "bid_depth": len(bids),
                "ask_depth": len(asks),
            }
    except Exception:
        pass
    
    return {"has_orderbook": False}


def format_market_info(market: dict) -> None:
    """Pretty print market information."""
    print("\n" + "=" * 70)
    print("MARKET INFORMATION")
    print("=" * 70)
    
    # Basic info
    print(f"\n[Basic Info]")
    print(f"  Title:        {market.get('title', 'N/A')}")
    print(f"  Slug:         {market.get('slug', 'N/A')}")
    print(f"  Description:  {market.get('description', 'N/A')[:100]}...")
    print(f"  End Date:     {market.get('endDate', 'N/A')}")
    print(f"  Active:       {market.get('active', 'N/A')}")
    print(f"  Closed:       {market.get('closed', 'N/A')}")
    
    # Markets/outcomes
    markets = market.get("markets", [])
    if not markets:
        # Single market format
        markets = [market]
    
    print(f"\n[Outcomes] ({len(markets)} found)")
    print("-" * 70)
    
    for i, m in enumerate(markets):
        outcome = m.get("outcome", m.get("groupItemTitle", f"Outcome {i+1}"))
        token_id = m.get("clobTokenIds")
        
        # Handle different token ID formats
        if isinstance(token_id, str):
            token_id = json.loads(token_id) if token_id.startswith("[") else [token_id]
        elif token_id is None:
            token_id = [m.get("conditionId", "N/A")]
        
        yes_token = token_id[0] if len(token_id) > 0 else "N/A"
        no_token = token_id[1] if len(token_id) > 1 else "N/A"
        
        # Get prices
        yes_price = m.get("outcomePrices")
        if isinstance(yes_price, str):
            try:
                prices = json.loads(yes_price)
                yes_price = float(prices[0]) if prices else 0
                no_price = float(prices[1]) if len(prices) > 1 else 1 - yes_price
            except:
                yes_price = 0
                no_price = 0
        else:
            yes_price = float(m.get("bestBid", 0) or 0)
            no_price = 1 - yes_price
        
        print(f"\n  Outcome #{i+1}: {outcome}")
        print(f"    YES Token:  {yes_token}")
        print(f"    NO Token:   {no_token}")
        print(f"    YES Price:  ${yes_price:.4f}")
        print(f"    NO Price:   ${no_price:.4f}")
        
        # Check orderbook for YES token
        if yes_token and yes_token != "N/A":
            ob = get_orderbook_status(yes_token)
            if ob["has_orderbook"]:
                print(f"    Orderbook:  [Y] Active (bid: ${ob['best_bid']:.3f}, ask: ${ob['best_ask']:.3f}, spread: {ob['spread']*100:.1f}%)")
            else:
                print(f"    Orderbook:  [N] No orders")
    
    # Generate .env snippet
    print("\n" + "=" * 70)
    print("COPY TO .env FILE")
    print("=" * 70)
    
    slug = market.get("slug", "")
    if markets:
        first_market = markets[0]
        token_ids = first_market.get("clobTokenIds")
        if isinstance(token_ids, str):
            token_ids = json.loads(token_ids) if token_ids.startswith("[") else [token_ids]
        token_id = token_ids[0] if token_ids else ""
    else:
        token_id = ""
    
    print(f"""
# Market Configuration
MARKET_SLUG={slug}
# Or use token ID directly:
# MARKET_TOKEN_ID={token_id}
""")
    
    print("=" * 70)


def main():
    if len(sys.argv) < 2:
        print("Usage: python scripts/get_market_from_url.py <polymarket-url-or-slug>")
        print("\nExamples:")
        print("  python scripts/get_market_from_url.py https://polymarket.com/event/some-market")
        print("  python scripts/get_market_from_url.py some-market-slug")
        print("  python scripts/get_market_from_url.py crban-syl-ran-2026-01-12")
        sys.exit(1)
    
    url_or_slug = sys.argv[1]
    
    print(f"\n[*] Processing: {url_or_slug}")
    
    # Extract slug
    slug = extract_slug_from_url(url_or_slug)
    print(f"[*] Extracted slug: {slug}")
    
    # Fetch market data
    print(f"[*] Fetching market data from Gamma API...")
    market = get_market_by_slug(slug)
    
    if not market:
        print(f"\n[X] Could not find market with slug: {slug}")
        print("\nTips:")
        print("  1. Check the URL is correct")
        print("  2. Try copying the slug directly from the URL")
        print("  3. The market might be closed or not exist")
        sys.exit(1)
    
    format_market_info(market)


if __name__ == "__main__":
    main()
