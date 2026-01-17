import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.bot_session import BotConfigData, BotSession


class DummyClient:
    def __init__(self):
        self._wallet = "0xabc"

    def get_wallet_address(self):
        return self._wallet

    def get_usdc_balance(self):
        return 0.0

    def get_market_info(self):
        return {"active": True, "closed": False, "question": "Q"}


@pytest.mark.parametrize(
    "market_info,expected",
    [
        ({"active": True, "closed": False}, "active"),
        ({"active": False, "closed": False}, "inactive"),
        ({"active": False, "closed": True}, "closed"),
        ({"active": True, "closed": False, "outcome": "YES"}, "resolved"),
    ],
)
def test_market_status_mapping(monkeypatch, tmp_path, market_info, expected):
    cfg = BotConfigData.create(name="t")
    s = BotSession(cfg)
    s.client = DummyClient()
    monkeypatch.setattr(s, "_runtime_state_file", tmp_path / "runtime.json")

    monkeypatch.setattr(s.client, "get_market_info", lambda: market_info)

    assert s._get_market_status() == expected


def test_runtime_state_persistence(monkeypatch, tmp_path):
    cfg = BotConfigData.create(name="t")
    s = BotSession(cfg)
    s.client = DummyClient()

    runtime_file = tmp_path / "runtime.json"
    monkeypatch.setattr(s, "_runtime_state_file", runtime_file)

    # simulate updates
    s._update_24h_price(0.4)
    s._record_trade("BUY")

    assert runtime_file.exists()
    data = json.loads(runtime_file.read_text())
    assert data["price_24h_ago"] == 0.4
    assert data["last_trade_side"] == "BUY"
    assert data["last_trade_time"] is not None

    # new session loads it
    s2 = BotSession(cfg)
    monkeypatch.setattr(s2, "_runtime_state_file", runtime_file)
    s2._load_runtime_state()

    assert s2._price_24h_ago == 0.4
    assert s2._last_trade_side == "BUY"
    assert isinstance(s2._last_trade_time, datetime)
