"""Isolated Bot Session for multi-bot trading with independent configurations.

Each BotSession is a completely independent trading bot with:
- Its own wallet (private key, signature type, funder address)
- Its own market configuration (token_id, slug)
- Its own strategy settings (thresholds, trade sizes, risk params)
- Its own state file and logs

Bots run in parallel and don't share any state.
"""
from __future__ import annotations

import json
import logging
import random
import threading
import time
import uuid
import asyncio  # Added asyncio import
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional, Dict, Any, List, Callable
from copy import deepcopy

from .config import Config, TradingProfile
from .bot import Bot
from .clob_client import Client
from .crypto import encrypt_sensitive_fields, decrypt_sensitive_fields


logger = logging.getLogger(__name__)


# Directory for storing bot configurations
BOT_CONFIG_DIR = Path("data/bots")
BOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

# Global registry of active bot sessions
_active_sessions: Dict[str, "BotSession"] = {}


class ActivityLog:
    """Activity log for a bot session.
    
    Stores activities like spikes, trades, errors for display in the frontend
    ActivityFeed component. Activities are stored in memory with a max limit.
    """
    
    def __init__(self, max_size: int = 500):
        self._activities: List[Dict[str, Any]] = []
        self._max_size = max_size
        self._lock = threading.Lock()
    
    def add(
        self, 
        activity_type: str, 
        message: str, 
        details: Optional[Dict[str, Any]] = None,
        bot_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Add a new activity.
        
        Args:
            activity_type: Type of activity (spike, order, fill, exit, pnl, error, system)
            message: Human-readable message
            details: Additional details dict
            bot_id: Bot ID for this activity
            
        Returns:
            The created activity dict
        """
        activity = {
            "id": f"act_{int(time.time()*1000)}_{random.randint(1000,9999)}",
            "timestamp": int(time.time()),
            "type": activity_type,
            "message": message,
            "details": details or {},
            "bot_id": bot_id,
        }
        
        with self._lock:
            self._activities.insert(0, activity)
            if len(self._activities) > self._max_size:
                self._activities = self._activities[:self._max_size]
        
        return activity
    
    def get_all(self, limit: int = 100, activity_type: str = "all") -> List[Dict[str, Any]]:
        """Get activities.
        
        Args:
            limit: Maximum number of activities to return
            activity_type: Filter by type, or "all" for all types
            
        Returns:
            List of activity dicts (newest first)
        """
        with self._lock:
            if activity_type == "all":
                return self._activities[:limit]
            else:
                filtered = [a for a in self._activities if a["type"] == activity_type]
                return filtered[:limit]
    
    def clear(self) -> None:
        """Clear all activities."""
        with self._lock:
            self._activities = []
    
    def count(self) -> int:
        """Get total activity count."""
        with self._lock:
            return len(self._activities)


@dataclass
class BotConfigData:
    """Configuration data for a bot session.

    This mirrors the Config class but is serializable and can be customized
    per bot. Each bot can have completely different settings.
    """
    # Bot metadata
    bot_id: str
    name: str
    description: str = ""
    created_at: str = ""
    status: str = "stopped"  # stopped, running, paused, error

    # Core API/wallet - each bot can have its own wallet
    private_key: str = ""
    signature_type: int = 0  # 0 = EOA, 2 = Proxy
    funder_address: Optional[str] = None
    host: str = "https://clob.polymarket.com"
    chain_id: int = 137

    # Market selection
    market_slug: Optional[str] = None
    market_token_id: Optional[str] = None
    market_index: Optional[int] = None

    # WebSocket Settings
    wss_enabled: bool = True
    wss_reconnect_delay: float = 1.0
    wss_max_reconnect_delay: float = 60.0

    # Spike Detection
    spike_windows_minutes: List[int] = field(default_factory=lambda: [10, 30, 60])
    use_volatility_filter: bool = True
    max_volatility_cv: float = 10.0
    min_spike_strength: float = 5.0
    spike_threshold_pct: float = 8.0
    price_history_size: int = 3600
    cooldown_seconds: int = 120
    max_concurrent_trades: int = 1
    min_liquidity_requirement: float = 10.0

    # Risk Management
    default_trade_size_usd: float = 2.0
    min_trade_usd: float = 1.0
    max_trade_usd: float = 100.0
    take_profit_pct: float = 3.0
    stop_loss_pct: float = 2.5
    max_hold_seconds: int = 3600
    slippage_tolerance: float = 0.06
    max_balance_per_bot: float = 10.0  # Per-bot max allocation

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
    entry_mode: str = "wait_for_spike"  # immediate_buy, wait_for_spike, delayed_buy
    entry_delay_seconds: int = 0

    # Orderbook guards
    min_bid_liquidity: float = 5.0
    min_ask_liquidity: float = 5.0
    max_spread_pct: float = 1.0

    # Rebuy Strategy
    rebuy_delay_seconds: float = 2.0
    rebuy_strategy: str = "immediate"
    rebuy_drop_pct: float = 0.1

    # Settlement Tracking
    settlement_timeout_seconds: float = 90.0

    # Trading Profile (optional preset)
    trading_profile: Optional[str] = None  # normal, live, edge, custom

    # Custom env variables (for any additional settings)
    custom_env: Dict[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not self.created_at:
            self.created_at = datetime.now(timezone.utc).isoformat()

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        config_overrides: Optional[Dict[str, Any]] = None,
        profile: Optional[str] = None,
    ) -> "BotConfigData":
        """Create a new bot configuration.

        Args:
            name: Bot name
            description: Bot description
            config_overrides: Dictionary of config values to override
            profile: Trading profile to use as base (normal, live, edge)

        Returns:
            New BotConfigData instance
        """
        bot_id = f"bot_{uuid.uuid4().hex[:8]}"

        # Start with defaults - wallet credentials MUST be provided via frontend
        # No environment variables are used for security
        default_private_key = config_overrides.get("private_key") if config_overrides else None
        default_signature_type = config_overrides.get("signature_type", 0) if config_overrides else 0
        default_funder_address = config_overrides.get("funder_address") if config_overrides else None
        
        # Validation: private key is required
        if not default_private_key or default_private_key == "0"*64:
            raise ValueError("Private key is required. Please configure wallet credentials in the bot settings.")
        
        if profile:
            profile_obj = TradingProfile.get_profile(profile)
            # Create a base config from profile
            from .config import Config
            # Start from defaults; rely on overrides provided by frontend
            base_config = Config(
                private_key=default_private_key,
                signature_type=default_signature_type,
                funder_address=default_funder_address,
                host="https://clob.polymarket.com",
                chain_id=137,
            )
            base_config = profile_obj.apply_to_config(base_config)
        else:
            from .config import Config
            base_config = Config(
                private_key=default_private_key,
                signature_type=default_signature_type,
                funder_address=default_funder_address,
                host="https://clob.polymarket.com",
                chain_id=137,
            )

        # Convert Config to dict for BotConfigData
        base_dict = {
            "private_key": base_config.private_key,
            "signature_type": base_config.signature_type,
            "funder_address": base_config.funder_address,
            "host": base_config.host,
            "chain_id": base_config.chain_id,
            "market_slug": base_config.market_slug,
            "market_token_id": base_config.market_token_id,
            "market_index": base_config.market_index,
            "wss_enabled": base_config.wss_enabled,
            "wss_reconnect_delay": base_config.wss_reconnect_delay,
            "wss_max_reconnect_delay": base_config.wss_max_reconnect_delay,
            "spike_windows_minutes": base_config.spike_windows_minutes,
            "use_volatility_filter": base_config.use_volatility_filter,
            "max_volatility_cv": base_config.max_volatility_cv,
            "min_spike_strength": base_config.min_spike_strength,
            "spike_threshold_pct": base_config.spike_threshold_pct,
            "price_history_size": base_config.price_history_size,
            "cooldown_seconds": base_config.cooldown_seconds,
            "max_concurrent_trades": base_config.max_concurrent_trades,
            "min_liquidity_requirement": base_config.min_liquidity_requirement,
            "default_trade_size_usd": base_config.default_trade_size_usd,
            "min_trade_usd": base_config.min_trade_usd,
            "max_trade_usd": base_config.max_trade_usd,
            "take_profit_pct": base_config.take_profit_pct,
            "stop_loss_pct": base_config.stop_loss_pct,
            "max_hold_seconds": base_config.max_hold_seconds,
            "slippage_tolerance": base_config.slippage_tolerance,
            "max_balance_per_bot": base_config.max_balance_per_bot,
            "price_poll_interval_sec": base_config.price_poll_interval_sec,
            "dry_run": base_config.dry_run,
            "log_level": base_config.log_level,
            "log_format": base_config.log_format,
            "log_file": base_config.log_file,
            "use_gamma_primary": base_config.use_gamma_primary,
            "force_first_entry": base_config.force_first_entry,
            "first_entry_after_seconds": base_config.first_entry_after_seconds,
            "min_history_for_entry": base_config.min_history_for_entry,
            "min_bid_liquidity": base_config.min_bid_liquidity,
            "min_ask_liquidity": base_config.min_ask_liquidity,
            "max_spread_pct": base_config.max_spread_pct,
            "rebuy_delay_seconds": base_config.rebuy_delay_seconds,
            "rebuy_strategy": base_config.rebuy_strategy,
            "rebuy_drop_pct": base_config.rebuy_drop_pct,
            "settlement_timeout_seconds": base_config.settlement_timeout_seconds,
        }

        # Apply any config overrides
        if config_overrides:
            base_dict.update(config_overrides)

        return cls(
            bot_id=bot_id,
            name=name,
            description=description,
            trading_profile=profile,
            **base_dict
        )

    def to_config(self) -> Config:
        """Convert BotConfigData to Config object."""
        return Config(
            private_key=self.private_key,
            signature_type=self.signature_type,
            funder_address=self.funder_address,
            host=self.host,
            chain_id=self.chain_id,
            market_slug=self.market_slug,
            market_token_id=self.market_token_id,
            market_index=self.market_index,
            wss_enabled=self.wss_enabled,
            wss_reconnect_delay=self.wss_reconnect_delay,
            wss_max_reconnect_delay=self.wss_max_reconnect_delay,
            spike_windows_minutes=self.spike_windows_minutes,
            use_volatility_filter=self.use_volatility_filter,
            max_volatility_cv=self.max_volatility_cv,
            min_spike_strength=self.min_spike_strength,
            spike_threshold_pct=self.spike_threshold_pct,
            price_history_size=self.price_history_size,
            cooldown_seconds=self.cooldown_seconds,
            max_concurrent_trades=self.max_concurrent_trades,
            min_liquidity_requirement=self.min_liquidity_requirement,
            min_bid_liquidity=self.min_bid_liquidity,
            min_ask_liquidity=self.min_ask_liquidity,
            max_spread_pct=self.max_spread_pct,
            default_trade_size_usd=self.default_trade_size_usd,
            min_trade_usd=self.min_trade_usd,
            max_trade_usd=self.max_trade_usd,
            take_profit_pct=self.take_profit_pct,
            stop_loss_pct=self.stop_loss_pct,
            max_hold_seconds=self.max_hold_seconds,
            slippage_tolerance=self.slippage_tolerance,
            price_poll_interval_sec=self.price_poll_interval_sec,
            dry_run=self.dry_run,
            log_level=self.log_level,
            log_format=self.log_format,
            log_file=f"logs/bot_{self.bot_id}.log",
            use_gamma_primary=self.use_gamma_primary,
            force_first_entry=self.force_first_entry,
            first_entry_after_seconds=self.first_entry_after_seconds,
            min_history_for_entry=self.min_history_for_entry,
            entry_mode=self.entry_mode,
            entry_delay_seconds=self.entry_delay_seconds,
            max_balance_per_bot=self.max_balance_per_bot,
            enable_bankroll_management=True,
            max_allocation_pct=0.8,
            rebuy_delay_seconds=self.rebuy_delay_seconds,
            rebuy_strategy=self.rebuy_strategy,
            rebuy_drop_pct=self.rebuy_drop_pct,
            settlement_timeout_seconds=self.settlement_timeout_seconds,
        )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary (excluding sensitive data for display)."""
        data = asdict(self)
        # Mask private key for display
        if data.get("private_key"):
            pk = data["private_key"]
            data["private_key"] = f"{pk[:6]}...{pk[-4:]}" if len(pk) > 10 else "***"
        return data

    def to_dict_full(self) -> Dict[str, Any]:
        """Convert to dictionary including sensitive data."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BotConfigData":
        """Create BotConfigData from dictionary with proper type coercion.
        
        JSON doesn't preserve Python types, so we need to ensure numeric 
        fields are properly typed to avoid comparison errors like:
        '<' not supported between instances of 'str' and 'int'
        """
        # Make a copy to avoid mutating the input
        coerced = data.copy()
        
        # Integer fields
        int_fields = [
            "signature_type", "chain_id", "market_index", "price_history_size",
            "cooldown_seconds", "max_concurrent_trades", "max_hold_seconds",
            "first_entry_after_seconds", "min_history_for_entry"
        ]
        for field in int_fields:
            if field in coerced and coerced[field] is not None:
                try:
                    coerced[field] = int(coerced[field])
                except (ValueError, TypeError):
                    pass  # Keep original if conversion fails
        
        # Float fields
        float_fields = [
            "wss_reconnect_delay", "wss_max_reconnect_delay", "max_volatility_cv",
            "min_spike_strength", "spike_threshold_pct", "min_liquidity_requirement",
            "default_trade_size_usd", "min_trade_usd", "max_trade_usd",
            "take_profit_pct", "stop_loss_pct", "slippage_tolerance",
            "max_balance_per_bot", "price_poll_interval_sec",
            "min_bid_liquidity", "min_ask_liquidity", "max_spread_pct",
            "rebuy_delay_seconds", "rebuy_drop_pct", "settlement_timeout_seconds"
        ]
        for field in float_fields:
            if field in coerced and coerced[field] is not None:
                try:
                    coerced[field] = float(coerced[field])
                except (ValueError, TypeError):
                    pass  # Keep original if conversion fails
        
        # Boolean fields
        bool_fields = [
            "wss_enabled", "use_volatility_filter", "dry_run",
            "use_gamma_primary", "force_first_entry"
        ]
        for field in bool_fields:
            if field in coerced and coerced[field] is not None:
                if isinstance(coerced[field], str):
                    coerced[field] = coerced[field].lower() in ("true", "1", "yes")
                else:
                    coerced[field] = bool(coerced[field])
        
        # List[int] fields - spike_windows_minutes
        if "spike_windows_minutes" in coerced and coerced["spike_windows_minutes"] is not None:
            try:
                coerced["spike_windows_minutes"] = [int(x) for x in coerced["spike_windows_minutes"]]
            except (ValueError, TypeError):
                pass
        
        return cls(**coerced)

    def save(self) -> None:
        """Save bot configuration to file.
        
        NOTE: Configuration including private keys are stored locally.
        User is responsible for securing access to the data/bots directory.
        All configuration is managed via the frontend UI.
        
        SENSITIVE DATA IS ENCRYPTED BEFORE SAVING.
        """
        config_file = BOT_CONFIG_DIR / f"{self.bot_id}.json"
        # Save full configuration including private key
        # User is responsible for securing access to this directory
        data = self.to_dict_full()
        
        # Encrypt sensitive fields before writing to disk
        data = encrypt_sensitive_fields(data, ["private_key"])
        
        with open(config_file, "w") as f:
            json.dump(data, f, indent=2, default=str)
        logger.info(f"Saved bot config: {self.bot_id} to {config_file}")

    @classmethod
    def load(cls, bot_id: str) -> Optional["BotConfigData"]:
        """Load bot configuration from file.
        
        All configuration including credentials is loaded from the saved file.
        No environment variables are used.
        """
        config_file = BOT_CONFIG_DIR / f"{bot_id}.json"
        if not config_file.exists():
            return None

        with open(config_file, "r") as f:
            data = json.load(f)

        # Decrypt sensitive fields after reading from disk
        data = decrypt_sensitive_fields(data, ["private_key"])

        return cls.from_dict(data)

    @classmethod
    def list_all(cls) -> List["BotConfigData"]:
        """List all bot configurations.
        
        All configuration is loaded from saved files. No environment variables used.
        """
        bots = []
        for config_file in BOT_CONFIG_DIR.glob("*.json"):
            # Skip runtime state files - they have different schema
            if "_runtime.json" in config_file.name:
                continue
            try:
                with open(config_file, "r") as f:
                    data = json.load(f)
                
                # Decrypt sensitive fields after reading from disk
                data = decrypt_sensitive_fields(data, ["private_key"])
                
                bots.append(cls.from_dict(data))
            except Exception as e:
                logger.error(f"Failed to load bot config from {config_file}: {e}")
        return bots

    def delete(self) -> bool:
        """Delete bot configuration file."""
        config_file = BOT_CONFIG_DIR / f"{self.bot_id}.json"
        if config_file.exists():
            config_file.unlink()
            logger.info(f"Deleted bot config: {self.bot_id}")
            return True
        return False


def _safe_parse_datetime(dt: Any) -> Optional[datetime]:
    if not dt:
        return None
    if isinstance(dt, datetime):
        return dt
    try:
        # stored as ISO
        return datetime.fromisoformat(dt)
    except Exception:
        return None


class BotSession:
    """A completely isolated bot session.

    Each BotSession has:
    - Its own configuration (BotConfigData)
    - Its own Bot instance
    - Its own Client instance
    - Its own thread for execution
    - Its own state file

    Multiple BotSessions can run simultaneously with completely different settings.
    """

    def __init__(self, config_data: BotConfigData):
        self.config_data = config_data
        self.config = config_data.to_config()

        # Bot components
        self.bot: Optional[Bot] = None
        self.client: Optional[Client] = None
        self.token_id: Optional[str] = None

        # Thread management
        self.thread: Optional[threading.Thread] = None
        self.stop_event = threading.Event()
        self._event_loop: Optional[asyncio.AbstractEventLoop] = None  # Reference to main event loop

        # State tracking
        self.start_time: Optional[datetime] = None
        self.last_error: Optional[str] = None
        self.status = config_data.status

        # Activity log for frontend ActivityFeed
        self.activity_log = ActivityLog(max_size=500)

        # Market info cache (to avoid hammering gamma API)
        self._market_info_cache: Optional[Dict[str, Any]] = None
        self._market_info_cache_time: Optional[datetime] = None
        self._market_info_cache_ttl = timedelta(minutes=5)  # Cache for 5 minutes

        # 24h price tracking
        self._price_24h_ago: Optional[float] = None
        self._price_24h_timestamp: Optional[datetime] = None

        # Last trade tracking
        self._last_trade_time: Optional[datetime] = None
        self._last_trade_side: Optional[str] = None
        self._prev_position_has: bool = False
        self._prev_position_side: Optional[str] = None

        # Runtime state persistence
        self._runtime_state_file = BOT_CONFIG_DIR / f"{self.config_data.bot_id}_runtime.json"
        self._load_runtime_state()

        # Callbacks
        self.on_state_change: Optional[Callable] = None
        self.on_activity: Optional[Callable] = None
        self.on_trade: Optional[Callable] = None
        self.on_price_update: Optional[Callable] = None
        self.on_position_update: Optional[Callable] = None
        self.on_spike_detected: Optional[Callable] = None
        self.on_target_update: Optional[Callable] = None  # Train of Trade target updates
        self.on_error: Optional[Callable] = None

    def set_event_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        """Set the event loop for scheduling async callbacks."""
        self._event_loop = loop

    def _get_market_info_cached(self) -> Dict[str, Any]:
        """Get market info with caching to avoid rate limits."""
        now = datetime.now()
        if (
            self._market_info_cache is not None
            and self._market_info_cache_time is not None
            and (now - self._market_info_cache_time) < self._market_info_cache_ttl
        ):
            return self._market_info_cache

        if self.client:
            self._market_info_cache = self.client.get_market_info()
            self._market_info_cache_time = now
            return self._market_info_cache
        
        return {"active": True, "closed": False, "question": "Unknown"}

    def _get_market_status(self) -> str:
        """Get real market status from cached market info."""
        info = self._get_market_info_cached()
        if info.get("closed", False):
            return "closed"
        if info.get("outcome"):
            return "resolved"
        if info.get("active", True):
            return "active"
        return "inactive"

    def _update_24h_price(self, current_price: float) -> None:
        """Track price from ~24h ago for change calculation.
        
        Uses a simple approach: store the first price we see, then update
        it every 24h. For more accuracy with limited history, we use
        the oldest price in our 1h buffer as a proxy.
        """
        now = datetime.now()
        
        # If we don't have a 24h price yet, set it
        if self._price_24h_ago is None:
            self._price_24h_ago = current_price
            self._price_24h_timestamp = now
            self._save_runtime_state()
            return
        
        # If 24h has passed, update the reference price
        if self._price_24h_timestamp and (now - self._price_24h_timestamp) >= timedelta(hours=24):
            self._price_24h_ago = current_price
            self._price_24h_timestamp = now
            self._save_runtime_state()

    def _get_24h_price_change(self, current_price: float) -> tuple:
        """Get 24h ago price and change percent.
        
        Returns:
            Tuple of (price_24h_ago, change_percent) or (None, None) if not available
        """
        if self._price_24h_ago is None or self._price_24h_ago == 0:
            return None, None
        
        change_pct = ((current_price - self._price_24h_ago) / self._price_24h_ago) * 100
        return self._price_24h_ago, change_pct

    def _load_runtime_state(self) -> None:
        """Load runtime state (24h baseline + last trade) from disk."""
        try:
            if not self._runtime_state_file.exists():
                return
            with open(self._runtime_state_file, "r") as f:
                data = json.load(f)

            self._price_24h_ago = data.get("price_24h_ago")
            self._price_24h_timestamp = _safe_parse_datetime(data.get("price_24h_timestamp"))
            self._last_trade_time = _safe_parse_datetime(data.get("last_trade_time"))
            self._last_trade_side = data.get("last_trade_side")
        except Exception as e:
            logger.debug(f"Failed to load runtime state for {self.config_data.bot_id}: {e}")

    def _save_runtime_state(self) -> None:
        """Persist runtime state (best-effort)."""
        try:
            payload = {
                "price_24h_ago": self._price_24h_ago,
                "price_24h_timestamp": self._price_24h_timestamp.isoformat() if self._price_24h_timestamp else None,
                "last_trade_time": self._last_trade_time.isoformat() if self._last_trade_time else None,
                "last_trade_side": self._last_trade_side,
            }
            with open(self._runtime_state_file, "w") as f:
                json.dump(payload, f, indent=2)
        except Exception as e:
            logger.debug(f"Failed to save runtime state for {self.config_data.bot_id}: {e}")

    def _record_trade(self, side: str) -> None:
        """Record a trade execution for last trade tracking."""
        self._last_trade_time = datetime.now(timezone.utc)
        self._last_trade_side = side
        self._save_runtime_state()

    @classmethod
    def create(
        cls,
        name: str,
        description: str = "",
        config_overrides: Optional[Dict[str, Any]] = None,
        profile: Optional[str] = None,
    ) -> "BotSession":
        """Create a new bot session with configuration."""
        config_data = BotConfigData.create(
            name=name,
            description=description,
            config_overrides=config_overrides,
            profile=profile,
        )
        config_data.save()
        return cls(config_data)

    @classmethod
    def load(cls, bot_id: str) -> Optional["BotSession"]:
        """Load an existing bot session."""
        config_data = BotConfigData.load(bot_id)
        if not config_data:
            return None
        return cls(config_data)

    @classmethod
    def list_all(cls) -> List["BotSession"]:
        """List all bot sessions."""
        sessions = []
        for config_data in BotConfigData.list_all():
            sessions.append(cls(config_data))
        return sessions

    def reload_config(self) -> None:
        """Reload configuration from file."""
        config_data = BotConfigData.load(self.config_data.bot_id)
        if config_data:
            self.config_data = config_data
            self.config = config_data.to_config()

    def save_config(self) -> None:
        """Save current configuration to file."""
        self.config_data.save()

    def update_config(self, updates: Dict[str, Any]) -> None:
        """Update bot configuration."""
        for key, value in updates.items():
            if hasattr(self.config_data, key):
                setattr(self.config_data, key, value)
            elif hasattr(self.config, key):
                setattr(self.config, key, value)

        # Update trading profile if specified
        if "trading_profile" in updates:
            profile = updates["trading_profile"]
            if profile:
                profile_obj = TradingProfile.get_profile(profile)
                self.config = profile_obj.apply_to_config(self.config)

        self.save_config()

    def start(self) -> bool:
        """Start the bot session."""
        if self.status == "running":
            logger.warning(f"Bot {self.config_data.bot_id} is already running")
            return True

        try:
            # Reset stop event
            self.stop_event.clear()
            
            # Regenerate config from config_data to pick up any updates
            self.config = self.config_data.to_config()

            # Create client
            self.client = Client(self.config)

            # Resolve token ID
            if self.config.market_token_id:
                self.token_id = self.config.market_token_id
            else:
                self.token_id = self.client.resolve_token_id()

            # Create bot
            self.bot = Bot(self.config, self.client)

            # Set up callbacks for WebSocket broadcasting
            self.bot._price_update_callback = self._on_price_update
            self.bot._position_update_callback = self._on_position_update
            self.bot._spike_detected_callback = self._on_spike_detected
            self.bot._target_update_callback = self._on_target_update

            # Update status
            self.status = "running"
            self.config_data.status = "running"
            self.start_time = datetime.now(timezone.utc)
            self.last_error = None
            self.save_config()

            # Start bot in background thread
            self.thread = threading.Thread(
                target=self._run_bot,
                daemon=True,
                name=f"Bot-{self.config_data.bot_id}",
            )
            self.thread.start()

            logger.info(f"Started bot session: {self.config_data.bot_id} ({self.config_data.name})")

            if self.on_state_change:
                self.on_state_change(self.config_data.bot_id, {"status": "running"})

            return True

        except Exception as e:
            import traceback
            logger.error(f"Failed to start bot {self.config_data.bot_id}: {e}\n{traceback.format_exc()}")
            self.status = "error"
            self.config_data.status = "error"
            self.last_error = str(e)
            self.save_config()
            return False

    def stop(self) -> bool:
        """Stop the bot session."""
        if self.status != "running":
            return True

        self.stop_event.set()
        self.status = "stopped"
        self.config_data.status = "stopped"
        self.save_config()

        # Wait for thread to finish
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5.0)

        logger.info(f"Stopped bot session: {self.config_data.bot_id}")

        if self.on_state_change:
            self.on_state_change(self.config_data.bot_id, {"status": "stopped"})

        return True

    def pause(self) -> bool:
        """Pause the bot session."""
        if self.status != "running":
            return False

        self.status = "paused"
        self.config_data.status = "paused"
        self.save_config()

        if self.on_state_change:
            self.on_state_change(self.config_data.bot_id, {"status": "paused"})

        return True

    def resume(self) -> bool:
        """Resume the bot session."""
        if self.status != "paused":
            return False

        self.status = "running"
        self.config_data.status = "running"
        self.save_config()

        if self.on_state_change:
            self.on_state_change(self.config_data.bot_id, {"status": "running"})

        return True

    def delete(self) -> bool:
        """Delete the bot session (stops if running)."""
        if self.status == "running":
            self.stop()

        return self.config_data.delete()

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        # Get current price if bot is running
        current_price = None
        if self.bot and hasattr(self.bot, "last_price") and self.bot.last_price:
            current_price = self.bot.last_price
            # Update 24h tracking whenever we have a price
            self._update_24h_price(current_price)

        # Get market name from slug or use a default
        market_name = self.config_data.market_slug or "Unknown Market"
        if self.config_data.market_slug:
            # Convert slug to readable name
            market_name = self.config_data.market_slug.replace("-", " ").title()

        status = {
            "bot_id": self.config_data.bot_id,
            "name": self.config_data.name,
            "description": self.config_data.description,
            "status": self.status,
            "created_at": self.config_data.created_at,
            "trading_profile": self.config_data.trading_profile,
            "market_slug": self.config_data.market_slug,
            "token_id": self.token_id,
            "wallet_address": self.client.get_wallet_address() if self.client else "N/A",
            "usdc_balance": self.client.get_usdc_balance() if self.client else 0.0,
            "max_balance_per_bot": self.config_data.max_balance_per_bot,
            "dry_run": self.config_data.dry_run,
            "signature_type": "EOA" if self.config_data.signature_type == 0 else "Proxy",
            # Strategy config fields needed by frontend
            "spike_threshold_pct": self.config_data.spike_threshold_pct,
            "take_profit_pct": self.config_data.take_profit_pct,
            "stop_loss_pct": self.config_data.stop_loss_pct,
            "trade_size_usd": self.config_data.default_trade_size_usd,
            # Current price at bot level (for market display)
            "current_price": current_price,
            
            # NEW FIELDS for frontend alignment
            # Market information
            "market_name": market_name,
            "market_status": self._get_market_status(),
            "price_24h_ago": None,
            "price_24h_change_pct": None,
            
            # Price tracking
            "last_price_time": self.bot.last_price_time.timestamp() if self.bot and self.bot.last_price_time else None,
            "last_trade_time": self._last_trade_time.timestamp() if self._last_trade_time else None,
            "last_trade_side": self._last_trade_side,
            "total_trade_count": self.bot.total_trades if self.bot and hasattr(self.bot, "total_trades") else 0,
        }

        # Add 24h change fields if price available
        if current_price is not None:
            price_24h, change_pct = self._get_24h_price_change(current_price)
            status["price_24h_ago"] = price_24h
            status["price_24h_change_pct"] = change_pct

        # Add uptime if running
        if self.start_time and self.status == "running":
            status["uptime_seconds"] = (datetime.now(timezone.utc) - self.start_time).total_seconds()

        # Add position info if bot is running
        if self.bot and self.bot.open_position:
            pos = self.bot.open_position
            pos_price = current_price if current_price else pos.entry_price
            pnl = pos.calculate_pnl(pos_price)

            status["position"] = {
                "has_position": True,
                "side": pos.side,
                "entry_price": pos.entry_price,
                "current_price": pos_price,
                "amount_usd": pos.amount_usd,
                "age_seconds": pos.age_seconds,
                "pnl_pct": pnl["pnl_pct"],
                "pnl_usd": pnl["pnl_usd"],
                # Additional fields for frontend display
                "shares": getattr(pos, "expected_shares", 0),
                "entry_time": pos.entry_time.isoformat() if hasattr(pos, 'entry_time') else None,
                "pending_settlement": getattr(pos, "pending_settlement", False),
                "max_hold_seconds": self.config_data.max_hold_seconds,
                "take_profit_pct": self.config_data.take_profit_pct,
                "stop_loss_pct": self.config_data.stop_loss_pct,
            }
        else:
            status["position"] = {"has_position": False}

        # Add session stats if bot is running
        if self.bot:
            status["session_stats"] = {
                "realized_pnl": self.bot.realized_pnl if hasattr(self.bot, "realized_pnl") else 0.0,
                "total_trades": self.bot.total_trades if hasattr(self.bot, "total_trades") else 0,
                "winning_trades": self.bot.winning_trades if hasattr(self.bot, "winning_trades") else 0,
            }

            # Add spikes detected if available
            status["spikes_detected"] = (
                self.bot.spikes_detected if hasattr(self.bot, "spikes_detected") else 0
            )

            # Add spike detection details for frontend
            if current_price:
                max_spike, spike_stats = self.bot._compute_spike_multi_window(current_price)

                # Build windows data for multi-window analysis
                windows = []
                if hasattr(self.bot, 'history') and len(self.bot.history) > 0:
                    now = datetime.now(timezone.utc)
                    windows_seconds = self.bot.cfg.get_spike_windows_seconds()
                    
                    for window_sec in windows_seconds:
                        cutoff = now - timedelta(seconds=window_sec)
                        window_prices = [(ts, p) for ts, p in self.bot.history if ts >= cutoff and p > 0]
                        
                        if len(window_prices) >= 2:
                            base_price = window_prices[0][1]
                            change_pct = (current_price - base_price) / base_price * 100.0
                            
                            windows.append({
                                "window_sec": window_sec,
                                "base_price": base_price,
                                "current_price": current_price,
                                "change_pct": change_pct,
                            })

                status["spike_detection"] = {
                    "is_active": self.status == "running",
                    "threshold": self.config_data.spike_threshold_pct,
                    "max_change_pct": max_spike,
                    "max_change_window_sec": spike_stats.get("window_seconds", 0),
                    "volatility_cv": spike_stats.get("volatility_cv", 0.0),
                    "max_volatility_cv": self.config_data.max_volatility_cv,
                    "is_volatility_filtered": spike_stats.get("volatility_filtered", False),
                    "history_size": len(self.bot.history) if hasattr(self.bot, 'history') else 0,
                    "max_history_size": self.config_data.price_history_size,
                    "windows": windows,
                }
            else:
                # Provide default spike detection structure when no price available
                status["spike_detection"] = {
                    "is_active": self.status == "running",
                    "threshold": self.config_data.spike_threshold_pct,
                    "max_change_pct": 0.0,
                    "max_change_window_sec": 0,
                    "volatility_cv": 0.0,
                    "max_volatility_cv": self.config_data.max_volatility_cv,
                    "is_volatility_filtered": False,
                    "history_size": 0,
                    "max_history_size": self.config_data.price_history_size,
                    "windows": [],
                }

            # Add price history sample for charts (last 100 points)
            if hasattr(self.bot, 'history') and len(self.bot.history) > 0:
                recent_history = list(self.bot.history)[-100:]
                status["price_history_sample"] = [
                    {"time": int(ts.timestamp()), "price": price}
                    for ts, price in recent_history
                ]
            else:
                status["price_history_sample"] = []

        # Add error if any
        if self.last_error:
            status["error"] = self.last_error

        return status

    def _on_price_update(self, price_data: Dict[str, Any]) -> None:
        """Handle price update from bot for WebSocket broadcasting."""
        if self.on_price_update:
            try:
                if self._event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_price_update(self.config_data.bot_id, price_data),
                        self._event_loop
                    )
                else:
                    logger.warning("Event loop not set, cannot broadcast price update")
            except Exception as e:
                logger.warning(f"Price update broadcast failed: {e}")

    def _on_position_update(self, position_data: Dict[str, Any]) -> None:
        """Handle position update from bot for WebSocket broadcasting."""
        # Auto-trade detection: record last trade when position flips/opens
        try:
            has_pos = bool(position_data.get("has_position", False))
            side = position_data.get("side")
            if has_pos and (not self._prev_position_has):
                # Position opened => trade side is entry side
                if side:
                    self._record_trade(str(side).upper())
            elif (not has_pos) and self._prev_position_has:
                # Position closed => infer exit side from previous position side
                if self._prev_position_side:
                    exit_side = "SELL" if str(self._prev_position_side).upper() == "BUY" else "BUY"
                    self._record_trade(exit_side)

            self._prev_position_has = has_pos
            self._prev_position_side = side if has_pos else None
        except Exception:
            pass

        if self.on_position_update:
            try:
                if self._event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_position_update(self.config_data.bot_id, position_data),
                        self._event_loop
                    )
                else:
                    logger.warning("Event loop not set, cannot broadcast position update")
            except Exception as e:
                logger.warning(f"Position update broadcast failed: {e}")

    def _on_spike_detected(self, spike_data: Dict[str, Any]) -> None:
        """Handle spike detection from bot for WebSocket broadcasting."""
        # Add to activity log
        direction = "up" if spike_data.get("direction") == "up" else "down"
        spike_pct = spike_data.get("spike_pct", 0)
        action = spike_data.get("action_taken", spike_data.get("reason", ""))
        message = f"{'↗️' if direction == 'up' else '↘️'} Spike {spike_pct:.1f}%"
        if action:
            message += f" → {action}"
        
        activity = self.activity_log.add(
            "spike",
            message,
            details=spike_data,
            bot_id=self.config_data.bot_id
        )
        
        # Broadcast via WebSocket
        if self.on_spike_detected:
            try:
                if self._event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_spike_detected(self.config_data.bot_id, spike_data),
                        self._event_loop
                    )
                else:
                    logger.warning("Event loop not set, cannot broadcast spike detection")
            except Exception as e:
                logger.warning(f"Spike detection broadcast failed: {e}")
        
        # Also broadcast activity
        if self.on_activity:
            try:
                if self._event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_activity(self.config_data.bot_id, activity),
                        self._event_loop
                    )
            except Exception as e:
                logger.warning(f"Activity broadcast failed: {e}")

    def _on_target_update(self, target_data: Dict[str, Any]) -> None:
        """Handle target update from bot for WebSocket broadcasting (Train of Trade strategy)."""
        # Add to activity log
        if target_data.get("target"):
            target = target_data["target"]
            action = target.get("action", "BUY")
            price = target.get("price", 0)
            reason = target.get("reason", "")
            message = f"Target set: {action} @ ${price:.4f}"
            if reason:
                message += f" ({reason})"
            
            activity = self.activity_log.add(
                "signal",
                message,
                details=target_data,
                bot_id=self.config_data.bot_id
            )
            
            # Broadcast activity
            if self.on_activity:
                try:
                    if self._event_loop:
                        asyncio.run_coroutine_threadsafe(
                            self.on_activity(self.config_data.bot_id, activity),
                            self._event_loop
                        )
                except Exception as e:
                    logger.warning(f"Activity broadcast failed: {e}")
        
        # Broadcast target update via WebSocket
        if self.on_target_update:
            try:
                if self._event_loop:
                    asyncio.run_coroutine_threadsafe(
                        self.on_target_update(self.config_data.bot_id, target_data),
                        self._event_loop
                    )
                else:
                    logger.warning("Event loop not set, cannot broadcast target update")
            except Exception as e:
                logger.warning(f"Target update broadcast failed: {e}")

    def execute_trade(self, side: str, amount_usd: float) -> Dict[str, Any]:
        """Execute a manual trade."""
        if not self.client or not self.token_id:
            logger.error(f"Cannot trade: client={self.client}, token_id={self.token_id}")
            self.activity_log.add(
                "error",
                f"Trade failed: Bot not running",
                bot_id=self.config_data.bot_id
            )
            return {"success": False, "error": "Bot not running"}

        # DRY RUN MODE: Simulate the trade without calling the real API
        if self.config_data.dry_run:
            logger.info(f"[DRY-RUN] Simulating manual {side} ${amount_usd:.2f}")
            
            # Get current price for position tracking
            current_price = self.bot.last_price if self.bot and self.bot.last_price else 0.50
            order_id = f"dry_run_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}"
            
            # Update position state for simulated trades
            if self.bot:
                if side.upper() == "BUY":
                    from .bot import Position
                    self.bot.open_position = Position(
                        side="BUY",
                        entry_price=current_price,
                        entry_time=datetime.now(timezone.utc),
                        amount_usd=amount_usd,
                    )
                    logger.info(f"[DRY-RUN] Created simulated BUY position @ ${current_price:.4f}")
                    self.bot._set_sell_target(current_price, reason="after_buy")
                elif side.upper() == "SELL":
                    had_position = self.bot.open_position is not None
                    if had_position:
                        self.bot.open_position = None
                        logger.info(f"[DRY-RUN] Closed simulated position")
                        drop_pct = max(self.config_data.rebuy_drop_pct, 0.5)
                        target_price = current_price * (1 - drop_pct / 100)
                        self.bot._set_buy_target(target_price, reason="after_sell")
            
            # Record trade for tracking
            self._record_trade(side.upper())
            
            # Add to activity log
            activity = self.activity_log.add(
                "order",
                f"[DRY-RUN] {side.upper()} ${amount_usd:.2f} simulated (order: {order_id[:8]}...)",
                details={"side": side, "amount_usd": amount_usd, "order_id": order_id, "dry_run": True},
                bot_id=self.config_data.bot_id
            )
            
            # Broadcast position update via WebSocket (async-safe)
            if self.on_position_update and self._event_loop:
                try:
                    position_data = self._get_position_dict()
                    asyncio.run_coroutine_threadsafe(
                        self.on_position_update(self.config_data.bot_id, position_data),
                        self._event_loop
                    )
                except Exception as e:
                    logger.warning(f"Position update broadcast failed: {e}")
            
            # Broadcast activity via WebSocket (async-safe)
            if self.on_activity and self._event_loop:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.on_activity(self.config_data.bot_id, activity),
                        self._event_loop
                    )
                except Exception as e:
                    logger.warning(f"Activity broadcast failed: {e}")
            
            return {
                "success": True,
                "order_id": order_id,
                "side": side,
                "amount_usd": amount_usd,
                "dry_run": True,
            }

        # REAL TRADE: Call the actual API
        try:
            result = self.client.place_market_order(
                side=side.upper(),
                amount_usd=amount_usd,
                token_id=self.token_id,
            )

            if result.success:
                # Record trade for last-trade tracking
                self._record_trade(side.upper())

                # Extract order_id from response dict
                order_id = result.response.get("orderID") or result.response.get("order_id") or "N/A"
                
                # Get current price for position tracking
                current_price = self.bot.last_price if self.bot else 0.001
                
                # Update position state for manual trades
                if self.bot:
                    if side.upper() == "BUY":
                        # Create new position
                        from .bot import Position
                        self.bot.open_position = Position(
                            side="BUY",
                            entry_price=current_price,
                            entry_time=datetime.now(timezone.utc),
                            amount_usd=amount_usd,
                        )
                        logger.info(f"Manual BUY: Created position @ ${current_price:.4f}")
                        
                        # TRAIN OF TRADE: After BUY, set SELL target at take profit
                        self.bot._set_sell_target(current_price, reason="after_buy")
                        logger.info(f"Train of Trade: Set SELL target after manual BUY")
                        
                    elif side.upper() == "SELL":
                        # Close existing position
                        had_position = self.bot.open_position is not None
                        self.bot.open_position = None
                        logger.info(f"Manual SELL: Closed position")
                        
                        # TRAIN OF TRADE: After SELL, use wait_for_drop strategy
                        # DON'T use immediate rebuy here - it causes race conditions
                        # Instead, set a BUY target slightly below current price
                        if had_position:
                            # Always use wait_for_drop for manual sells to avoid immediate re-trigger
                            drop_pct = max(self.config_data.rebuy_drop_pct, 0.5)  # At least 0.5% drop
                            target_price = current_price * (1 - drop_pct / 100)
                            self.bot._set_buy_target(target_price, reason="after_sell")
                            logger.info(f"Train of Trade: Set BUY target @ ${target_price:.4f} (wait for {drop_pct}% drop)")
                
                # Add to activity log
                activity = self.activity_log.add(
                    "order",
                    f"{side.upper()} ${amount_usd:.2f} executed (order: {order_id[:8]}...)",
                    details={"side": side, "amount_usd": amount_usd, "order_id": order_id},
                    bot_id=self.config_data.bot_id
                )
                
                # Broadcast position update via WebSocket (async-safe)
                if self.on_position_update and self._event_loop:
                    try:
                        position_data = self._get_position_dict()
                        asyncio.run_coroutine_threadsafe(
                            self.on_position_update(self.config_data.bot_id, position_data),
                            self._event_loop
                        )
                    except Exception as e:
                        logger.warning(f"Position update broadcast failed: {e}")
                
                # Broadcast activity via WebSocket (async-safe)
                if self.on_activity and self._event_loop:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.on_activity(self.config_data.bot_id, activity),
                            self._event_loop
                        )
                    except Exception as e:
                        logger.warning(f"Activity broadcast failed: {e}")

                return {
                    "success": True,
                    "order_id": order_id,
                    "side": side,
                    "amount_usd": amount_usd,
                }
            else:
                error_msg = result.response.get("error") or result.response.get("message") or "Order failed"
                self.activity_log.add(
                    "error",
                    f"Trade failed: {error_msg}",
                    details={"side": side, "amount_usd": amount_usd, "error": error_msg},
                    bot_id=self.config_data.bot_id
                )
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            logger.error(f"Manual trade failed: {e}")
            self.activity_log.add(
                "error",
                f"Trade exception: {str(e)}",
                bot_id=self.config_data.bot_id
            )
            return {"success": False, "error": str(e)}

    def close_position(self) -> Dict[str, Any]:
        """Close the current position."""
        if not self.bot or not self.bot.open_position:
            return {"success": False, "error": "No open position"}

        position = self.bot.open_position
        side = "SELL" if position.side == "BUY" else "BUY"

        # DRY RUN MODE: Simulate closing without calling the real API
        if self.config_data.dry_run:
            logger.info(f"[DRY-RUN] Simulating close position: {side} ${position.amount_usd:.2f}")
            
            self.bot.open_position = None
            self._record_trade(side)
            
            # Add activity log
            activity = self.activity_log.add(
                "order",
                f"[DRY-RUN] Position closed: {side} ${position.amount_usd:.2f}",
                details={"side": side, "amount_usd": position.amount_usd, "dry_run": True},
                bot_id=self.config_data.bot_id
            )
            
            # Broadcast position update via WebSocket (async-safe)
            if self.on_position_update and self._event_loop:
                try:
                    position_data = self._get_position_dict()
                    asyncio.run_coroutine_threadsafe(
                        self.on_position_update(self.config_data.bot_id, position_data),
                        self._event_loop
                    )
                except Exception as e:
                    logger.warning(f"Position update broadcast failed: {e}")
            
            # Broadcast activity via WebSocket (async-safe)
            if self.on_activity and self._event_loop:
                try:
                    asyncio.run_coroutine_threadsafe(
                        self.on_activity(self.config_data.bot_id, activity),
                        self._event_loop
                    )
                except Exception as e:
                    logger.warning(f"Activity broadcast failed: {e}")
            
            return {"success": True, "side": side, "amount_usd": position.amount_usd, "dry_run": True}

        # REAL TRADE: Call the actual API
        try:
            result = self.client.place_market_order(
                side=side,
                amount_usd=position.amount_usd,
                token_id=self.token_id,
            )

            if result.success:
                self.bot.open_position = None
                self._record_trade(side)
                
                # Add activity log
                activity = self.activity_log.add(
                    "order",
                    f"Position closed: {side} ${position.amount_usd:.2f}",
                    details={"side": side, "amount_usd": position.amount_usd},
                    bot_id=self.config_data.bot_id
                )
                
                # Broadcast position update via WebSocket (async-safe)
                if self.on_position_update and self._event_loop:
                    try:
                        position_data = self._get_position_dict()
                        asyncio.run_coroutine_threadsafe(
                            self.on_position_update(self.config_data.bot_id, position_data),
                            self._event_loop
                        )
                    except Exception as e:
                        logger.warning(f"Position update broadcast failed: {e}")
                
                # Broadcast activity via WebSocket (async-safe)
                if self.on_activity and self._event_loop:
                    try:
                        asyncio.run_coroutine_threadsafe(
                            self.on_activity(self.config_data.bot_id, activity),
                            self._event_loop
                        )
                    except Exception as e:
                        logger.warning(f"Activity broadcast failed: {e}")
                
                return {"success": True, "side": side, "amount_usd": position.amount_usd}
            else:
                return {"success": False, "error": result.error or "Close failed"}

        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return {"success": False, "error": str(e)}

    def _run_bot(self):
        """Run the bot in background thread."""
        try:
            if not self.bot:
                return

            logger.info(f"Starting bot thread for {self.config_data.bot_id}")

            # Run the bot
            self.bot.run(stop_event=self.stop_event)

        except Exception as e:
            logger.error(f"Bot thread error for {self.config_data.bot_id}: {e}")
            self.status = "error"
            self.config_data.status = "error"
            self.last_error = str(e)
            self.save_config()

            if self.on_activity:
                self.on_activity(self.config_data.bot_id, {
                    "type": "error",
                    "message": f"Bot error: {str(e)}",
                })
        finally:
            # Update status when thread exits
            if not self.stop_event.is_set():
                self.status = "stopped"
                self.config_data.status = "stopped"
                self.save_config()


# === Utility Functions ===


def create_bot(
    name: str,
    description: str = "",
    private_key: Optional[str] = None,
    signature_type: int = 0,
    funder_address: Optional[str] = None,
    market_slug: Optional[str] = None,
    market_token_id: Optional[str] = None,
    profile: Optional[str] = None,
    trade_size_usd: Optional[float] = None,
    dry_run: bool = True,
    **kwargs
) -> Optional[BotSession]:
    """Create a new bot session with common parameters.

    This is the main function for creating bots with custom configurations.

    Args:
        name: Bot name
        description: Bot description
        private_key: Private key for this bot (if different from default)
        signature_type: 0 for EOA, 2 for Gnosis Proxy
        funder_address: Funder address for Proxy mode
        market_slug: Market slug
        market_token_id: Market token ID
        profile: Trading profile (normal, live, edge)
        trade_size_usd: Trade size override
        dry_run: Dry run mode
        **kwargs: Any other config overrides

    Returns:
        BotSession instance or None if failed
    """
    config_overrides = {
        "market_slug": market_slug,
        "market_token_id": market_token_id,
        "dry_run": dry_run,
        **kwargs
    }

    if private_key:
        config_overrides["private_key"] = private_key

    if signature_type is not None:
        config_overrides["signature_type"] = signature_type

    if funder_address:
        config_overrides["funder_address"] = funder_address

    if trade_size_usd is not None:
        config_overrides["default_trade_size_usd"] = trade_size_usd

    try:
        session = BotSession.create(
            name=name,
            description=description,
            config_overrides=config_overrides,
            profile=profile,
        )
        _active_sessions[session.config_data.bot_id] = session
        return session
    except Exception as e:
        logger.error(f"Failed to create bot: {e}")
        return None


def list_bots() -> List[Dict[str, Any]]:
    """List all bot sessions with their status."""
    # Get all config IDs from disk
    configs = BotConfigData.list_all()
    
    # Sync with memory (load missing ones)
    for config in configs:
        if config.bot_id not in _active_sessions:
            _active_sessions[config.bot_id] = BotSession(config)
            
    # Return status from active sessions
    # Filter to ensure we only return bots that still exist on disk
    existing_ids = {c.bot_id for c in configs}
    return [s.get_status() for s in _active_sessions.values() if s.config_data.bot_id in existing_ids]


def get_bot(bot_id: str) -> Optional[BotSession]:
    """Get a bot session by ID (using in-memory cache if available)."""
    if bot_id in _active_sessions:
        return _active_sessions[bot_id]
    
    session = BotSession.load(bot_id)
    if session:
        _active_sessions[bot_id] = session
    return session


def delete_bot(bot_id: str) -> bool:
    """Delete a bot session."""
    # Remove from active sessions first to stop it if running
    if bot_id in _active_sessions:
        session = _active_sessions[bot_id]
        if session.status == "running":
            session.stop()
        del _active_sessions[bot_id]
    
    # Load just to delete if not in memory (rare but possible)
    session = BotSession.load(bot_id)
    if session:
        return session.delete()
    return False
