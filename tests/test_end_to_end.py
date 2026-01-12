import types
from datetime import datetime, timezone, timedelta

from src.config import Config
from src.bot import Bot

class DummyClient:
    def __init__(self, prices):
        self.prices = prices
        self.i = 0
    def resolve_token_id(self):
        return "dummy"
    def get_mid_price(self, token_id=None):
        p = self.prices[min(self.i, len(self.prices)-1)]
        self.i += 1
        return p
    def place_market_order(self, side, amount_usd, token_id=None, order_type=None):
        return types.SimpleNamespace(success=True, response={"success": True, "side": side, "amount": amount_usd})


def test_spike_and_exit(monkeypatch):
    # Craft a price series with an UPWARD spike (then we SELL to fade it)
    # Starting at 0.50, spiking to 0.53 (6% up), then reverting
    prices = [0.50, 0.50, 0.50, 0.51, 0.52, 0.53, 0.52, 0.51, 0.50]
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="dummy",
        spike_threshold_pct=3.0,  # Threshold for this test
        price_history_size=100,
        cooldown_seconds=0,
        default_trade_size_usd=1.0,
        take_profit_pct=10.0,  # Higher TP for the test
        stop_loss_pct=10.0,  # Higher SL for the test
        max_hold_seconds=9999,
        dry_run=True,
        spike_windows_minutes=[1, 2, 5],  # Longer windows for test (60s, 120s, 300s)
    )
    bot = Bot(cfg)
    bot.client = DummyClient(prices)
    bot.token_id = "dummy"
    bot.initial_inventory_acquired = True  # Allow SELL (bot already has inventory)
    
    # Reset any state loaded from file (isolate test from real position.json)
    bot.open_position = None
    bot.realized_pnl = 0.0
    bot.total_trades = 0
    bot.winning_trades = 0
    bot.last_signal_time = None
    bot.history.clear()

    # Simulate price history over time - use recent timestamps within the windows
    base_time = datetime.now(timezone.utc) - timedelta(seconds=40)  # Start 40s ago
    spike_pct = 0.0  # Initialize for error message
    for i, price in enumerate(prices):
        timestamp = base_time + timedelta(seconds=i*5)  # 5s apart, ending at now
        bot.history.append((timestamp, price))

        if bot.open_position:
            reason = bot._risk_exit(price)
            if reason:
                bot._exit(reason, price)

        if bot.open_position is None and len(bot.history) >= 5:
            spike_pct, stats = bot._compute_spike_multi_window(price)
            # Positive spike (price up) -> SELL to fade
            if spike_pct >= cfg.spike_threshold_pct:
                bot._enter("SELL", price)

    # Should have entered on the spike up
    assert bot.last_signal_time is not None, f"Expected entry signal on price spike, got last spike_pct={spike_pct}%"
