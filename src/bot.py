"""Main bot orchestrator tying together config, client, market data, strategy, and risk.

Implements the Spike Sam fade strategy with TP/SL/time risk controls and structured logs.

Now supports WebSocket for real-time market data with multi-window spike detection.
Based on Polymarket documentation:
https://docs.polymarket.com/developers/CLOB/websocket/market-channel
"""
from __future__ import annotations

import time
import logging
from collections import deque
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from typing import Optional, Deque, List, Tuple, Dict, Any
import json
from pathlib import Path
import threading
import statistics
import random

from .config import Config
from .clob_client import Client

try:
    from .websocket_client import WebSocketSyncWrapper
    WEBSOCKET_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"WebSocket import failed: {e}")
    WEBSOCKET_AVAILABLE = False

try:
    from .user_websocket_client import UserWebSocketSyncWrapper
    USER_WEBSOCKET_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"User WebSocket import failed: {e}")
    USER_WEBSOCKET_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class TradeTarget:
    """Represents the current target price for the Train of Trade strategy.
    
    The target is set:
    1. When bot starts (price to buy)
    2. After buying (price to sell = entry * (1 + take_profit))
    3. After selling (price to buy = current market price for immediate rebuy)
    """
    price: float                    # Target price to trigger action
    action: str                     # "BUY" or "SELL"
    condition: str                  # "<=" for buy, ">=" for sell
    set_at: datetime                # When target was set
    set_at_market_price: float      # Market price when target was set
    reason: str                     # Why: "bot_start", "after_buy", "after_sell", "spike_detected"
    triggered: bool = False         # Has this target been executed?

    def to_dict(self) -> dict:
        return {
            "price": self.price,
            "action": self.action,
            "condition": self.condition,
            "set_at": self.set_at.isoformat(),
            "set_at_market_price": self.set_at_market_price,
            "reason": self.reason,
            "triggered": self.triggered,
        }

    def check_condition(self, current_price: float) -> bool:
        """Check if current price meets the target condition."""
        if self.action == "BUY" and self.condition == "<=":
            return current_price <= self.price
        elif self.action == "SELL" and self.condition == ">=":
            return current_price >= self.price
        return False


@dataclass
class Position:
    side: str  # BUY -> LONG, SELL -> SHORT
    entry_price: float
    entry_time: datetime
    amount_usd: float
    entry_order_id: Optional[str] = None  # Order ID for settlement tracking
    pending_settlement: bool = True       # True until settlement confirmed
    expected_shares: float = 0.0          # Expected shares from trade

    @property
    def position_type(self) -> str:
        return "LONG" if self.side.upper() == "BUY" else "SHORT"

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.entry_time).total_seconds()

    @property
    def age_minutes(self) -> float:
        return self.age_seconds / 60

    def calculate_pnl(self, current_price: float) -> Dict[str, float]:
        """Calculate unrealized P&L at current price."""
        if self.position_type == "LONG":
            pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        else:  # SHORT
            pnl_pct = (self.entry_price - current_price) / self.entry_price * 100

        pnl_usd = self.amount_usd * pnl_pct / 100

        return {
            "pnl_pct": pnl_pct,
            "pnl_usd": pnl_usd,
            "current_price": current_price,
            "entry_price": self.entry_price,
        }

    def to_dict(self) -> dict:
        return {
            "side": self.side,
            "position_type": self.position_type,
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "amount_usd": self.amount_usd,
            "age_seconds": self.age_seconds,
            "entry_order_id": self.entry_order_id,
            "pending_settlement": self.pending_settlement,
            "expected_shares": self.expected_shares,
        }


