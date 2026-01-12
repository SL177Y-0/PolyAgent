"""Quick config verification script."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from src.config import Config

c = Config.from_env()
print("=== CONFIG CHECK ===")
print(f"DRY_RUN: {c.dry_run}")
print(f"SIGNATURE_TYPE: {c.signature_type}")
print(f"FUNDER_ADDRESS: {c.funder_address}")
print(f"TRADE_SIZE: ${c.default_trade_size_usd}")
print(f"MARKET_SLUG: {c.market_slug}")
print(f"SPIKE_THRESHOLD: {c.spike_threshold_pct}%")
print(f"MIN_SPIKE_STRENGTH: {c.min_spike_strength}%")
print(f"TAKE_PROFIT: {c.take_profit_pct}%")
print(f"STOP_LOSS: {c.stop_loss_pct}%")
print(f"MAX_HOLD: {c.max_hold_seconds}s")
print(f"WSS_ENABLED: {c.wss_enabled}")
if not c.dry_run:
    print("=== REAL TRADING MODE ===")
else:
    print("=== DRY RUN MODE ===")
