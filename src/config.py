"""Centralized configuration loaded from .env only.

This module provides a typed Config object with validation and sensible defaults
for the Polymarket trading bot. It supports both EOA (SIGNATURE_TYPE=0) and
Proxy (SIGNATURE_TYPE=2) operation modes.

Updated with v2 features:
- WebSocket real-time detection settings
- Multi-window spike detection configuration
- Volatility filtering options
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Optional, List
from dotenv import load_dotenv


def _parse_list(val: Optional[str], default: List[int]) -> List[int]:
    """Parse comma-separated list of integers."""
    if val is None:
        return default
    try:
        return [int(x.strip()) for x in val.split(",")]
    except ValueError:
        return default


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

    # Orderbook guards
    min_bid_liquidity: float = 5.0
    min_ask_liquidity: float = 5.0  # Added for BUY order validation
    max_spread_pct: float = 1.0

    @staticmethod
    def _parse_bool(val: Optional[str], default: bool) -> bool:
        if val is None:
            return default
        return str(val).strip().lower() in {"1", "true", "yes", "y", "on"}

    @classmethod
    def from_env(cls) -> "Config":
        load_dotenv()
        # Core
        private_key = (os.getenv("PRIVATE_KEY") or "").strip()
        if private_key.startswith("0x"):
            private_key = private_key[2:]
        if len(private_key) != 64:
            raise ValueError("PRIVATE_KEY must be 64 hex characters (without 0x)")
        # Validate hex
        int(private_key, 16)

        signature_type = int(os.getenv("SIGNATURE_TYPE", "0").strip())
        funder_address = os.getenv("FUNDER_ADDRESS")
        if signature_type == 2 and not funder_address:
            raise ValueError("FUNDER_ADDRESS is required when SIGNATURE_TYPE=2 (Proxy mode)")

        host = os.getenv("POLYMARKET_HOST", "https://clob.polymarket.com").strip()
        chain_id = int(os.getenv("CHAIN_ID", "137").strip())

        # Market
        market_slug = os.getenv("MARKET_SLUG")
        market_token_id = os.getenv("MARKET_TOKEN_ID")
        market_index = os.getenv("MARKET_INDEX")
        if market_index is not None:
            market_index = int(market_index.strip())

        # === V2: WebSocket Settings ===
        wss_enabled = cls._parse_bool(os.getenv("WSS_ENABLED"), True)
        wss_reconnect = float(os.getenv("WSS_RECONNECT_DELAY", "1.0"))
        wss_max_reconnect = float(os.getenv("WSS_MAX_RECONNECT_DELAY", "60.0"))

        # === V2: Multi-Window Spike Detection ===
        spike_windows = _parse_list(os.getenv("SPIKE_WINDOWS_MINUTES"), [10, 30, 60])
        use_volatility_filter = cls._parse_bool(os.getenv("USE_VOLATILITY_FILTER"), True)
        max_volatility_cv = float(os.getenv("MAX_VOLATILITY_CV", "10.0"))
        min_spike_strength = float(os.getenv("MIN_SPIKE_STRENGTH", "5.0"))

        # Strategy (original + updated defaults)
        spike_threshold_pct = float(os.getenv("SPIKE_THRESHOLD_PCT", "8.0"))
        price_history_size = int(os.getenv("PRICE_HISTORY_SIZE", "3600"))
        cooldown_seconds = int(os.getenv("COOLDOWN_SECONDS", "120"))
        max_concurrent_trades = int(os.getenv("MAX_CONCURRENT_TRADES", "1"))
        min_liquidity_requirement = float(os.getenv("MIN_LIQUIDITY_REQUIREMENT", "10"))

        # Risk
        default_trade_size_usd = float(os.getenv("DEFAULT_TRADE_SIZE_USD", "2.0"))
        min_trade_usd = float(os.getenv("MIN_TRADE_USD", "1.0"))
        max_trade_usd = float(os.getenv("MAX_TRADE_USD", "100.0"))
        take_profit_pct = float(os.getenv("TAKE_PROFIT_PCT", "3.0"))
        stop_loss_pct = float(os.getenv("STOP_LOSS_PCT", "2.5"))
        max_hold_seconds = int(os.getenv("MAX_HOLD_SECONDS", "3600"))  # 60 minutes
        slippage_tolerance = float(os.getenv("SLIPPAGE_TOLERANCE", "0.06"))

        # Loop/logging
        price_poll_interval_sec = float(os.getenv("PRICE_POLL_INTERVAL_SEC", "1.0"))
        dry_run = cls._parse_bool(os.getenv("DRY_RUN"), True)
        log_level = os.getenv("LOG_LEVEL", "INFO").strip().upper()
        log_format = os.getenv("LOG_FORMAT", "PLAIN").strip().upper()
        log_file = os.getenv("LOG_FILE", "logs/bot.log").strip()

        # Behavior toggles
        use_gamma_primary = cls._parse_bool(os.getenv("USE_GAMMA_PRIMARY"), False)
        force_first_entry = cls._parse_bool(os.getenv("FORCE_FIRST_ENTRY"), False)
        first_entry_after_seconds = int(os.getenv("FIRST_ENTRY_AFTER_SECONDS", "10"))
        min_history_for_entry = int(os.getenv("MIN_HISTORY_FOR_ENTRY", "10"))
        min_bid_liquidity = float(os.getenv("MIN_BID_LIQUIDITY", "5"))
        min_ask_liquidity = float(os.getenv("MIN_ASK_LIQUIDITY", "5"))
        max_spread_pct = float(os.getenv("MAX_SPREAD_PCT", "1.0"))

        # Construct
        cfg = cls(
            private_key=private_key,
            signature_type=signature_type,
            funder_address=funder_address if signature_type != 0 else None,
            host=host,
            chain_id=chain_id,
            market_slug=market_slug,
            market_token_id=market_token_id,
            market_index=market_index,
            # V2 settings
            wss_enabled=wss_enabled,
            wss_reconnect_delay=wss_reconnect,
            wss_max_reconnect_delay=wss_max_reconnect,
            spike_windows_minutes=spike_windows,
            use_volatility_filter=use_volatility_filter,
            max_volatility_cv=max_volatility_cv,
            min_spike_strength=min_spike_strength,
            # Original settings
            spike_threshold_pct=spike_threshold_pct,
            price_history_size=price_history_size,
            cooldown_seconds=cooldown_seconds,
            max_concurrent_trades=max_concurrent_trades,
            min_liquidity_requirement=min_liquidity_requirement,
            min_bid_liquidity=min_bid_liquidity,
            min_ask_liquidity=min_ask_liquidity,
            max_spread_pct=max_spread_pct,
            default_trade_size_usd=default_trade_size_usd,
            min_trade_usd=min_trade_usd,
            max_trade_usd=max_trade_usd,
            take_profit_pct=take_profit_pct,
            stop_loss_pct=stop_loss_pct,
            max_hold_seconds=max_hold_seconds,
            slippage_tolerance=slippage_tolerance,
            price_poll_interval_sec=price_poll_interval_sec,
            dry_run=dry_run,
            log_level=log_level,
            log_format=log_format,
            log_file=log_file,
            use_gamma_primary=use_gamma_primary,
            force_first_entry=force_first_entry,
            first_entry_after_seconds=first_entry_after_seconds,
            min_history_for_entry=min_history_for_entry,
        )
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
