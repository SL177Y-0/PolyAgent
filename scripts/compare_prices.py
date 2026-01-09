
import requests
from src.config import Config
from src.clob_client import Client

def main():
    print("🕵️ Comparing Price Sources...")
    cfg = Config.from_env()
    client = Client(cfg)
    
    # 1. Resolve Token ID (Khamenei)
    slug = "khamenei-out-as-supreme-leader-of-iran-by-january-31"
    print(f"Slug: {slug}")
    
    # 2. Fetch Gamma Price (UI Price)
    print("\n--- Gamma API (UI) ---")
    try:
        url = f"https://gamma-api.polymarket.com/events?slug={slug}"
        resp = requests.get(url)
        data = resp.json()
        market = data[0].get("markets", [{}])[0]
        
        # Gamma usually provides 'outcomePrices' or similar
        # Let's print the whole market object keys to find price
        # Actually, usually it's in the 'markets' list
        # "outcomePrices": ["0.18", "0.82"]
        outcome_prices = market.get("outcomePrices", [])
        clob_ids = market.get("clobTokenIds", [])
        
        print(f"Outcome Prices: {outcome_prices}")
        if outcome_prices:
            print(f"✅ YES Price: {outcome_prices[0]}")
            print(f"✅ NO Price: {outcome_prices[1]}")
            
        tid = clob_ids[0] if clob_ids else None
        print(f"Token ID: {tid}")
        
    except Exception as e:
        print(f"❌ Gamma Error: {e}")
        tid = None

    if not tid:
        print("Cannot proceed without Token ID")
        return

    # 3. Fetch CLOB Mid Price (Bot Current)
    print("\n--- CLOB Mid Price (Bot) ---")
    try:
        mid = client.get_mid_price(tid)
        print(f"📉 Mid Price: {mid}")
    except Exception as e:
        print(f"❌ CLOB Error: {e}")

    # 4. Fetch CLOB Orderbook
    print("\n--- CLOB Orderbook ---")
    try:
        ob = client.get_orderbook(tid)
        bids = ob.bids if hasattr(ob, 'bids') else ob.get('bids', [])
        asks = ob.asks if hasattr(ob, 'asks') else ob.get('asks', [])
        
        bb = bids[0].price if bids else "None"
        ba = asks[0].price if asks else "None"
        print(f"Bid: {bb}")
        print(f"Ask: {ba}")
    except Exception as e:
        print(f"❌ CLOB OB Error: {e}")

if __name__ == "__main__":
    main()
