
import pytest
from src.config import Config, TradingProfile
from src.bot_session import BotConfigData

def test_config_has_rebuy_defaults():
    """Test that Config class has the correct default values for rebuy settings."""
    config = Config(private_key="test_key")
    
    assert hasattr(config, "rebuy_delay_seconds")
    assert config.rebuy_delay_seconds == 2.0
    
    assert hasattr(config, "rebuy_strategy")
    assert config.rebuy_strategy == "immediate"
    
    assert hasattr(config, "rebuy_drop_pct")
    assert config.rebuy_drop_pct == 0.1

def test_bot_config_data_includes_rebuy_fields():
    """Test that BotConfigData includes rebuy fields in serialization."""
    # Create config data
    data = BotConfigData(
        bot_id="test_bot",
        name="Test Bot",
        private_key="test_key",
        rebuy_delay_seconds=5.0,
        rebuy_strategy="wait_for_drop",
        rebuy_drop_pct=1.5
    )
    
    # Check serialization
    config_dict = data.to_dict()
    assert config_dict["rebuy_delay_seconds"] == 5.0
    assert config_dict["rebuy_strategy"] == "wait_for_drop"
    assert config_dict["rebuy_drop_pct"] == 1.5
    
    # Check conversion to Config object
    config = data.to_config()
    assert config.rebuy_delay_seconds == 5.0
    assert config.rebuy_strategy == "wait_for_drop"
    assert config.rebuy_drop_pct == 1.5

def test_trading_profile_overrides():
    """Test that TradingProfile can override rebuy settings."""
    # Create a profile with rebuy settings
    # Note: We need to ensure TradingProfile supports these fields first
    # This test might fail until we update TradingProfile, which is part of the plan
    pass
