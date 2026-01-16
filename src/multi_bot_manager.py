"""Multi-bot manager for running multiple trading bots in parallel.

Manages multiple bot instances, each trading on a different market
with its own configuration. Provides unified state tracking and control.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any, Callable
from pathlib import Path
import json

from .config import Config, TradingProfile
from .bot import Bot, Position
from .clob_client import Client


logger = logging.getLogger(__name__)


@dataclass
class Activity:
    """Activity log entry."""
    id: str
    bot_id: str
    timestamp: float
    type: str  # signal, spike, order, fill, confirm, exit, pnl, cooldown, error, system
    message: str
    details: Optional[Dict[str, Any]] = None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "bot_id": self.bot_id,
            "timestamp": self.timestamp,
            "type": self.type,
            "message": self.message,
            "details": self.details,
        }


@dataclass
class BotInstance:
    """A single bot instance with its own state."""

    bot_id: str
    config: Config
    bot: Optional[Bot] = None
    client: Optional[Client] = None
    status: str = "stopped"  # running, stopped, paused, error
    thread: Optional[threading.Thread] = None
    stop_event: threading.Event = field(default_factory=threading.Event)

    # Market info
    market_name: Optional[str] = None
    token_id: Optional[str] = None

    # State tracking
    start_time: Optional[datetime] = None
    last_update: Optional[datetime] = None

    # Balance allocation
    max_allocated_balance: float = 10.0  # Maximum USD this bot can use
    current_allocation: float = 0.0  # Currently allocated (active positions)

    # Callbacks for broadcasting
    on_state_change: Optional[Callable] = None
    on_activity: Optional[Callable] = None
    on_price_update: Optional[Callable] = None
    on_trade: Optional[Callable] = None


class BankrollManager:
    """Manages bankroll distribution across multiple bot instances."""

    def __init__(self, total_bankroll: float, max_allocation_pct: float = 0.8):
        """Initialize bankroll manager.

        Args:
            total_bankroll: Total available USDC balance
            max_allocation_pct: Maximum % of bankroll to allocate (keep reserve)
        """
        self.total_bankroll = total_bankroll
        self.max_allocation_pct = max_allocation_pct
        self.max_allocatable = total_bankroll * max_allocation_pct
        self.reserve = total_bankroll - self.max_allocatable

        # Track allocations per bot
        self.bot_allocations: Dict[str, float] = {}
        self.bot_pnl: Dict[str, float] = {}

        logger.info(f"BankrollManager initialized: ${total_bankroll:.2f} total, ${self.max_allocatable:.2f} allocatable")

    def allocate_to_bot(self, bot_id: str, trade_size: float) -> bool:
        """Check if bot can trade with given amount.

        Returns:
            True if allocation available, False otherwise
        """
        current_total = sum(self.bot_allocations.values())

        if current_total + trade_size <= self.max_allocatable:
            # Track allocation (actual balance check happens at trade time)
            self.bot_allocations[bot_id] = self.bot_allocations.get(bot_id, 0) + trade_size
            return True

        logger.warning(f"Insufficient bankroll for {bot_id}: need ${trade_size:.2f}, available ${self.max_allocatable - current_total:.2f}")
        return False

    def release_from_bot(self, bot_id: str, amount: float):
        """Release allocation from bot (after position closed)."""
        if bot_id in self.bot_allocations:
            self.bot_allocations[bot_id] = max(0, self.bot_allocations[bot_id] - amount)

    def update_pnl(self, bot_id: str, pnl: float):
        """Update realized P&L for a bot."""
        self.bot_pnl[bot_id] = self.bot_pnl.get(bot_id, 0) + pnl

    def get_bot_pnl(self, bot_id: str) -> float:
        """Get realized P&L for a specific bot."""
        return self.bot_pnl.get(bot_id, 0)

    def get_total_pnl(self) -> float:
        """Get total realized P&L across all bots."""
        return sum(self.bot_pnl.values())

    def get_allocation_status(self) -> Dict[str, Any]:
        """Get current allocation status."""
        allocated = sum(self.bot_allocations.values())
        available = self.max_allocatable - allocated

        return {
            "total_bankroll": self.total_bankroll,
            "max_allocatable": self.max_allocatable,
            "allocated": allocated,
            "available": available,
            "reserve": self.reserve,
            "utilization_pct": (allocated / self.max_allocatable * 100) if self.max_allocatable > 0 else 0,
            "total_pnl": self.get_total_pnl(),
            "bot_count": len(self.bot_allocations),
        }


class MultiBotManager:
    """Manages multiple bot instances running in parallel."""

    def __init__(self, base_config: Optional[Config] = None):
        self.base_config = base_config
        self.bots: Dict[str, BotInstance] = {}
        self._lock = threading.Lock()
        self._activities: deque[Activity] = deque(maxlen=1000)
        self._activity_callbacks: List[Callable] = []

        # Track overall wallet balance
        self._wallet_balance: float = 0.0

        # Bankroll management
        self.bankroll_manager: Optional[BankrollManager] = None

        logger.info("MultiBotManager initialized")

    def create_bot(
        self,
        market_identifier: str,
        profile: str = "normal",
        trade_size_usd: Optional[float] = None,
        max_balance_per_bot: Optional[float] = None,
        custom_config: Optional[Dict[str, Any]] = None,
    ) -> Optional[str]:
        """Create a new bot instance.

        Args:
            market_identifier: Market slug or token_id
            profile: Trading profile name (normal, live, edge, custom)
            trade_size_usd: Override trade size
            max_balance_per_bot: Maximum USD this bot can allocate (default: from config)
            custom_config: Optional custom config overrides

        Returns:
            Bot ID if created successfully, None otherwise
        """
        bot_id = f"bot_{uuid.uuid4().hex[:8]}"

        try:
            # Load base config if not provided
            if self.base_config is None:
                raise RuntimeError("Provide base_config to MultiBotManager; env-based config is disabled.")
            else:
                base = self.base_config

            # Apply trading profile
            profile_obj = TradingProfile.get_profile(profile)
            config = profile_obj.apply_to_config(base)

            # Apply market identifier
            if market_identifier.startswith("0x") or len(market_identifier) > 20:
                config.market_token_id = market_identifier
                config.market_slug = None
            else:
                config.market_slug = market_identifier
                config.market_token_id = None

            # Override trade size if specified
            if trade_size_usd is not None:
                config.default_trade_size_usd = trade_size_usd

            # Apply custom config overrides
            if custom_config:
                for key, value in custom_config.items():
                    if hasattr(config, key):
                        setattr(config, key, value)

            # Determine max balance for this bot
            max_balance = max_balance_per_bot if max_balance_per_bot is not None else config.max_balance_per_bot

            # Create bot instance with per-bot balance limit
            bot_instance = BotInstance(
                bot_id=bot_id,
                config=config,
                max_allocated_balance=max_balance,
            )

            # Setup callbacks
            bot_instance.on_state_change = self._on_state_change
            bot_instance.on_activity = self._on_activity
            bot_instance.on_price_update = self._on_price_update
            bot_instance.on_trade = self._on_trade

            with self._lock:
                self.bots[bot_id] = bot_instance

            self._log_activity(
                bot_id=bot_id,
                activity_type="system",
                message=f"Bot created for market: {market_identifier} (profile: {profile}, max_balance: ${max_balance:.2f})",
            )

            logger.info(f"Created bot {bot_id} for market {market_identifier} with max_balance=${max_balance:.2f}")
            return bot_id

        except Exception as e:
            logger.error(f"Failed to create bot: {e}")
            return None

    async def start_bot(self, bot_id: str) -> bool:
        """Start a bot instance."""
        with self._lock:
            if bot_id not in self.bots:
                return False

            instance = self.bots[bot_id]

            if instance.status == "running":
                return True

            # Reset stop event
            instance.stop_event.clear()

        # Create client and bot outside lock
        try:
            client = Client(instance.config)
            bot = Bot(instance.config, client)

            # Set token_id
            if instance.config.market_token_id:
                instance.token_id = instance.config.market_token_id
            else:
                instance.token_id = client.resolve_token_id(instance.config.market_slug)

            instance.client = client
            instance.bot = bot
            instance.start_time = datetime.now(timezone.utc)
            instance.status = "running"

            # Start bot in background thread
            thread = threading.Thread(
                target=self._run_bot,
                args=(instance,),
                daemon=True,
                name=f"Bot-{bot_id}",
            )
            instance.thread = thread
            thread.start()

            self._log_activity(
                bot_id=bot_id,
                activity_type="system",
                message=f"Bot started for market: {instance.token_id}",
            )

            return True

        except Exception as e:
            logger.error(f"Failed to start bot {bot_id}: {e}")
            instance.status = "error"
            return False

    async def stop_bot(self, bot_id: str) -> bool:
        """Stop a bot instance."""
        with self._lock:
            if bot_id not in self.bots:
                return False

            instance = self.bots[bot_id]

        # Signal bot to stop
        instance.stop_event.set()
        instance.status = "stopped"

        # Wait for thread to finish (with timeout)
        if instance.thread and instance.thread.is_alive():
            instance.thread.join(timeout=5.0)

        self._log_activity(
            bot_id=bot_id,
            activity_type="system",
            message="Bot stopped",
        )

        return True

    async def pause_bot(self, bot_id: str) -> bool:
        """Pause a bot instance."""
        with self._lock:
            if bot_id not in self.bots:
                return False

            instance = self.bots[bot_id]
            instance.status = "paused"

        self._log_activity(
            bot_id=bot_id,
            activity_type="system",
            message="Bot paused",
        )

        return True

    async def stop_all(self):
        """Stop all bot instances."""
        bot_ids = list(self.bots.keys())
        for bot_id in bot_ids:
            await self.stop_bot(bot_id)

    def update_bot_config(self, bot_id: str, updates: Dict[str, Any]) -> bool:
        """Update configuration for a bot instance.

        Note: Some changes require bot restart to take effect.
        """
        with self._lock:
            if bot_id not in self.bots:
                return False

            instance = self.bots[bot_id]

        for key, value in updates.items():
            if hasattr(instance.config, key):
                setattr(instance.config, key, value)
                # Update bot config if bot exists
                if instance.bot:
                    instance.bot.cfg = instance.config

        self._log_activity(
            bot_id=bot_id,
            activity_type="system",
            message=f"Config updated: {list(updates.keys())}",
        )

        return True

    async def manual_trade(
        self,
        bot_id: str,
        side: str,
        amount_usd: float,
        reason: str = "manual",
    ) -> Dict[str, Any]:
        """Execute a manual trade on a specific bot."""
        with self._lock:
            if bot_id not in self.bots:
                return {"success": False, "error": "Bot not found"}

            instance = self.bots[bot_id]

        if not instance.bot or not instance.client:
            return {"success": False, "error": "Bot not running"}

        try:
            result = instance.client.place_market_order(
                side=side,
                amount_usd=amount_usd,
                token_id=instance.token_id,
            )

            if result.success:
                # Extract order_id from response dict
                order_id = result.response.get("orderID") or result.response.get("order_id") or "N/A"
                
                self._log_activity(
                    bot_id=bot_id,
                    activity_type="order",
                    message=f"Manual {side} order: ${amount_usd} ({reason})",
                    details={"order_id": order_id, "side": side, "amount": amount_usd},
                )
                return {
                    "success": True,
                    "order_id": order_id,
                    "side": side,
                    "amount_usd": amount_usd,
                }
            else:
                error_msg = result.response.get("error") or result.response.get("message") or "Order failed"
                return {
                    "success": False,
                    "error": error_msg,
                }

        except Exception as e:
            logger.error(f"Manual trade failed: {e}")
            return {"success": False, "error": str(e)}

    async def close_position(self, bot_id: str) -> Dict[str, Any]:
        """Close the current position for a bot."""
        with self._lock:
            if bot_id not in self.bots:
                return {"success": False, "error": "Bot not found"}

            instance = self.bots[bot_id]

        if not instance.bot or instance.bot.open_position is None:
            return {"success": False, "error": "No open position"}

        try:
            position = instance.bot.open_position

            # Determine opposite side
            side = "SELL" if position.side == "BUY" else "BUY"

            result = instance.client.place_market_order(
                side=side,
                amount_usd=position.amount_usd,
                token_id=instance.token_id,
            )

            if result.success:
                instance.bot.open_position = None

                self._log_activity(
                    bot_id=bot_id,
                    activity_type="exit",
                    message=f"Position closed: {side} ${position.amount_usd}",
                )

                return {"success": True, "side": side, "amount_usd": position.amount_usd}
            else:
                return {"success": False, "error": result.error or "Close failed"}

        except Exception as e:
            logger.error(f"Close position failed: {e}")
            return {"success": False, "error": str(e)}

    def get_bot_status(self, bot_id: str) -> Optional[Dict[str, Any]]:
        """Get detailed status of a specific bot."""
        with self._lock:
            if bot_id not in self.bots:
                return None

            instance = self.bots[bot_id]

        status = {
            "bot_id": instance.bot_id,
            "status": instance.status,
            "market_name": instance.market_name,
            "token_id": instance.token_id,
            # Balance allocation
            "max_allocated_balance": instance.max_allocated_balance,
            "current_allocation": instance.current_allocation,
            "available_balance": instance.max_allocated_balance - instance.current_allocation,
            "config": {
                "spike_threshold_pct": instance.config.spike_threshold_pct,
                "take_profit_pct": instance.config.take_profit_pct,
                "stop_loss_pct": instance.config.stop_loss_pct,
                "trade_size_usd": instance.config.default_trade_size_usd,
                "dry_run": instance.config.dry_run,
            },
        }

        # Add bot-specific info if running
        if instance.bot:
            status["uptime_seconds"] = instance.bot.uptime_seconds if hasattr(instance.bot, "uptime_seconds") else 0
            status["wallet_address"] = instance.client.get_wallet_address() if instance.client else "0x..."
            status["usdc_balance"] = instance.client.get_usdc_balance() if instance.client else 0.0

            # Position info
            if instance.bot.open_position:
                pos = instance.bot.open_position
                current_price = instance.bot.get_mid_price() if hasattr(instance.bot, "get_mid_price") else pos.entry_price
                pnl = pos.calculate_pnl(current_price)

                status["position"] = {
                    "has_position": True,
                    "side": pos.side,
                    "entry_price": pos.entry_price,
                    "current_price": current_price,
                    "amount_usd": pos.amount_usd,
                    "age_seconds": pos.age_seconds,
                    "pnl_pct": pnl["pnl_pct"],
                    "pnl_usd": pnl["pnl_usd"],
                }
            else:
                status["position"] = {"has_position": False}

            # Session stats
            status["session_stats"] = {
                "realized_pnl": instance.bot.realized_pnl if hasattr(instance.bot, "realized_pnl") else 0.0,
                "total_trades": instance.bot.total_trades if hasattr(instance.bot, "total_trades") else 0,
                "winning_trades": instance.bot.winning_trades if hasattr(instance.bot, "winning_trades") else 0,
            }

        return status

    def get_all_status(self) -> List[Dict[str, Any]]:
        """Get status of all bot instances."""
        statuses = []
        with self._lock:
            bot_ids = list(self.bots.keys())

        for bot_id in bot_ids:
            status = self.get_bot_status(bot_id)
            if status:
                statuses.append(status)

        return statuses

    def get_wallet_balance(self) -> float:
        """Get overall wallet USDC balance."""
        if self.bots:
            # Get balance from first bot's client
            for instance in self.bots.values():
                if instance.client:
                    try:
                        self._wallet_balance = instance.client.get_usdc_balance()
                        break
                    except Exception:
                        pass
        return self._wallet_balance

    def initialize_bankroll(self, max_allocation_pct: float = 0.8):
        """Initialize bankroll management with current wallet balance.

        Args:
            max_allocation_pct: Maximum % of balance to allocate (keep reserve)
        """
        balance = self.get_wallet_balance()
        if balance > 0:
            self.bankroll_manager = BankrollManager(balance, max_allocation_pct)
            logger.info(f"Bankroll initialized: ${balance:.2f}")
        else:
            logger.warning("Cannot initialize bankroll - no balance available")

    def check_bankroll_allocation(self, bot_id: str, trade_size: float) -> bool:
        """Check if bot has sufficient bankroll allocation.

        Args:
            bot_id: Bot requesting allocation
            trade_size: Amount needed for trade

        Returns:
            True if allocation available, False otherwise
        """
        if not self.bankroll_manager:
            # Auto-initialize if not exists
            self.initialize_bankroll()

        if not self.bankroll_manager:
            # No bankroll manager - allow trade (will fail at actual execution if insufficient)
            return True

        return self.bankroll_manager.allocate_to_bot(bot_id, trade_size)

    def release_bankroll(self, bot_id: str, amount: float):
        """Release bankroll allocation from bot (after position closed)."""
        if self.bankroll_manager:
            self.bankroll_manager.release_from_bot(bot_id, amount)

    def update_bot_pnl(self, bot_id: str, pnl: float):
        """Update realized P&L for a bot."""
        if self.bankroll_manager:
            self.bankroll_manager.update_pnl(bot_id, pnl)

    def get_bankroll_status(self) -> Optional[Dict[str, Any]]:
        """Get current bankroll allocation status."""
        if self.bankroll_manager:
            return self.bankroll_manager.get_allocation_status()
        return None

    def get_recent_activities(self, limit: int = 100, bot_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent activity log entries."""
        activities = list(self._activities)

        if bot_id:
            activities = [a for a in activities if a.bot_id == bot_id]

        # Return most recent first
        activities = list(reversed(activities))[:limit]

        return [a.to_dict() for a in activities]

    def _run_bot(self, instance: BotInstance):
        """Run bot in background thread."""
        try:
            if not instance.bot:
                return

            logger.info(f"Starting bot thread for {instance.bot_id}")

            # Run the bot
            instance.bot.run(
                stop_event=instance.stop_event,
            )

        except Exception as e:
            logger.error(f"Bot thread error for {instance.bot_id}: {e}")
            instance.status = "error"
            self._log_activity(
                bot_id=instance.bot_id,
                activity_type="error",
                message=f"Bot error: {str(e)}",
            )

    def _log_activity(self, bot_id: str, activity_type: str, message: str, details: Optional[Dict[str, Any]] = None):
        """Log an activity event."""
        activity = Activity(
            id=f"act_{uuid.uuid4().hex[:8]}",
            bot_id=bot_id,
            timestamp=datetime.now(timezone.utc).timestamp(),
            type=activity_type,
            message=message,
            details=details,
        )

        self._activities.append(activity)

        # Notify callbacks
        for callback in self._activity_callbacks:
            try:
                callback(activity.to_dict())
            except Exception as e:
                logger.error(f"Activity callback error: {e}")

    def _on_state_change(self, bot_id: str, state: Dict[str, Any]):
        """Handle bot state change."""
        # Could trigger WebSocket broadcast here
        pass

    def _on_activity(self, bot_id: str, activity: Dict[str, Any]):
        """Handle bot activity."""
        self._log_activity(bot_id, activity.get("type", "system"), activity.get("message", ""))

    def _on_price_update(self, bot_id: str, price_data: Dict[str, Any]):
        """Handle price update."""
        # Could trigger WebSocket broadcast here
        pass

    def _on_trade(self, bot_id: str, trade_data: Dict[str, Any]):
        """Handle trade execution."""
        self._log_activity(
            bot_id=bot_id,
            activity_type="order",
            message=f"Trade: {trade_data.get('side')} ${trade_data.get('amount_usd', 0)}",
            details=trade_data,
        )

    def register_activity_callback(self, callback: Callable):
        """Register a callback for activity events."""
        self._activity_callbacks.append(callback)
