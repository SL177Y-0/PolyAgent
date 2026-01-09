import types
from src.clob_client import Client
from src.config import Config
import types

class DummyOrder:
    def __init__(self, price, size):
        self.price = price
        self.size = size

class DummyOB:
    def __init__(self, bids, asks):
        self.bids = bids
        self.asks = asks

def test_mid_price_from_orderbook(monkeypatch):
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
    )
    c = Client.__new__(Client)
    c.config = cfg
    def fake_get_ob(token=None):
        return DummyOB([DummyOrder(0.48, 10)], [DummyOrder(0.52, 12)])
    c.get_orderbook = fake_get_ob
    assert abs(Client.get_mid_price(c, "t") - 0.5) < 1e-9

from src.bot import Bot

class DummyClient2:
    def resolve_token_id(self):
        return "t"
    def get_mid_price(self, token_id=None):
        return 0.505

def test_spike_compute_baseline_first(monkeypatch):
    from datetime import datetime, timezone
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
        price_history_size=10,
    )
    b = Bot(cfg, client=DummyClient2())
    # History is a deque of (datetime, price) tuples
    now = datetime.now(timezone.utc)
    for p in [0.50, 0.50, 0.50, 0.50, 0.50]:
        b.history.append((now, p))
    price = b.client.get_mid_price("t")
    spike_pct, _ = b._compute_spike_multi_window(price)  # Use new API
    assert spike_pct > 0.9  # ~1%

# New tests for Polymarket pricing logic

def test_polymarket_price_tight_spread_uses_midpoint(monkeypatch):
    """When spread <= 0.10, should use midpoint."""
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
    )
    c = Client.__new__(Client)
    c.config = cfg

    # Tight spread: 0.49 bid, 0.51 ask = spread 0.02 <= 0.10
    def fake_get_ob(token=None):
        return DummyOB([DummyOrder(0.49, 10)], [DummyOrder(0.51, 10)])

    # Mock get_last_trade_price to return 0 (should not be used)
    def fake_last_trade(token=None):
        return 0.0

    c.get_orderbook = fake_get_ob
    c.get_last_trade_price = fake_last_trade

    # Should use midpoint = 0.50
    price = c.get_polymarket_price("t")
    assert abs(price - 0.50) < 1e-6, f"Expected 0.50, got {price}"

def test_polymarket_price_wide_spread_uses_last_trade(monkeypatch):
    """When spread > 0.10, should use last trade price."""
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
    )
    c = Client.__new__(Client)
    c.config = cfg

    # Wide spread: 0.40 bid, 0.60 ask = spread 0.20 > 0.10
    def fake_get_ob(token=None):
        return DummyOB([DummyOrder(0.40, 10)], [DummyOrder(0.60, 10)])

    # Mock last trade price at 0.45
    def fake_last_trade(token=None):
        return 0.45

    c.get_orderbook = fake_get_ob
    c.get_last_trade_price = fake_last_trade

    # Should use last trade price = 0.45, NOT midpoint = 0.50
    price = c.get_polymarket_price("t")
    assert abs(price - 0.45) < 1e-6, f"Expected 0.45 (last trade), got {price}"

def test_polymarket_price_exactly_0_10_spread_uses_midpoint(monkeypatch):
    """When spread is slightly under 0.10, should use midpoint."""
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
    )
    c = Client.__new__(Client)
    c.config = cfg

    # Spread slightly under 0.10: 0.451 bid, 0.55 ask = spread 0.099 < 0.10
    def fake_get_ob(token=None):
        return DummyOB([DummyOrder(0.451, 10)], [DummyOrder(0.55, 10)])

    def fake_last_trade(token=None):
        return 0.35  # Different from midpoint

    c.get_orderbook = fake_get_ob
    c.get_last_trade_price = fake_last_trade

    # Should use midpoint since spread < 0.10
    expected_mid = (0.451 + 0.55) / 2  # 0.5005
    price = c.get_polymarket_price("t")
    assert abs(price - expected_mid) < 1e-6, f"Expected {expected_mid} (midpoint), got {price}"

def test_polymarket_price_wide_spread_no_last_trade_falls_back_to_midpoint(monkeypatch):
    """When spread > 0.10 but no last trade, fall back to midpoint."""
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
    )
    c = Client.__new__(Client)
    c.config = cfg

    # Wide spread
    def fake_get_ob(token=None):
        return DummyOB([DummyOrder(0.30, 10)], [DummyOrder(0.70, 10)])

    # No last trade available
    def fake_last_trade(token=None):
        return 0.0

    c.get_orderbook = fake_get_ob
    c.get_last_trade_price = fake_last_trade

    # Should fall back to midpoint = 0.50
    price = c.get_polymarket_price("t")
    assert abs(price - 0.50) < 1e-6, f"Expected 0.50 (fallback midpoint), got {price}"

def test_polymarket_price_extreme_wide_spread_illiquid_market(monkeypatch):
    """Test extreme illiquid market scenario (0.01 bid, 0.99 ask)."""
    cfg = Config(
        private_key=("0"*64),
        signature_type=0,
        host="https://clob.polymarket.com",
        chain_id=137,
        market_token_id="t",
    )
    c = Client.__new__(Client)
    c.config = cfg

    # Extreme spread: 0.98 > 0.10
    def fake_get_ob(token=None):
        return DummyOB([DummyOrder(0.01, 1)], [DummyOrder(0.99, 1)])

    # Last trade at more reasonable price
    def fake_last_trade(token=None):
        return 0.38  # Actual market consensus

    c.get_orderbook = fake_get_ob
    c.get_last_trade_price = fake_last_trade

    # Should use last trade price = 0.38, NOT midpoint = 0.50
    price = c.get_polymarket_price("t")
    assert abs(price - 0.38) < 1e-6, f"Expected 0.38 (last trade for illiquid), got {price}"