class Bot:
    def __init__(self, config: Config, client: Optional[Client] = None):
        self.cfg = config
        self.client = client
        self.token_id = None
        if self.client is not None:
            try:
                self.token_id = self.client.resolve_token_id()
            except Exception:
                self.token_id = None

        # Price history for spike detection
        self.history: Deque[Tuple[datetime, float]] = deque(
            maxlen=self.cfg.price_history_size
        )  # (timestamp, price)

        # Signal tracking
        self.last_signal_time: Optional[datetime] = None
        self.open_position: Optional[Position] = None

        # P&L tracking
        self.realized_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0

        # WebSocket client for real-time data
        self.ws_client: Optional[WebSocketSyncWrapper] = None
        self.use_websocket = self.cfg.wss_enabled and WEBSOCKET_AVAILABLE

        # Statistics
        self.prices_seen = 0
        self.last_price: Optional[float] = None
        self.last_price_time: Optional[datetime] = None
        self.spikes_detected = 0
        
        # Trading halt flag (limits/daily loss)
        self.trading_halted: bool = False
        
        # Daily loss tracking
        self.daily_realized_pnl: float = 0.0
        self.daily_pnl_date = datetime.now(timezone.utc).date()
        self.last_exit_time: Optional[datetime] = None  # Track exit for settlement delay

        # Settlement delay (seconds to wait after exit before new entry)
        self.settlement_delay_seconds = 2.0

        # Initial inventory flag - must BUY first before we can SELL
        self.initial_inventory_acquired = False

        # Thread safety lock for shared state (position, history) between WebSocket thread and main loop
        self._state_lock = threading.Lock()

        # User WebSocket for settlement confirmation (uses configured timeout)
        self.user_ws_client: Optional[UserWebSocketSyncWrapper] = None
        self.use_user_websocket = USER_WEBSOCKET_AVAILABLE
        self.settlement_timeout_seconds = self.cfg.settlement_timeout_seconds

        # Persistence
        self.state_file = Path("data/position.json")
        
        # Train of Trade: Target price tracking
        self.current_target: Optional[TradeTarget] = None
        self.target_history: List[TradeTarget] = []
        
        self._load_state()

    def _enough_cooldown(self) -> bool:
        """Check if enough time has passed since last signal.

        Also includes settlement delay after exits to prevent balance race conditions.
        """
        now = datetime.now(timezone.utc)

        # Check signal cooldown
        if self.last_signal_time:
            signal_cooldown = (now - self.last_signal_time).total_seconds() >= self.cfg.cooldown_seconds
            if not signal_cooldown:
                return False

        # Check settlement delay after exit
        if self.last_exit_time:
            settlement_elapsed = (now - self.last_exit_time).total_seconds()
            if settlement_elapsed < self.settlement_delay_seconds:
                logger.debug(f"Settlement delay: {settlement_elapsed:.1f}s < {self.settlement_delay_seconds}s")
                return False

        return True

    # ========== PRICE SIMULATION FOR DRY RUN ==========
    def _simulate_price_movement(self, current_price: float) -> float:
        """Simulate price movement for dry run mode using geometric Brownian motion.

        Creates realistic price movements with:
        - Random volatility (0.5-2% per tick)
        - Mean reversion tendency (prices drift back to center)
        - Occasional spikes (to test spike detection)
        """
        if not self.last_price:
            return current_price

        # Base volatility for prediction markets (higher than stocks)
        base_volatility = 0.005  # 0.5% per tick
        spike_chance = 0.02  # 2% chance of spike per tick

        # Decide if this tick has a spike
        if random.random() < spike_chance:
            # Generate a spike (2-8% move)
            spike_direction = 1 if random.random() > 0.5 else -1
            spike_magnitude = random.uniform(0.02, 0.08)
            change_pct = spike_direction * spike_magnitude
            logger.info(f"[SIMULATION] Spike generated: {change_pct*100:+.2f}%")
        else:
            # Normal price movement with mean reversion
            # Prices tend to stay in the 0.02-0.98 range (typical for YES/NO markets)
            center = 0.50
            mean_reversion_strength = 0.01

            # Distance from center creates pull toward center
            distance_from_center = (center - current_price) / center
            mean_reversion = distance_from_center * mean_reversion_strength

            # Random walk component
            random_walk = random.gauss(0, base_volatility)

            # Combine mean reversion + random walk
            change_pct = mean_reversion + random_walk

        # Calculate new price
        new_price = current_price * (1 + change_pct)

        # Clamp to valid prediction market range [0.01, 0.99]
        new_price = max(0.01, min(0.99, new_price))

        return new_price

    def _get_price_with_simulation(self, rest_price: Optional[float]) -> Optional[float]:
        """Get price, using simulation in dry run mode.

        In dry run mode:
        - Uses real REST price for first tick (initialization)
        - Then always uses simulated prices (no more REST calls)
        - This makes dry runs faster and more predictable for testing strategies
        """
        # In dry run mode, use initial real price then simulate
        if self.cfg.dry_run:
            if rest_price is not None and self.last_price is None:
                # First tick - use real price as starting point
                logger.info(f"[DRY_RUN] Initial price set from REST: {rest_price:.4f}")
                return rest_price
            elif self.last_price is not None:
                # Subsequent ticks - always simulate
                return self._simulate_price_movement(self.last_price)
            else:
                # No price available yet
                return None

        # Live mode - use real REST price
        return rest_price

    def _set_buy_target(self, price: float, reason: str = "manual"):
        """Set target to buy at specified price.
        
        For Train of Trade:
        - On bot start: target = current market price
        - After sell: target = current market price (immediate rebuy)
        """
        self.current_target = TradeTarget(
            price=price,
            action="BUY",
            condition="<=",
            set_at=datetime.now(timezone.utc),
            set_at_market_price=self.last_price or price,
            reason=reason
        )
        logger.info(f"[TARGET] BUY target set: ${price:.4f} (reason: {reason})")
        self._broadcast_target_update()

    def _set_sell_target(self, entry_price: float, reason: str = "after_buy"):
        """Set target to sell at calculated price based on take profit.
        
        For Train of Trade:
        - After buy: target = entry_price * (1 + take_profit_pct)
        """
        target_price = entry_price * (1 + self.cfg.take_profit_pct / 100)
        self.current_target = TradeTarget(
            price=target_price,
            action="SELL",
            condition=">=",
            set_at=datetime.now(timezone.utc),
            set_at_market_price=self.last_price or entry_price,
            reason=reason
        )
        logger.info(f"[TARGET] SELL target set: ${target_price:.4f} (TP: {self.cfg.take_profit_pct}%, entry: ${entry_price:.4f})")
        self._broadcast_target_update()

    def _broadcast_target_update(self):
        """Broadcast target update via callback."""
        if hasattr(self, '_target_update_callback') and self._target_update_callback:
            try:
                target_dict = self.current_target.to_dict() if self.current_target else None
                # Wrap target in expected format for frontend
                target_data = {
                    "target": target_dict,
                    "current_price": self.last_price,
                    "condition_met": self.current_target.check_condition(self.last_price) if self.current_target and self.last_price else False
                }
                self._target_update_callback(target_data)
            except Exception as e:
                logger.warning(f"Target update callback failed: {e}")

    def _check_target_condition(self, price: float) -> bool:
        """Check if current price meets the target condition."""
        if not self.current_target or self.current_target.triggered:
            return False
        return self.current_target.check_condition(price)

    def _execute_target(self, price: float):
        """Execute the current target order and set next target.
        
        This implements the Train of Trade cycle:
        1. BUY triggered -> Set SELL target
        2. SELL triggered -> Set BUY target (immediate rebuy)
        """
        if not self.current_target:
            return
            
        target = self.current_target
        target.triggered = True
        self.target_history.append(target)
        
        if target.action == "BUY":
            # Execute buy and set sell target
            logger.info(f"[TARGET_HIT] BUY at ${price:.4f} (target: ${target.price:.4f})")
            self._enter("BUY", price, reason=f"target_hit_{target.reason}")
            # After successful buy, set sell target
            if self.open_position:
                self._set_sell_target(price, reason="after_buy")
        
        elif target.action == "SELL":
            # Execute sell and apply rebuy strategy
            logger.info(f"[TARGET_HIT] SELL at ${price:.4f} (target: ${target.price:.4f})")
            if self.open_position:
                self._exit(reason=f"target_hit_{target.reason}", price=price)
            
            # Rebuy Strategy
            if self.cfg.rebuy_strategy == "immediate":
                # Wait for settlement then rebuy at market
                delay = self.cfg.rebuy_delay_seconds
                if delay > 0:
                    logger.info(f"[REBUY] Waiting {delay}s delay...")
                    import time
                    time.sleep(delay)
                
                self._enter("BUY", price, reason="immediate_rebuy")
                # After successful rebuy, set sell target
                if self.open_position:
                    self._set_sell_target(price, reason="after_rebuy")
            else:
                # wait_for_drop: Set target below current price
                drop_pct = self.cfg.rebuy_drop_pct
                target_price = price * (1 - drop_pct / 100)
                logger.info(f"[REBUY] Waiting for {drop_pct}% drop to ${target_price:.4f}")
                self._set_buy_target(target_price, reason="wait_for_drop")

    def _compute_spike_multi_window(self, current_price: float) -> Tuple[float, Dict[str, Any]]:
        """Compare current price against multiple time windows.

        Returns:
            (max_spike_pct, stats_dict) where stats contains analysis details
        """
        if len(self.history) < 5:
            return 0.0, {"reason": "insufficient_history"}

        now = datetime.now(timezone.utc)
        windows_seconds = self.cfg.get_spike_windows_seconds()
        max_spike = 0.0
        best_window = None

        for window_sec in windows_seconds:
            cutoff = now - timedelta(seconds=window_sec)

            # Get prices within window
            window_prices = [
                (ts, p) for ts, p in self.history
                if ts >= cutoff and p > 0
            ]

            if len(window_prices) < 3:
                continue

            # Use oldest price in window as baseline
            old_price = window_prices[0][1]

            # Calculate percentage change
            spike_pct = (current_price - old_price) / old_price * 100.0

            if abs(spike_pct) > abs(max_spike):
                max_spike = spike_pct
                best_window = window_sec

            # Also check cumulative move (peak to trough in window)
            prices_only = [p for _, p in window_prices]
            if prices_only:
                min_p = min(prices_only)
                max_p = max(prices_only)
                cumulative = (max_p - min_p) / min_p * 100 if min_p > 0 else 0
                if abs(cumulative) > abs(max_spike):
                    max_spike = cumulative
                    best_window = window_sec

        # Calculate volatility for filtering
        recent_prices = [p for _, p in list(self.history)[-100:]]
        volatility_cv = 0.0
        if len(recent_prices) >= 2:
            mean = sum(recent_prices) / len(recent_prices)
            if mean > 0:
                stddev = statistics.stdev(recent_prices)
                volatility_cv = (stddev / mean) * 100

        stats = {
            "spike_pct": max_spike,
            "window_seconds": best_window,
            "history_count": len(self.history),
            "volatility_cv": volatility_cv,
            "current_price": current_price,
        }

        # Apply volatility filter if enabled
        if self.cfg.use_volatility_filter and volatility_cv > self.cfg.max_volatility_cv:
            stats["volatility_filtered"] = True
            stats["volatility_reason"] = f"CV={volatility_cv:.2f}% > {self.cfg.max_volatility_cv}%"

        return max_spike, stats

    def decide_action(self, spike_pct: float, price: float, stats: Dict[str, Any]) -> Dict[str, Any]:
        """Strategy decision function: Spike Sam fade strategy.

        Args:
            spike_pct: Detected spike percentage
            price: Current market price
            stats: Additional statistics

        Returns:
            Dict with decision:
                - action: "buy" | "sell" | "ignore"
                - size_usd: float (trade size in USD)
                - reason: str (explanation)
        """
        has_position = self.open_position is not None
        in_cooldown = not self._enough_cooldown()

        # If we have a position, ignore (risk exits handled separately)
        if has_position:
            return {"action": "ignore", "size_usd": 0, "reason": "position_open"}

        # In cooldown
        if in_cooldown:
            return {"action": "ignore", "size_usd": 0, "reason": "cooldown"}

        # PRIORITY: Initial inventory acquisition (must BUY first before we can SELL)
        # This ensures we have tokens to sell when price spikes UP
        if not self.initial_inventory_acquired:
            logger.info("[STRATEGY] Session start - acquiring initial inventory with BUY")
            return {
                "action": "buy",
                "size_usd": self.cfg.default_trade_size_usd,
                "reason": "initial_inventory_acquisition"
            }

        # Check volatility filter (only after initial inventory)
        if stats.get("volatility_filtered"):
            return {
                "action": "ignore",
                "size_usd": 0,
                "reason": f"volatility_filtered ({stats.get('volatility_reason', 'high CV')})"
            }

        threshold = self.cfg.spike_threshold_pct
        min_strength = self.cfg.min_spike_strength

        # Spike UP -> SELL (fade the pump)
        if spike_pct >= threshold and abs(spike_pct) >= min_strength:
            return {
                "action": "sell",
                "size_usd": self.cfg.default_trade_size_usd,
                "reason": f"spike_up_{spike_pct:.2f}%_window_{stats.get('window_seconds', 'unknown')}s"
            }

        # Spike DOWN -> BUY (fade the dump)
        if spike_pct <= -threshold and abs(spike_pct) >= min_strength:
            return {
                "action": "buy",
                "size_usd": self.cfg.default_trade_size_usd,
                "reason": f"spike_down_{abs(spike_pct):.2f}%_window_{stats.get('window_seconds', 'unknown')}s"
            }

        # No significant spike
        return {"action": "ignore", "size_usd": 0, "reason": "no_spike"}

    def _risk_exit(self, current_price: float) -> Optional[str]:
        """Check if position should be exited based on risk rules."""
        if not self.open_position:
            return None
        pos = self.open_position

        # Time-based exit (convert minutes to seconds)
        max_hold_seconds = self.cfg.max_hold_seconds
        held = pos.age_seconds
        if held >= max_hold_seconds:
            return f"Time exit (held {held:.0f}s > {max_hold_seconds}s)"

        # Percentage P&L
        pnl = pos.calculate_pnl(current_price)
        pnl_pct = pnl["pnl_pct"]

        if pnl_pct >= self.cfg.take_profit_pct:
            return f"Take profit hit (+{pnl_pct:.2f}% >= {self.cfg.take_profit_pct}%)"
        if pnl_pct <= -self.cfg.stop_loss_pct:
            return f"Stop loss hit ({pnl_pct:.2f}% <= -{self.cfg.stop_loss_pct}%)"

        return None

    def _save_state(self):
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)
            data = {
                "open_position": asdict(self.open_position) if self.open_position else None,
                "realized_pnl": self.realized_pnl,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "initial_inventory_acquired": self.initial_inventory_acquired,
                "token_id": self.token_id,
                "current_target": self.current_target.to_dict() if self.current_target else None,
                "target_history_count": len(self.target_history),
            }
            self.state_file.write_text(json.dumps(data, default=str))
        except Exception:
            pass

    def _load_state(self):
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text())
                
                # Verify token_id matches (prevent loading state from different market)
                saved_token_id = data.get("token_id")
                if saved_token_id and self.token_id and saved_token_id != self.token_id:
                    logger.warning(f"[STATE] Ignoring saved state from different market (saved={saved_token_id[:8]}..., current={self.token_id[:8]}...)")
                    return
                
                pos = data.get("open_position")
                if pos:
                    self.open_position = Position(
                        side=pos["side"],
                        entry_price=float(pos["entry_price"]),
                        entry_time=datetime.fromisoformat(pos["entry_time"]) if isinstance(pos["entry_time"], str) else datetime.now(timezone.utc),
                        amount_usd=float(pos["amount_usd"]),
                    )
                self.realized_pnl = float(data.get("realized_pnl", 0.0))
                self.total_trades = int(data.get("total_trades", 0))
                self.winning_trades = int(data.get("winning_trades", 0))
                self.initial_inventory_acquired = bool(data.get("initial_inventory_acquired", False))
                
                # Restore current target
                target_data = data.get("current_target")
                if target_data:
                    self.current_target = TradeTarget(
                        price=float(target_data["price"]),
                        action=target_data["action"],
                        condition=target_data["condition"],
                        set_at=datetime.fromisoformat(target_data["set_at"]) if isinstance(target_data["set_at"], str) else datetime.now(timezone.utc),
                        set_at_market_price=float(target_data["set_at_market_price"]),
                        reason=target_data["reason"],
                        triggered=bool(target_data.get("triggered", False)),
                    )
                    logger.info(f"[STATE] Restored target: {self.current_target.action} @ ${self.current_target.price:.4f}")
                
                if self.initial_inventory_acquired:
                    logger.info("[STATE] Restored initial_inventory_acquired=True from saved state")
        except Exception:
            pass

    def _enter(self, side: str, price: float, reason: str = ""):
        """Enter a position with intelligent pre-checks and error handling.

        If order placement fails, the position is NOT opened (preventing tracking issues).
        """
        # Runtime validation of trade size
        if self.cfg.default_trade_size_usd < self.cfg.min_trade_usd:
            logger.warning(f"[ENTRY_SKIPPED] Trade size ${self.cfg.default_trade_size_usd:.2f} < min ${self.cfg.min_trade_usd:.2f}")
            return
        if self.cfg.default_trade_size_usd > self.cfg.max_trade_usd:
            logger.warning(f"[ENTRY_SKIPPED] Trade size ${self.cfg.default_trade_size_usd:.2f} > max ${self.cfg.max_trade_usd:.2f}")
            return

        if self.trading_halted:
            logger.warning("[ENTRY_BLOCKED] Trading halted due to limits")
            return

        # First, try to place the order
        amount_usd = self.cfg.default_trade_size_usd
        logger.info(f"[ENTRY] Attempting {side.upper()} ${amount_usd:.2f} at {price:.4f} ({reason})")

        try:
            result = self.client.place_market_order(
                side=side,
                amount_usd=self.cfg.default_trade_size_usd,
                token_id=self.token_id
            )

            if not result.success:
                # Pre-check failed or order rejected
                error_reason = result.response.get("reason", "unknown")
                error_msg = result.response.get("error", "Order failed")
                logger.warning(f"[ENTRY_SKIPPED] {error_msg} (reason: {error_reason})")
                # Don't open position - don't track trade, don't update cooldown
                return

            # Order succeeded - now track the position
            order_id = result.response.get("orderID") or result.response.get("order_id") or ""
            expected_shares = amount_usd / price if price > 0 else 0
            
            self.open_position = Position(
                side=side.upper(),
                entry_price=price,
                entry_time=datetime.now(timezone.utc),
                amount_usd=self.cfg.default_trade_size_usd,
                entry_order_id=order_id,
                pending_settlement=True,  # Mark as pending until confirmed
                expected_shares=expected_shares,
            )
            self.last_signal_time = datetime.now(timezone.utc)
            
            # Register for settlement tracking via User WebSocket
            if self.user_ws_client and order_id:
                self.user_ws_client.register_pending_order(order_id)
            
            # Start fallback timer (soft 2s timeout)
            if order_id:
                self._start_settlement_fallback_timer(order_id)
            else:
                # No order ID, mark as settled immediately
                self.open_position.pending_settlement = False
            
            # Mark initial inventory as acquired after first successful BUY
            if side.upper() == "BUY" and not self.initial_inventory_acquired:
                self.initial_inventory_acquired = True
                logger.info("[INVENTORY] Initial inventory acquired - SELL on spike UP now enabled")
                self._save_state()  # Persist immediately
            
            logger.info(f"[POSITION_OPENED] {side.upper()} ${amount_usd:.2f} at {price:.4f} (order={order_id[:16]}...)" if order_id else f"[POSITION_OPENED] {side.upper()} ${self.cfg.default_trade_size_usd:.2f} at {price:.4f}")
            
            # Emit position update callback
            if hasattr(self, '_position_update_callback') and self._position_update_callback:
                try:
                    pnl = self.open_position.calculate_pnl(price)
                    self._position_update_callback({
                        "has_position": True,
                        "side": side.upper(),
                        "entry_price": price,
                        "current_price": price,
                        "amount_usd": amount_usd,
                        "shares": expected_shares,
                        "age_seconds": 0,
                        "pnl_pct": 0.0,
                        "pnl_usd": 0.0,
                        "max_hold_seconds": self.cfg.max_hold_seconds,
                        "take_profit_pct": self.cfg.take_profit_pct,
                        "stop_loss_pct": self.cfg.stop_loss_pct,
                        "pending_settlement": True,
                    })
                except Exception as e:
                    logger.warning(f"Position update callback failed: {e}")

        except Exception as e:
            err_str = str(e).lower()
            # Check for specific error types
            if "balance" in err_str or "allowance" in err_str:
                logger.warning(f"[ENTRY_FAILED] Balance/allowance issue: {e}")
                logger.info("[TIP] Check your USDC.e balance on Polygon")
            elif "no match" in err_str:
                logger.warning(f"[ENTRY_FAILED] No matching orders: {e}")
                logger.info("[TIP] Market may be illiquid or price moved quickly")
            else:
                logger.warning(f"[ENTRY_FAILED] {e}")

            # Don't open position on failure
            self.open_position = None

    def _exit(self, reason: str, price: float):
        if not self.open_position:
            return
        pos = self.open_position
        side = "SELL" if pos.position_type == "LONG" else "BUY"

        # SAFETY CHECK: Don't exit if position is still pending settlement
        if pos.pending_settlement:
            logger.debug(f"[EXIT_SKIPPED] Position still pending settlement, waiting...")
            return

        # SAFETY CHECK: Verify we actually own tokens before trying to sell
        if side == "SELL":
            actual_shares = self.client.get_token_balance(self.token_id)
            if actual_shares <= 0:
                # Check if settlement just confirmed
                if self.user_ws_client and pos.entry_order_id:
                    if self.user_ws_client.is_settled(pos.entry_order_id):
                        # Settlement confirmed but API hasn't updated yet - wait a bit
                        logger.info("[EXIT_WAITING] Settlement confirmed but tokens not visible yet, waiting 5s...")
                        import time
                        time.sleep(5)
                        actual_shares = self.client.get_token_balance(self.token_id)
                
                if actual_shares <= 0:
                    logger.warning(f"[EXIT_DELAYED] Cannot SELL yet - tokens not in wallet (still settling)")
                    logger.info("[TIP] Will retry on next price update once tokens arrive")
                    # DON'T clear position - tokens will arrive, keep position open
                    return

        # Calculate realized P&L
        pnl = pos.calculate_pnl(price)
        pnl_pct = pnl["pnl_pct"]
        pnl_usd = pnl["pnl_usd"]

        self.realized_pnl += pnl_usd
        self.total_trades += 1

        # Daily loss tracking (UTC reset)
        today = datetime.now(timezone.utc).date()
        if self.daily_pnl_date != today:
            self.daily_pnl_date = today
            self.daily_realized_pnl = 0.0
        self.daily_realized_pnl += pnl_usd
        if pnl_usd > 0:
            self.winning_trades += 1

        # Session limit checks: trades and session loss
        if self.cfg.max_trades_per_session and self.total_trades >= self.cfg.max_trades_per_session:
            self.trading_halted = True
            logger.warning(f"[LIMIT] Max trades per session reached: {self.total_trades} >= {self.cfg.max_trades_per_session}. Stopping bot.")
            if hasattr(self, '_position_update_callback') and self._position_update_callback:
                try:
                    self._position_update_callback({"has_position": False})
                except Exception:
                    pass
            # Stop loop by setting a high cooldown and leaving
            self.last_signal_time = datetime.now(timezone.utc)
            # Emit activity via callback if available
            if hasattr(self, '_spike_detected_callback') and self._spike_detected_callback:
                try:
                    self._spike_detected_callback({"type": "system", "reason": "max_trades_reached"})
                except Exception:
                    pass
        if self.cfg.session_loss_limit_usd and self.realized_pnl <= -abs(self.cfg.session_loss_limit_usd):
            self.trading_halted = True
            logger.warning(f"[LIMIT] Session loss limit reached: PnL ${self.realized_pnl:.2f} <= -${abs(self.cfg.session_loss_limit_usd):.2f}. Stopping bot.")
            self.last_signal_time = datetime.now(timezone.utc)

        logger.info(
            f"[EXIT] {reason}: {side} ${pos.amount_usd:.2f} at {price:.4f} "
            f"| P&L: ${pnl_usd:+.2f} ({pnl_pct:+.2f}%) "
            f"| Hold: {pos.age_minutes:.1f}min"
        )
        logger.info(
            f"[TOTAL] P&L: ${self.realized_pnl:+.2f} | Win Rate: {self.winning_trades}/{self.total_trades}"
        )

        try:
            result = self.client.place_market_order(
                side=side,
                amount_usd=pos.amount_usd,
                token_id=self.token_id,
            )
            if result.success:
                order_id = result.response.get('orderID', 'N/A')
                filled = result.response.get('matchedAmount', 'N/A')
                logger.info(f"[EXIT_FILLED] ID={order_id} | Matched: ${filled}")
                # Track exit time for settlement delay
                self.last_exit_time = datetime.now(timezone.utc)
            else:
                # Exit order failed - log the reason
                error_msg = result.response.get('error', 'Unknown error')
                error_reason = result.response.get('reason', 'unknown')
                logger.warning(f"[EXIT_FAILED] {error_msg} (reason: {error_reason})")
        except Exception as e:
            logger.warning(f"[EXIT_FAILED] {e}")

        # Emit position closed callback
        if hasattr(self, '_position_update_callback') and self._position_update_callback:
            try:
                self._position_update_callback({
                    "has_position": False,
                    "side": None,
                    "entry_price": 0,
                    "current_price": price,
                    "amount_usd": 0,
                    "shares": 0,
                    "age_seconds": 0,
                    "pnl_pct": 0.0,
                    "pnl_usd": 0.0,
                    "max_hold_seconds": 0,
                    "take_profit_pct": 0,
                    "stop_loss_pct": 0,
                    "pending_settlement": False,
                })
            except Exception as e:
                logger.warning(f"Position update callback failed: {e}")

        self.open_position = None
        self.last_signal_time = datetime.now(timezone.utc)
        self._save_state()

    def _on_settlement_confirmed(self, order_id: str, status: str):
        """Called when User WebSocket confirms trade settlement."""
        with self._state_lock:
            if self.open_position and self.open_position.entry_order_id == order_id:
                if status == "CONFIRMED":
                    self.open_position.pending_settlement = False
                    logger.info(f"[SETTLEMENT] Order {order_id[:16]}... CONFIRMED via WebSocket")

    def _start_settlement_fallback_timer(self, order_id: str):
        """Start a background timer to mark settlement complete after timeout.

        This is a soft fallback - if WebSocket confirms earlier, this does nothing.
        Uses the configured settlement_timeout_seconds (default: 90s for Polymarket).
        """
        def fallback():
            time.sleep(self.settlement_timeout_seconds)
            with self._state_lock:
                if self.open_position and self.open_position.entry_order_id == order_id:
                    if self.open_position.pending_settlement:
                        self.open_position.pending_settlement = False
                        logger.info(f"[SETTLEMENT] Order {order_id[:16]}... assumed settled ({self.settlement_timeout_seconds}s timeout)")
        
        threading.Thread(target=fallback, daemon=True).start()

    def _on_websocket_trade(self, price: float):
        """Handle incoming trade from WebSocket (runs in WebSocket thread).
        
        HYBRID MODE: Combines Train of Trade (target prices) with Spike Sam (fade strategy).
        
        Priority Order:
        1. Risk exits (TP/SL/Time) - always checked first
        2. Target price execution - if current_target condition is met
        3. Spike detection - can trigger entries or adjust targets
        """
        with self._state_lock:
            self.prices_seen += 1
            now = datetime.now(timezone.utc)
            self.last_price = price
            self.last_price_time = now

            # Add to history
            self.history.append((now, price))

            # IMMEDIATE BUY on first WebSocket price if REST failed to get initial price
            # This ensures Train of Trade starts even when REST API is unavailable
            if hasattr(self, '_initial_buy_pending') and self._initial_buy_pending:
                if not self.open_position:
                    logger.info(f"[TRAIN_OF_TRADE] Executing IMMEDIATE BUY @ ${price:.4f} (first WSS price)")
                    self._enter("BUY", price, reason="bot_start_immediate_wss")
                    if self.open_position:
                        # Set SELL target based on take profit
                        self._set_sell_target(price, reason="after_initial_buy")
                        logger.info(f"[TRAIN_OF_TRADE] Position opened, SELL target set for TP/SL monitoring")
                self._initial_buy_pending = False  # Only try once

            # Compute multi-window spike
            spike_pct, stats = self._compute_spike_multi_window(price)

            # Emit price update callback for WebSocket broadcasting
            if hasattr(self, '_price_update_callback') and self._price_update_callback:
                try:
                    # Calculate change percentages for different windows
                    change_1m = 0.0
                    change_5m = 0.0
                    change_10m = 0.0
                    
                    if len(self.history) > 60:  # 1 minute at 1 sec intervals
                        old_price = self.history[-60][1]
                        change_1m = (price - old_price) / old_price * 100
                    
                    if len(self.history) > 300:  # 5 minutes
                        old_price = self.history[-300][1]
                        change_5m = (price - old_price) / old_price * 100
                        
                    if len(self.history) > 600:  # 10 minutes
                        old_price = self.history[-600][1]
                        change_10m = (price - old_price) / old_price * 100

                    self._price_update_callback({
                        "price": price,
                        "change_pct_1m": change_1m,
                        "change_pct_5m": change_5m,
                        "change_pct_10m": change_10m
                    })
                except Exception as e:
                    logger.warning(f"Price update callback failed: {e}")

            # Log periodically
            if self.prices_seen % 100 == 0:
                target_info = f"Target: {self.current_target.action}@${self.current_target.price:.4f}" if self.current_target else "No target"
                logger.info(
                    f"[WSS] {price:.4f} | Spike: {spike_pct:+.2f}% | "
                    f"{target_info} | "
                    f"History: {len(self.history)}"
                )

            # 1. RISK EXIT CHECK FIRST (if holding position)
            if self.open_position:
                exit_reason = self._risk_exit(price)
                if exit_reason:
                    self._exit(exit_reason, price)
                    
                    # Rebuy Strategy Logic
                    if self.cfg.rebuy_strategy == "immediate":
                        # Wait for settlement then rebuy at market
                        delay = self.cfg.rebuy_delay_seconds
                        if delay > 0:
                            logger.info(f"[REBUY] Waiting {delay}s delay...")
                            import time
                            time.sleep(delay)
                        
                        self._enter("BUY", price, reason="immediate_rebuy_after_exit")
                        if self.open_position:
                            self._set_sell_target(price, reason="after_rebuy")
                    else:
                        # wait_for_drop
                        drop_pct = self.cfg.rebuy_drop_pct
                        target_price = price * (1 - drop_pct / 100)
                        logger.info(f"[REBUY] Waiting for {drop_pct}% drop to ${target_price:.4f}")
                        self._set_buy_target(target_price, reason="wait_for_drop_after_exit")
                    
                    return

            # 2. TARGET PRICE CHECK (Train of Trade)
            if self._check_target_condition(price):
                self._execute_target(price)
                return

            # 3. INITIAL INVENTORY ACQUISITION (must happen first)
            if self.open_position is None and self._enough_cooldown():
                if not self.initial_inventory_acquired:
                    logger.info("[STRATEGY] Session start - acquiring initial inventory with BUY")
                    self._enter("BUY", price, "initial_inventory_acquisition")
                    if self.open_position:  # Entry was successful
                        self._set_sell_target(price, reason="after_initial_buy")
                    return

            # 4. SPIKE DETECTION (only for wait_for_drop rebuy strategy)
            # When rebuy_strategy == "immediate", we follow Train of Trade cycle:
            # BUY -> Monitor TP/SL -> SELL -> Immediate REBUY -> Repeat (LONG only)
            # When rebuy_strategy == "wait_for_drop", spikes can trigger entries
            if self.open_position is None and self._enough_cooldown():
                # Skip spike-based entries when using immediate rebuy strategy
                # This ensures LONG-only cycle: BUY -> TP/SL -> SELL -> REBUY
                if self.cfg.rebuy_strategy != "immediate":
                    threshold = self.cfg.spike_threshold_pct
                    if abs(spike_pct) >= threshold:
                        self.spikes_detected += 1

                        # Emit spike detected callback
                        if hasattr(self, '_spike_detected_callback') and self._spike_detected_callback:
                            try:
                                self._spike_detected_callback({
                                    "spike_pct": spike_pct,
                                    "threshold_pct": threshold,
                                    "window_sec": stats.get("window_seconds", 0),
                                    "direction": "up" if spike_pct > 0 else "down",
                                    "price": price,
                                    "base_price": None,
                                    "volatility_cv": stats.get("volatility_cv", 0),
                                    "action_taken": None,
                                    "reason": None,
                                })
                            except Exception as e:
                                logger.warning(f"Spike detected callback failed: {e}")

                        # HYBRID: Spike can trigger immediate action or adjust target
                        decision = self.decide_action(spike_pct, price, stats)

                        if decision["action"] != "ignore":
                            action = decision["action"].upper()
                            size = decision["size_usd"]
                            reason = decision["reason"]
                            logger.info(
                                f"[SPIKE_#{self.spikes_detected}] {spike_pct:+.2f}% "
                                f"-> {action} ${size:.2f} "
                                f"({reason}, price={price:.4f})"
                            )
                            self._enter(action, price, reason)

                            # Set appropriate target after entry
                            if self.open_position:
                                if action == "BUY":
                                    self._set_sell_target(price, reason="after_spike_buy")
                                # Note: SELL entries are rare in spike-fade strategy

    def run(self, stop_event: Optional[threading.Event] = None):
        # Lazy client init if not provided
        if self.client is None:
            self.client = Client(self.cfg)
            self.token_id = self.client.resolve_token_id()

        logger.info("=" * 60)
        logger.info("Bot starting...")
        logger.info("=" * 60)
        logger.info(f"Signature mode: {self.cfg.signature_type}")
        logger.info(f"Token: {str(self.token_id)[:30]}...")
        logger.info(f"Trade size: ${self.cfg.default_trade_size_usd:.2f}")
        logger.info(f"Spike threshold: {self.cfg.spike_threshold_pct:.4f}%")
        logger.info(f"Spike windows: {self.cfg.spike_windows_minutes} min")
        logger.info(f"Take profit: {self.cfg.take_profit_pct}% | Stop loss: {self.cfg.stop_loss_pct}%")
        logger.info(f"Max hold: {self.cfg.max_hold_seconds}s ({self.cfg.max_hold_seconds/60:.1f} min)")
        logger.info(f"History size: {self.cfg.price_history_size}")
        logger.info(f"Volatility filter: {self.cfg.use_volatility_filter}")
        logger.info(f"Dry run: {self.cfg.dry_run}")
        if self.cfg.dry_run:
            logger.info("[DRY_RUN] SIMULATION MODE - Orders will NOT be executed")
            logger.info("[DRY_RUN] Price simulation ENABLED for realistic testing")
        logger.info("=" * 60)

        # Enforce daily loss limit before entering main loop
        if self.cfg.daily_loss_limit_usd and self.daily_realized_pnl <= -abs(self.cfg.daily_loss_limit_usd):
            self.trading_halted = True
            logger.warning(f"[LIMIT] Daily loss limit in effect at start: ${self.daily_realized_pnl:.2f} <= -${abs(self.cfg.daily_loss_limit_usd):.2f}")

        # WebSocket mode
        if self.use_websocket:
            logger.info("[WSS_ENABLED] Real-time spike detection (~1 second)")
            self.ws_client = WebSocketSyncWrapper(
                token_id=self.token_id,
                on_trade_callback=self._on_websocket_trade,
                on_connect_callback=lambda: logger.info("[WSS_CONNECTED]"),
                on_disconnect_callback=lambda: logger.warning("[WSS_DISCONNECTED]"),
            )
            self.ws_client.start()

        # Initialize User WebSocket for settlement confirmation
        if self.use_user_websocket:
            try:
                api_creds = self.client.get_api_credentials()
                self.user_ws_client = UserWebSocketSyncWrapper(
                    api_key=api_creds["api_key"],
                    api_secret=api_creds["api_secret"],
                    api_passphrase=api_creds["api_passphrase"],
                    on_trade_confirmed=self._on_settlement_confirmed,
                )
                self.user_ws_client.start()
                logger.info("[USER_WSS] Settlement tracking enabled (soft 2s timeout)")
            except Exception as e:
                logger.warning(f"[USER_WSS] Failed to initialize: {e}, using fallback mode")
                self.user_ws_client = None

        if self.use_websocket:
            # Fetch initial price from REST to populate history
            logger.info("[REST] Fetching initial price from API...")
            initial_price = self._get_price_rest()
            
            # Flag to track if initial buy has been executed
            initial_buy_pending = True
            
            if initial_price:
                self.history.append((datetime.now(timezone.utc), initial_price))
                self.last_price = initial_price
                logger.info(f"   Initial price: {initial_price:.4f}")
                
                # Entry mode control
                if not self.open_position:
                    if self.cfg.entry_mode == "immediate_buy":
                        logger.info(f"[ENTRY_MODE] Immediate BUY @ ${initial_price:.4f}")
                        self._enter("BUY", initial_price, reason="entry_mode_immediate")
                        if self.open_position:
                            self._set_sell_target(initial_price, reason="after_initial_buy")
                            initial_buy_pending = False
                    elif self.cfg.entry_mode == "delayed_buy":
                        delay = max(int(self.cfg.entry_delay_seconds or 0), 0)
                        if delay > 0:
                            logger.info(f"[ENTRY_MODE] Delayed BUY in {delay}s")
                            time.sleep(delay)
                        # Use most recent price if available
                        price = self.last_price or initial_price
                        self._enter("BUY", price, reason="entry_mode_delayed")
                        if self.open_position:
                            self._set_sell_target(price, reason="after_initial_buy")
                            initial_buy_pending = False
                    else:
                        # wait_for_spike => do nothing here
                        logger.info("[ENTRY_MODE] Waiting for spike to enter")
                        initial_buy_pending = False
            else:
                logger.warning("[REST] No initial price - will execute on first WebSocket price per entry_mode")
            
            # Store flag on self so _on_websocket_trade can access it
            self._initial_buy_pending = initial_buy_pending

            # Run monitoring loop for risk checks
            try:
                iteration = 0
                last_rest_fetch = 0
                rest_fetch_interval = 30  # Fetch from REST every 30 seconds as backup

                while True:
                    if stop_event and stop_event.is_set():
                        logger.info("Bot stopping...")
                        break

                    iteration += 1
                    time.sleep(self.cfg.price_poll_interval_sec)

                    # Periodic REST fetch as backup (in case WSS has no activity)
                    now = time.time()
                    if now - last_rest_fetch >= rest_fetch_interval:
                        rest_price = self._get_price_rest()
                        if rest_price:
                            with self._state_lock:
                                # Only log if price changed
                                if rest_price != self.last_price:
                                    logger.info(f"[REST] Price: {rest_price:.4f}")
                                self.history.append((datetime.now(timezone.utc), rest_price))
                                self.last_price = rest_price
                        last_rest_fetch = now

                    # Periodic status and risk check
                    with self._state_lock:
                        if self.open_position:
                            price = self.last_price or self.ws_client.get_polymarket_price()
                            if price:
                                # Check risk exits
                                exit_reason = self._risk_exit(price)
                                if exit_reason:
                                    self._exit(exit_reason, price)

                                # Show position status every 30 iterations
                                if iteration % 30 == 0 and self.open_position:
                                    pnl = self.open_position.calculate_pnl(price)
                                    logger.info(
                                        f"   Position: {self.open_position.position_type} | "
                                        f"Entry: {self.open_position.entry_price:.4f} | "
                                        f"P&L: {pnl['pnl_pct']:+.2f}% | "
                                        f"Held: {self.open_position.age_minutes:.1f}min"
                                    )

                    # Connection status
                    if iteration % 60 == 0:
                        ws_connected = self.ws_client.is_connected()
                        logger.info(
                            f"Status: Price={f'{self.last_price:.4f}' if self.last_price else 'N/A'} | "
                            f"Position={'OPEN' if self.open_position else 'NONE'} | "
                            f"WSS={'OK' if ws_connected else 'FAIL'} | "
                            f"Spikes detected={self.spikes_detected}"
                        )

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt, shutting down...")
            finally:
                if self.ws_client:
                    self.ws_client.stop()
            return

        # REST polling mode (fallback)
        logger.info("[MODE] REST API polling (WebSocket disabled)")
        self._run_rest_mode(stop_event)

    def _run_rest_mode(self, stop_event: Optional[threading.Event] = None):
        """Run bot in REST polling mode."""
        iteration = 0
        while True:
            if stop_event and stop_event.is_set():
                logger.info("Bot stopping...")
                break

            iteration += 1
            try:
                # Get price from REST API
                rest_price = self._get_price_rest()

                # In dry run mode, use simulation between REST fetches
                price = self._get_price_with_simulation(rest_price)
                price_source = "SIMULATED" if self.cfg.dry_run and rest_price is None else "REST"

                if price is None or price <= 0:
                    time.sleep(self.cfg.price_poll_interval_sec)
                    continue

                # Update price tracking
                self.prices_seen += 1
                self.last_price = price
                self.last_price_time = datetime.now(timezone.utc)

                # Add to history
                self.history.append((self.last_price_time, price))

                # Compute multi-window spike
                spike_pct, stats = self._compute_spike_multi_window(price)

                # Periodic detailed logging
                if iteration % 30 == 0 or len(self.history) <= 10:
                    logger.info(
                        f"[{price_source}] {price:.4f} | "
                        f"Spike: {spike_pct:+.2f}% (window: {stats.get('window_seconds', 'N/A')}s) | "
                        f"History: {len(self.history)} | "
                        f"Vol CV: {stats.get('volatility_cv', 0):.2f}%"
                    )

                    # Show position status
                    if self.open_position:
                        pnl = self.open_position.calculate_pnl(price)
                        logger.info(
                            f"   Position: {self.open_position.position_type} | "
                            f"Entry: {self.open_position.entry_price:.4f} | "
                            f"P&L: {pnl['pnl_pct']:+.2f}% | "
                            f"Held: {self.open_position.age_minutes:.1f}min"
                        )

                # Risk-managed exit first
                if self.open_position is not None:
                    reason = self._risk_exit(price)
                    if reason is not None:
                        self._exit(reason, price)

                # Price filtering: skip extreme prices
                if price < 0.01 or price > 0.99:
                    logger.debug(f"Price {price:.4f} outside range [0.01, 0.99], skipping spike check")
                    time.sleep(self.cfg.price_poll_interval_sec)
                    continue

                # Entry logic based on spike-fade strategy
                if self.open_position is None and self._enough_cooldown() and len(self.history) >= 5:
                    threshold = self.cfg.spike_threshold_pct
                    if abs(spike_pct) >= threshold:
                        decision = self.decide_action(spike_pct, price, stats)

                        if decision["action"] != "ignore":
                            action = decision["action"].upper()
                            size = decision["size_usd"]
                            reason = decision["reason"]
                            logger.info(
                                f"[DECISION] {action} ${size:.2f} "
                                f"(reason: {reason}, price={price:.4f})"
                            )
                            self._enter(action, price, reason)

                # Small sleep to prevent CPU spinning
                time.sleep(self.cfg.price_poll_interval_sec)

            except KeyboardInterrupt:
                logger.info("Keyboard interrupt, shutting down...")
                break
            except Exception as e:
                logger.error(f"Error in main loop: {e}")
                time.sleep(self.cfg.price_poll_interval_sec)

    def _get_price_rest(self) -> Optional[float]:
        """Get price from REST API (fallback)."""
        try:
            if self.cfg.use_gamma_primary:
                price = self.client.get_gamma_price(self.token_id)
                if price > 0:
                    return price
            return self.client.get_polymarket_price(self.token_id)
        except Exception as e:
            logger.warning(f"Failed to fetch REST price: {e}")
            return None
