"""Enhanced bot with train-of-trade strategy and fixed threshold/target logic.

The train-of-trade strategy implements a sequential trading approach:
1. Start with no position -> Set target price for BUY
2. When price reaches target -> BUY -> Set target price for SELL
3. When price reaches target -> SELL -> Set target price for BUY
4. Repeat continuously

Target price logic:
- Target is saved to a variable (not computed dynamically)
- Target is set on: bot start (buy target), after buy (sell target), after sell (buy target)
- Compare current market price with saved target
- Execute when: current >= target (sell) or current <= target (buy)

This approach is more predictable and follows a "limit order style" trading pattern.
"""
from __future__ import annotations

import logging
import threading
import uuid
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Optional, Deque, List, Tuple, Dict, Any
from enum import Enum
import json
from pathlib import Path

from .config import Config
from .clob_client import Client


logger = logging.getLogger(__name__)


class TradeState(Enum):
    """States in the train-of-trade cycle."""
    WANT_TO_BUY = "want_to_buy"      # Looking for entry point to buy
    HAVE_BOUGHT = "have_bought"      # Have position, looking for exit
    WANT_TO_SELL = "want_to_sell"    # Looking for entry point to sell (short)
    HAVE_SOLD = "have_sold"          # Have short position, looking for exit


class TargetDirection(Enum):
    """Direction of target price."""
    UP = "up"      # Target is above current (for selling)
    DOWN = "down"  # Target is below current (for buying)


@dataclass
class PriceTarget:
    """A saved target price for trading."""
    target_id: str
    target_price: float
    direction: TargetDirection  # UP for sell target, DOWN for buy target
    action: str  # "buy" or "sell"
    set_at: datetime
    base_price: float  # Price when target was set
    threshold_pct: float  # Threshold percentage used

    def is_triggered(self, current_price: float) -> bool:
        """Check if current price triggers this target."""
        if self.direction == TargetDirection.UP:
            # For sell orders: trigger when current >= target
            return current_price >= self.target_price
        else:
            # For buy orders: trigger when current <= target
            return current_price <= self.target_price

    def distance_pct(self, current_price: float) -> float:
        """Calculate percentage distance to target."""
        if self.target_price == 0:
            return 0.0
        return (self.target_price - current_price) / current_price * 100.0

    def to_dict(self) -> dict:
        return {
            "target_id": self.target_id,
            "target_price": self.target_price,
            "direction": self.direction.value,
            "action": self.action,
            "set_at": self.set_at.isoformat(),
            "base_price": self.base_price,
            "threshold_pct": self.threshold_pct,
        }


@dataclass
class TrainPosition:
    """Position with train-of-trade specific tracking."""
    side: str  # "BUY" (long) or "SELL" (short)
    entry_price: float
    entry_time: datetime
    amount_usd: float
    shares: float = 0.0
    entry_order_id: Optional[str] = None

    # Train-of-trade state
    target: Optional[PriceTarget] = None  # Next target for this position

    @property
    def age_seconds(self) -> float:
        return (datetime.now(timezone.utc) - self.entry_time).total_seconds()

    def calculate_pnl(self, current_price: float) -> Dict[str, float]:
        """Calculate unrealized P&L at current price."""
        if self.side == "BUY":
            pnl_pct = (current_price - self.entry_price) / self.entry_price * 100
        else:  # SELL (short)
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
            "entry_price": self.entry_price,
            "entry_time": self.entry_time.isoformat(),
            "amount_usd": self.amount_usd,
            "shares": self.shares,
            "age_seconds": self.age_seconds,
            "entry_order_id": self.entry_order_id,
            "target": self.target.to_dict() if self.target else None,
        }


