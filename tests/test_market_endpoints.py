
import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, patch
from src.api_server import app, get_bot
from src.bot_session import BotSession, BotConfigData

client = TestClient(app)

@pytest.fixture
def mock_session():
    config_data = BotConfigData(
        bot_id="test_bot",
        name="Test Bot",
        private_key="0"*64
    )
    session = BotSession(config_data)
    # Mock client and token
    session.client = MagicMock()
    session.token_id = "test_token"
    return session

def test_get_orderbook(mock_session):
    """Test GET /api/bots/{id}/orderbook endpoint."""
    mock_session.client.get_orderbook.return_value = {
        "bids": [{"price": 0.5, "size": 100}, {"price": 0.49, "size": 200}],
        "asks": [{"price": 0.51, "size": 150}, {"price": 0.52, "size": 300}]
    }
    
    with patch("src.api_server.get_bot", return_value=mock_session):
        response = client.get("/api/bots/test_bot/orderbook?depth=5")
        
        assert response.status_code == 200
        data = response.json()
        assert data["bot_id"] == "test_bot"
        assert len(data["bids"]) == 2
        assert len(data["asks"]) == 2
        assert data["bids"][0]["price"] == 0.5
        assert data["asks"][0]["price"] == 0.51

def test_get_market_metrics(mock_session):
    """Test GET /api/bots/{id}/market-metrics endpoint."""
    mock_session.client.get_orderbook_metrics.return_value = {
        "best_bid": 0.50,
        "best_ask": 0.52,
        "spread_pct": 4.0,
        "bid_liquidity": 1000.0,
        "ask_liquidity": 2000.0
    }
    
    with patch("src.api_server.get_bot", return_value=mock_session):
        response = client.get("/api/bots/test_bot/market-metrics")
        
        assert response.status_code == 200
        data = response.json()
        assert data["bot_id"] == "test_bot"
        assert data["best_bid"] == 0.50
        assert data["best_ask"] == 0.52
        assert data["mid_price"] == 0.51
        assert data["spread_pct"] == 4.0

def test_endpoints_return_404_if_bot_not_found():
    with patch("src.api_server.get_bot", return_value=None):
        response = client.get("/api/bots/unknown_bot/orderbook")
        assert response.status_code == 404
        
        response = client.get("/api/bots/unknown_bot/market-metrics")
        assert response.status_code == 404
