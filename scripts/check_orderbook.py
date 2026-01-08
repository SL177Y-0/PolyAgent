
from src.config import Config
from src.clob_client import Client
import json

cfg = Config.from_env()
c = Client(cfg)
tid = c.resolve_token_id()
print(f'Token ID: {tid}')

ob = c.get_orderbook(tid)
# Handle different response formats (obj or dict)
if hasattr(ob, "bids"):
    bids = ob.bids
    asks = ob.asks
elif isinstance(ob, dict):
    bids = ob.get("bids", [])
    asks = ob.get("asks", [])
else:
    bids = []
    asks = []

print(f'Bids: {len(bids)}')
print(f'Asks: {len(asks)}')

if len(bids) > 0:
    print(f'Best Bid: {bids[0]}')
if len(asks) > 0:
    print(f'Best Ask: {asks[0]}')