class TrainOfTradeBot:
    """Enhanced bot implementing train-of-trade strategy with fixed target logic.

    Key differences from standard bot:
    1. Targets are saved and persisted, not computed dynamically
    2. Trading follows a predictable cycle: buy -> sell -> buy -> sell
    3. Each position has a specific exit target price
    4. Targets are set based on threshold % from entry price
    """

    def __init__(self, config: Config, client: Client, bot_id: Optional[str] = None):
        self.cfg = config
        self.client = client
        self.bot_id = bot_id or f"bot_{uuid.uuid4().hex[:8]}"

        # Resolve token ID
        self.token_id: Optional[str] = None
        try:
            if config.market_token_id:
                self.token_id = config.market_token_id
            else:
                self.token_id = self.client.resolve_token_id(config.market_slug)
        except Exception as e:
            logger.warning(f"Failed to resolve token ID: {e}")
            self.token_id = None

        # Train-of-trade state
        self.current_target: Optional[PriceTarget] = None
        self.position: Optional[TrainPosition] = None
        self.trade_state = TradeState.WANT_TO_BUY  # Start wanting to buy

        # Price tracking
        self.price_history: Deque[Tuple[datetime, float]] = deque(
            maxlen=self.cfg.price_history_size
        )

        # P&L tracking
        self.realized_pnl: float = 0.0
        self.total_trades: int = 0
        self.winning_trades: int = 0
        self.losing_trades: int = 0

        # Statistics
        self.targets_set = 0
        self.targets_hit = 0
        self.start_time: Optional[datetime] = None

        # Thread safety
        self._lock = threading.Lock()
        self._stop_event = threading.Event()

        # State persistence
        self.state_file = Path(f"data/train_bot_{self.bot_id}.json")

        # Callbacks for external notification
        self.on_trade: Optional[callable] = None
        self.on_target_set: Optional[callable] = None
        self.on_target_hit: Optional[callable] = None
        self.on_activity: Optional[callable] = None

        logger.info(f"[TRAIN_BOT] Initialized {self.bot_id} for token {self.token_id}")

    def get_current_price(self) -> Optional[float]:
        """Get current market price."""
        try:
            return self.client.get_polymarket_price(self.token_id)
        except Exception as e:
            logger.error(f"Failed to get price: {e}")
            return None

    def get_mid_price(self) -> Optional[float]:
        """Get mid price from orderbook."""
        try:
            orderbook = self.client.get_orderbook(self.token_id)
            if orderbook:
                best_bid = float(orderbook.get("bids", [{}])[0].get("price", 0)) if orderbook.get("bids") else 0
                best_ask = float(orderbook.get("asks", [{}])[0].get("price", 0)) if orderbook.get("asks") else 0
                if best_bid > 0 and best_ask > 0:
                    return (best_bid + best_ask) / 2
        except Exception as e:
            logger.debug(f"Failed to get mid price: {e}")
        return self.get_current_price()

    def set_buy_target(self, current_price: float) -> PriceTarget:
        """Set a target price for buying.

        Target = current * (1 - threshold_pct/100)
        """
        threshold = self.cfg.spike_threshold_pct / 100
        target_price = current_price * (1 - threshold)

        target = PriceTarget(
            target_id=f"tgt_{uuid.uuid4().hex[:8]}",
            target_price=target_price,
            direction=TargetDirection.DOWN,
            action="buy",
            set_at=datetime.now(timezone.utc),
            base_price=current_price,
            threshold_pct=self.cfg.spike_threshold_pct,
        )

        with self._lock:
            self.current_target = target
            self.trade_state = TradeState.WANT_TO_BUY

        self.targets_set += 1
        self._log_activity(
            "target_set",
            f"Buy target set: {target_price:.4f} (threshold: -{self.cfg.spike_threshold_pct}% from {current_price:.4f})"
        )

        if self.on_target_set:
            self.on_target_set(target.to_dict())

        return target

    def set_sell_target(self, current_price: float, entry_price: Optional[float] = None) -> PriceTarget:
        """Set a target price for selling.

        For selling a long position:
        - Use take_profit_pct from entry if we have a position
        - Otherwise use threshold_pct from current

        Target = entry * (1 + take_profit/100) or current * (1 + threshold/100)
        """
        if entry_price and self.position:
            # We have a position - use TP/SL logic
            threshold = self.cfg.take_profit_pct / 100
            base = entry_price
        else:
            # No position - use spike threshold
            threshold = self.cfg.spike_threshold_pct / 100
            base = current_price

        target_price = base * (1 + threshold)

        target = PriceTarget(
            target_id=f"tgt_{uuid.uuid4().hex[:8]}",
            target_price=target_price,
            direction=TargetDirection.UP,
            action="sell",
            set_at=datetime.now(timezone.utc),
            base_price=base,
            threshold_pct=threshold * 100,
        )

        with self._lock:
            self.current_target = target
            self.trade_state = TradeState.HAVE_BOUGHT if self.position else TradeState.WANT_TO_SELL

        self.targets_set += 1
        self._log_activity(
            "target_set",
            f"Sell target set: {target_price:.4f} (threshold: +{threshold * 100}% from {base:.4f})"
        )

        if self.on_target_set:
            self.on_target_set(target.to_dict())

        return target

    def check_target(self, current_price: float) -> Optional[PriceTarget]:
        """Check if current price triggers the target.

        Returns the triggered target if any, None otherwise.
        """
        with self._lock:
            if not self.current_target:
                return None

            target = self.current_target

        if target.is_triggered(current_price):
            self.targets_hit += 1
            self._log_activity(
                "target_hit",
                f"Target hit: {target.action.upper()} @ {current_price:.4f} (target was {target.target_price:.4f})"
            )

            if self.on_target_hit:
                self.on_target_hit(target.to_dict())

            return target

        return None

    def execute_trade(self, side: str, amount_usd: Optional[float] = None) -> Optional[Dict[str, Any]]:
        """Execute a trade and update state.

        Returns:
            Dict with trade result or None if failed
        """
        amount = amount_usd or self.cfg.default_trade_size_usd

        logger.info(f"[TRADE] Executing {side.upper()} ${amount:.2f}")

        try:
            result = self.client.place_market_order(
                side=side,
                amount_usd=amount,
                token_id=self.token_id
            )

            if not result.success:
                error_msg = result.response.get("error") or result.response.get("message") or str(result.response)
                self._log_activity(
                    "error",
                    f"{side.upper()} order failed: {error_msg}"
                )
                return None

            self.total_trades += 1

            # Extract order_id and price from response
            order_id = result.response.get("orderID") or result.response.get("order_id") or "N/A"
            price = result.response.get("avgPrice") or result.response.get("price") or 0

            trade_result = {
                "side": side,
                "amount_usd": amount,
                "price": price,
                "order_id": order_id,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

            self._log_activity(
                "order",
                f"Order filled: {side.upper()} ${amount:.2f} @ {result.price:.4f}"
            )

            if self.on_trade:
                self.on_trade(trade_result)

            return trade_result

        except Exception as e:
            logger.error(f"Trade execution failed: {e}")
            self._log_activity("error", f"Trade error: {str(e)}")
            return None

    def enter_long(self, current_price: float) -> bool:
        """Enter a long position (BUY).

        1. Execute BUY order
        2. Create TrainPosition
        3. Set sell target for exit

        Returns True if successful
        """
        trade = self.execute_trade("buy")
        if not trade:
            return False

        # Create position
        with self._lock:
            self.position = TrainPosition(
                side="BUY",
                entry_price=trade["price"],
                entry_time=datetime.now(timezone.utc),
                amount_usd=trade["amount_usd"],
                entry_order_id=trade.get("order_id"),
            )
            self.trade_state = TradeState.HAVE_BOUGHT

        # Set sell target
        self.set_sell_target(trade["price"], trade["price"])

        return True

    def exit_long(self, current_price: float) -> bool:
        """Exit a long position (SELL).

        1. Execute SELL order
        2. Calculate P&L
        3. Clear position
        4. Set buy target for re-entry

        Returns True if successful
        """
        if not self.position:
            logger.warning("No position to exit")
            return False

        trade = self.execute_trade("sell", self.position.amount_usd)
        if not trade:
            return False

        # Calculate P&L
        pnl = self.position.calculate_pnl(trade["price"])
        self.realized_pnl += pnl["pnl_usd"]

        if pnl["pnl_usd"] > 0:
            self.winning_trades += 1
        else:
            self.losing_trades += 1

        self._log_activity(
            "pnl",
            f"Trade closed: P&L = ${pnl['pnl_usd']:+.2f} ({pnl['pnl_pct']:+.2f}%)"
        )

        # Clear position and set buy target
        with self._lock:
            self.position = None
            self.current_target = None
            self.trade_state = TradeState.WANT_TO_BUY

        # Set next buy target
        self.set_buy_target(trade["price"])

        return True

    def check_risk_exit(self, current_price: float) -> Optional[str]:
        """Check if position should be exited based on risk rules.

        Returns:
            Exit reason if should exit, None otherwise
        """
        if not self.position:
            return None

        pos = self.position

        # Time-based exit
        if pos.age_seconds >= self.cfg.max_hold_seconds:
            return f"time_exit_{pos.age_seconds:.0f}s"

        # P&L-based exit
        pnl = pos.calculate_pnl(current_price)

        if pnl["pnl_pct"] >= self.cfg.take_profit_pct:
            return f"take_profit_+{pnl['pnl_pct']:.2f}%"

        if pnl["pnl_pct"] <= -self.cfg.stop_loss_pct:
            return f"stop_loss_{pnl['pnl_pct']:.2f}%"

        return None

    def process_tick(self, current_price: float) -> Optional[Dict[str, Any]]:
        """Process a price tick and take action if needed.

        This is the main method called on each price update.

        Args:
            current_price: Current market price

        Returns:
            Dict with action taken or None
        """
        # Add to history
        self.price_history.append((datetime.now(timezone.utc), current_price))

        # Check risk exit first if we have a position
        if self.position:
            exit_reason = self.check_risk_exit(current_price)
            if exit_reason:
                self._log_activity("exit", f"Risk exit: {exit_reason}")
                if self.exit_long(current_price):
                    return {"action": "risk_exit", "reason": exit_reason, "price": current_price}

        # Check if target is hit
        triggered_target = self.check_target(current_price)
        if triggered_target:
            action = triggered_target.action

            if action == "buy":
                if not self.position:
                    if self.enter_long(current_price):
                        return {"action": "buy", "reason": "target_hit", "price": current_price}

            elif action == "sell":
                if self.position:
                    if self.exit_long(current_price):
                        return {"action": "sell", "reason": "target_hit", "price": current_price}

        return None

    def initialize_targets(self, current_price: Optional[float] = None):
        """Initialize the first target based on current state.

        Should be called when bot starts to set the initial target.
        """
        price = current_price or self.get_current_price()
        if price is None:
            logger.warning("Cannot initialize targets - no price available")
            return

        # If we have a position, set appropriate exit target
        if self.position:
            if self.position.side == "BUY":
                self.set_sell_target(price, self.position.entry_price)
            else:
                self.set_buy_target(price)
        else:
            # No position - start with buy target
            self.set_buy_target(price)

    def get_status(self) -> Dict[str, Any]:
        """Get current bot status."""
        current_price = self.get_current_price()

        status = {
            "bot_id": self.bot_id,
            "token_id": self.token_id,
            "trade_state": self.trade_state.value,
            "current_target": self.current_target.to_dict() if self.current_target else None,
            "position": self.position.to_dict() if self.position else None,
            "current_price": current_price,
            "realized_pnl": self.realized_pnl,
            "total_trades": self.total_trades,
            "winning_trades": self.winning_trades,
            "losing_trades": self.losing_trades,
            "targets_set": self.targets_set,
            "targets_hit": self.targets_hit,
        }

        if self.current_target and current_price:
            status["target_distance_pct"] = self.current_target.distance_pct(current_price)

        return status

    def _log_activity(self, activity_type: str, message: str):
        """Log an activity event."""
        activity = {
            "id": f"act_{uuid.uuid4().hex[:8]}",
            "bot_id": self.bot_id,
            "timestamp": datetime.now(timezone.utc).timestamp(),
            "type": activity_type,
            "message": message,
        }

        logger.info(f"[{activity_type.upper()}] {message}")

        if self.on_activity:
            self.on_activity(activity)

    def save_state(self):
        """Save bot state to file."""
        try:
            self.state_file.parent.mkdir(parents=True, exist_ok=True)

            state = {
                "bot_id": self.bot_id,
                "token_id": self.token_id,
                "trade_state": self.trade_state.value,
                "current_target": self.current_target.to_dict() if self.current_target else None,
                "position": self.position.to_dict() if self.position else None,
                "realized_pnl": self.realized_pnl,
                "total_trades": self.total_trades,
                "winning_trades": self.winning_trades,
                "losing_trades": self.losing_trades,
                "targets_set": self.targets_set,
                "targets_hit": self.targets_hit,
                "start_time": self.start_time.isoformat() if self.start_time else None,
            }

            self.state_file.write_text(json.dumps(state, default=str))
        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def load_state(self):
        """Load bot state from file."""
        try:
            if not self.state_file.exists():
                return

            state = json.loads(self.state_file.read_text())

            # Verify token ID matches
            saved_token = state.get("token_id")
            if saved_token and saved_token != self.token_id:
                logger.warning(f"State file is for different token ({saved_token} vs {self.token_id})")
                return

            # Load trade state
            self.trade_state = TradeState(state.get("trade_state", TradeState.WANT_TO_BUY.value))

            # Load target
            target_data = state.get("current_target")
            if target_data:
                self.current_target = PriceTarget(
                    target_id=target_data["target_id"],
                    target_price=target_data["target_price"],
                    direction=TargetDirection(target_data["direction"]),
                    action=target_data["action"],
                    set_at=datetime.fromisoformat(target_data["set_at"]),
                    base_price=target_data["base_price"],
                    threshold_pct=target_data["threshold_pct"],
                )

            # Load position
            pos_data = state.get("position")
            if pos_data:
                target = None
                if pos_data.get("target"):
                    t = pos_data["target"]
                    target = PriceTarget(
                        target_id=t["target_id"],
                        target_price=t["target_price"],
                        direction=TargetDirection(t["direction"]),
                        action=t["action"],
                        set_at=datetime.fromisoformat(t["set_at"]),
                        base_price=t["base_price"],
                        threshold_pct=t["threshold_pct"],
                    )

                self.position = TrainPosition(
                    side=pos_data["side"],
                    entry_price=pos_data["entry_price"],
                    entry_time=datetime.fromisoformat(pos_data["entry_time"]),
                    amount_usd=pos_data["amount_usd"],
                    shares=pos_data.get("shares", 0),
                    entry_order_id=pos_data.get("entry_order_id"),
                    target=target,
                )

            # Load stats
            self.realized_pnl = state.get("realized_pnl", 0.0)
            self.total_trades = state.get("total_trades", 0)
            self.winning_trades = state.get("winning_trades", 0)
            self.losing_trades = state.get("losing_trades", 0)
            self.targets_set = state.get("targets_set", 0)
            self.targets_hit = state.get("targets_hit", 0)

            if state.get("start_time"):
                self.start_time = datetime.fromisoformat(state["start_time"])

            logger.info(f"[TRAIN_BOT] State loaded for {self.bot_id}")

        except Exception as e:
            logger.error(f"Failed to load state: {e}")

    def run(self, stop_event: Optional[threading.Event] = None):
        """Run the train-of-trade bot loop.

        This is the main entry point for running the bot continuously.
        It will:
        1. Initialize targets based on current price
        2. Poll for price updates
        3. Check if targets are hit
        4. Execute trades accordingly

        Args:
            stop_event: Threading event to signal stop (uses internal if None)
        """
        if stop_event is None:
            stop_event = self._stop_event

        self.start_time = datetime.now(timezone.utc)
        logger.info(f"[TRAIN_BOT] Starting run loop for {self.bot_id}")

        # Load any saved state
        self.load_state()

        # Initialize targets if not already set
        if not self.current_target:
            self.initialize_targets()

        if not self.current_target:
            logger.error("[TRAIN_BOT] Failed to initialize targets - cannot start")
            return

        logger.info(f"[TRAIN_BOT] Initial target: {self.current_target.action} @ {self.current_target.target_price:.4f}")

        # Main trading loop
        last_price = None
        loop_count = 0

        while not stop_event.is_set():
            try:
                # Get current price
                current_price = self.get_current_price()

                if current_price is None:
                    logger.debug("[TRAIN_BOT] No price available, waiting...")
                    stop_event.wait(self.cfg.price_poll_interval_sec)
                    continue

                # Only log on significant price changes
                if last_price is None or abs(current_price - last_price) / last_price > 0.001:
                    loop_count += 1

                    # Log target distance every 30 ticks
                    if loop_count % 30 == 0 and self.current_target:
                        distance = self.current_target.distance_pct(current_price)
                        logger.info(
                            f"[TRAIN_BOT] Price: {current_price:.4f} | "
                            f"Target: {self.current_target.action.upper()} @ {self.current_target.target_price:.4f} "
                            f"({distance:+.2f}%)"
                        )

                    last_price = current_price

                # Process the tick - this checks targets and executes trades
                action = self.process_tick(current_price)

                if action:
                    logger.info(f"[TRAIN_BOT] Action taken: {action}")

                    # Save state after any action
                    self.save_state()

                # Small sleep to avoid tight loop
                stop_event.wait(self.cfg.price_poll_interval_sec)

            except KeyboardInterrupt:
                logger.info("[TRAIN_BOT] Keyboard interrupt received")
                break
            except Exception as e:
                logger.error(f"[TRAIN_BOT] Error in run loop: {e}")
                stop_event.wait(5.0)  # Wait longer on error

        # Cleanup
        logger.info(f"[TRAIN_BOT] Stopping run loop for {self.bot_id}")
        self.save_state()

    def stop(self):
        """Signal the bot to stop."""
        self._stop_event.set()

    @property
    def uptime_seconds(self) -> float:
        """Get bot uptime in seconds."""
        if self.start_time:
            return (datetime.now(timezone.utc) - self.start_time).total_seconds()
        return 0.0

    @property
    def is_running(self) -> bool:
        """Check if bot is currently running."""
        return not self._stop_event.is_set()
