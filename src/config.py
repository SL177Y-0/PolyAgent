"""Centralized configuration for the Polymarket trading bot.

This module provides a typed Config object with validation and sensible defaults.
It supports both EOA (SIGNATURE_TYPE=0) and Proxy (SIGNATURE_TYPE=2) operation modes.

IMPORTANT: All configuration is managed via the frontend UI.
No environment variables are used. Configuration is stored in data/bots/*.json

Features:
- WebSocket real-time detection settings
- Multi-window spike detection configuration
- Volatility filtering options
- Trading profiles (normal, live, edge)
- Multi-bot support
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any


def _parse_list(val: Optional[str], default: List[int]) -> List[int]:
    """Parse comma-separated list of integers."""
    if val is None:
        return default
    try:
        return [int(x.strip()) for x in val.split(",")]
    except ValueError:
        return default


@dataclass
class TradingProfile:
    """Trading profile with preset configurations for different market conditions."""

    name: str
    description: str
    spike_threshold_pct: float
    take_profit_pct: float
    stop_loss_pct: float
    default_trade_size_usd: float
    max_hold_seconds: int
    cooldown_seconds: int = 120
    min_spike_strength: float = 5.0
    use_volatility_filter: bool = True
    max_volatility_cv: float = 10.0
    rebuy_delay_seconds: float = 2.0
    rebuy_strategy: str = "immediate"
    rebuy_drop_pct: float = 0.1

    @classmethod
    def get_profile(cls, name: str) -> "TradingProfile":
        """Get a trading profile by name."""
        profiles = cls.get_all_profiles()
        name = name.lower()
        if name not in profiles:
            raise ValueError(f"Unknown profile: {name}. Available: {list(profiles.keys())}")
        return profiles[name]

    @classmethod
    def get_all_profiles(cls) -> Dict[str, "TradingProfile"]:
        """Get all available trading profiles."""
        return {
            "normal": cls(
                name="normal",
                description="Balanced settings for general markets",
                spike_threshold_pct=8.0,
                take_profit_pct=3.0,
                stop_loss_pct=2.5,
                default_trade_size_usd=2.0,
                max_hold_seconds=3600,
                cooldown_seconds=120,
                min_spike_strength=5.0,
                use_volatility_filter=True,
                max_volatility_cv=10.0,
                rebuy_delay_seconds=2.0,
                rebuy_strategy="immediate",
                rebuy_drop_pct=0.1,
            ),
            "live": cls(
                name="live",
                description="More aggressive for high-volatility live markets",
                spike_threshold_pct=5.0,
                take_profit_pct=2.0,
                stop_loss_pct=1.5,
                default_trade_size_usd=1.0,
                max_hold_seconds=1800,
                cooldown_seconds=60,
                min_spike_strength=3.0,
                use_volatility_filter=False,  # Don't filter in fast-moving markets
                max_volatility_cv=20.0,
                rebuy_delay_seconds=1.0,
                rebuy_strategy="immediate",
                rebuy_drop_pct=0.0,
            ),
            "edge": cls(
                name="edge",
                description="Conservative settings for edge trading",
                spike_threshold_pct=12.0,
                take_profit_pct=5.0,
                stop_loss_pct=3.0,
                default_trade_size_usd=5.0,
                max_hold_seconds=7200,
                cooldown_seconds=300,
                min_spike_strength=8.0,
                use_volatility_filter=True,
                max_volatility_cv=5.0,
                rebuy_delay_seconds=5.0,
                rebuy_strategy="wait_for_drop",
                rebuy_drop_pct=0.5,
            ),
            "custom": cls(
                name="custom",
                description="Custom profile - use .env to override all values",
                spike_threshold_pct=8.0,
                take_profit_pct=3.0,
                stop_loss_pct=2.5,
                default_trade_size_usd=2.0,
                max_hold_seconds=3600,
                cooldown_seconds=120,
                min_spike_strength=5.0,
                use_volatility_filter=True,
                max_volatility_cv=10.0,
                rebuy_delay_seconds=2.0,
                rebuy_strategy="immediate",
                rebuy_drop_pct=0.1,
            ),
        }

    def apply_to_config(self, config: "Config") -> "Config":
        """Create a new config with profile values applied."""
        # Create a new config with profile values
        import dataclasses

        config_dict = dataclasses.asdict(config)
        config_dict.update({
            "spike_threshold_pct": self.spike_threshold_pct,
            "take_profit_pct": self.take_profit_pct,
            "stop_loss_pct": self.stop_loss_pct,
            "default_trade_size_usd": self.default_trade_size_usd,
            "max_hold_seconds": self.max_hold_seconds,
            "cooldown_seconds": self.cooldown_seconds,
            "min_spike_strength": self.min_spike_strength,
            "use_volatility_filter": self.use_volatility_filter,
            "max_volatility_cv": self.max_volatility_cv,
            "rebuy_delay_seconds": self.rebuy_delay_seconds,
            "rebuy_strategy": self.rebuy_strategy,
            "rebuy_drop_pct": self.rebuy_drop_pct,
        })
        return Config(**config_dict)


@dataclass
class Config:
    # Core API/wallet
    private_key: str
    signature_type: int = 0  # 0 = EOA, 2 = Proxy
    funder_address: Optional[str] = None
    host: str = "https://clob.polymarket.com"
    chain_id: int = 137

    # Market selection
    market_slug: Optional[str] = None
    market_token_id: Optional[str] = None
    market_index: Optional[int] = None  # Which market within event to use (0=first)

    # === V2: WebSocket Settings ===
    wss_enabled: bool = True
    wss_reconnect_delay: float = 1.0
    wss_max_reconnect_delay: float = 60.0

    # === V2: Multi-Window Spike Detection ===
    spike_windows_minutes: List[int] = field(default_factory=lambda: [10, 30, 60])
    use_volatility_filter: bool = True
    max_volatility_cv: float = 10.0
    min_spike_strength: float = 5.0

    # Strategy / spike detection (original)
    spike_threshold_pct: float = 8.0  # Updated default for better spike detection
    price_history_size: int = 3600  # Increased for 60-minute history at 1-sec intervals
    cooldown_seconds: int = 120
    max_concurrent_trades: int = 1  # Updated to 1 for single position per market
    min_liquidity_requirement: float = 10.0

    # Risk
    default_trade_size_usd: float = 2.0
    min_trade_usd: float = 1.0  # Polymarket minimum
    max_trade_usd: float = 100.0
    take_profit_pct: float = 3.0
    stop_loss_pct: float = 2.5
    max_hold_seconds: int = 3600  # 60 minutes in seconds
    slippage_tolerance: float = 0.06

    # Loop/logging
    price_poll_interval_sec: float = 1.0
    dry_run: bool = True
    log_level: str = "INFO"
    log_format: str = "PLAIN"
    log_file: str = "logs/bot.log"

    # Price/entry behavior
    use_gamma_primary: bool = False
    force_first_entry: bool = False
    first_entry_after_seconds: int = 10
    min_history_for_entry: int = 10

    # Startup entry mode
    # immediate_buy | wait_for_spike | delayed_buy
    entry_mode: str = "wait_for_spike"
    entry_delay_seconds: int = 0

    # Session limits
    max_trades_per_session: int = 0  # 0=disabled
    session_loss_limit_usd: float = 0.0

    # Daily limit (injected from global settings at start)
    daily_loss_limit_usd: float = 0.0

    # Orderbook guards
    min_bid_liquidity: float = 5.0
    min_ask_liquidity: float = 5.0  # Added for BUY order validation
    max_spread_pct: float = 1.0

    # === Multi-Bot Settings ===
    # Per-bot maximum balance allocation
    max_balance_per_bot: float = 10.0  # Maximum USD each bot can use
    # Enable bankroll management (default: true)
    enable_bankroll_management: bool = True
    # Percentage of total balance to allocate across all bots
    max_allocation_pct: float = 0.8  # Keep 20% reserve

    # === Rebuy Strategy ===
    rebuy_delay_seconds: float = 2.0
    rebuy_strategy: str = "immediate"  # "immediate" or "wait_for_drop"
    rebuy_drop_pct: float = 0.1

    # === Settlement Tracking ===
    # Time to wait for order settlement confirmation (via User WebSocket or fallback)
    # Polymarket settlements typically take 60-90 seconds
    settlement_timeout_seconds: float = 10

    @staticmethod
    def _parse_bool(val: Optional[str], default: bool) -> bool:
        if val is None:
            return default
        return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

    @classmethod
    def from_env(cls) -> "Config":
        raise RuntimeError("Environment-based config is disabled. Provide config from frontend or use Config(...) explicitly.")

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Config":
        cfg = cls(**data)
        cfg.validate()
        return cfg


    def validate(self) -> None:
        if self.signature_type not in (0, 2):
            raise ValueError("SIGNATURE_TYPE must be 0 (EOA) or 2 (Proxy)")
        if self.signature_type == 2 and not self.funder_address:
            raise ValueError("FUNDER_ADDRESS is required for Proxy mode")
        if not (0 < self.spike_threshold_pct < 100):
            raise ValueError("SPIKE_THRESHOLD_PCT must be in (0, 100)")
        if not (0 < self.take_profit_pct < 100 and 0 < self.stop_loss_pct < 100):
            raise ValueError("TP/SL percentages must be within (0, 100)")
        if self.price_history_size < 5:
            raise ValueError("PRICE_HISTORY_SIZE must be >= 5")
        if self.max_hold_seconds <= 0:
            raise ValueError("MAX_HOLD_SECONDS must be > 0")
        if self.min_trade_usd < 1.0:
            raise ValueError("MIN_TRADE_USD must be >= 1.0 (Polymarket minimum)")
        if not (self.min_trade_usd <= self.default_trade_size_usd <= self.max_trade_usd):
            raise ValueError(f"DEFAULT_TRADE_SIZE_USD must be between ${self.min_trade_usd} and ${self.max_trade_usd}")

    def get_spike_windows_seconds(self) -> List[int]:
        """Get spike detection windows in seconds."""
        return [m * 60 for m in self.spike_windows_minutes]
