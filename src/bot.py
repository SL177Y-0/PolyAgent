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

from .config import Config
from .clob_client import Client

try:
    from .websocket_client import WebSocketSyncWrapper
    WEBSOCKET_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"WebSocket import failed: {e}")
    WEBSOCKET_AVAILABLE = False

logger = logging.getLogger(__name__)


@dataclass
class Position:
    side: str  # BUY -> LONG, SELL -> SHORT
    entry_price: float
    entry_time: datetime
    amount_usd: float

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
        self.last_exit_time: Optional[datetime] = None  # Track exit for settlement delay

        # Settlement delay (seconds to wait after exit before new entry)
        self.settlement_delay_seconds = 2.0

        # Persistence
        self.state_file = Path("data/position.json")
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

        # Check volatility filter
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
            }
            self.state_file.write_text(json.dumps(data, default=str))
        except Exception:
            pass

    def _load_state(self):
        try:
            if self.state_file.exists():
                data = json.loads(self.state_file.read_text())
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
        except Exception:
            pass

    def _enter(self, side: str, price: float, reason: str = ""):
        """Enter a position with intelligent pre-checks and error handling.

        If order placement fails, the position is NOT opened (preventing tracking issues).
        """
        # First, try to place the order
        logger.info(f"[ENTRY] Attempting {side.upper()} ${self.cfg.default_trade_size_usd:.2f} at {price:.4f} ({reason})")

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
            self.open_position = Position(
                side=side.upper(),
                entry_price=price,
                entry_time=datetime.now(timezone.utc),
                amount_usd=self.cfg.default_trade_size_usd,
            )
            self.last_signal_time = datetime.now(timezone.utc)
            logger.info(f"[POSITION_OPENED] {side.upper()} ${self.cfg.default_trade_size_usd:.2f} at {price:.4f}")

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

        # Calculate realized P&L
        pnl = pos.calculate_pnl(price)
        pnl_pct = pnl["pnl_pct"]
        pnl_usd = pnl["pnl_usd"]

        self.realized_pnl += pnl_usd
        self.total_trades += 1
        if pnl_usd > 0:
            self.winning_trades += 1

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
                filled = result.response.get('data', {}).get('filledAmount', 'N/A')
                logger.info(f"[ORDER_FILLED] ID={order_id} | Shares: {filled}")
                # Track exit time for settlement delay
                self.last_exit_time = datetime.now(timezone.utc)
        except Exception as e:
            logger.warning(f"[EXIT_FAILED] {e}")

        self.open_position = None
        self.last_signal_time = datetime.now(timezone.utc)
        self._save_state()

    def _on_websocket_trade(self, price: float):
        """Handle incoming trade from WebSocket."""
        self.prices_seen += 1
        now = datetime.now(timezone.utc)
        self.last_price = price
        self.last_price_time = now

        # Add to history
        self.history.append((now, price))

        # Compute multi-window spike
        spike_pct, stats = self._compute_spike_multi_window(price)

        # Log periodically
        if self.prices_seen % 100 == 0:
            logger.info(
                f"[WSS] {price:.4f} | Spike: {spike_pct:+.2f}% | "
                f"History: {len(self.history)} | "
                f"Vol CV: {stats.get('volatility_cv', 0):.2f}%"
            )

        # Risk exit check first
        if self.open_position:
            exit_reason = self._risk_exit(price)
            if exit_reason:
                self._exit(exit_reason, price)
                return

        # Entry logic
        if self.open_position is None and self._enough_cooldown():
            threshold = self.cfg.spike_threshold_pct
            if abs(spike_pct) >= threshold:
                self.spikes_detected += 1
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

    def run(self):
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
        logger.info("=" * 60)

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

            # Fetch initial price from REST to populate history
            logger.info("[REST] Fetching initial price from API...")
            initial_price = self._get_price_rest()
            if initial_price:
                self.history.append((datetime.now(timezone.utc), initial_price))
                self.last_price = initial_price
                logger.info(f"   Initial price: {initial_price:.4f}")

            # Run monitoring loop for risk checks
            try:
                iteration = 0
                last_rest_fetch = 0
                rest_fetch_interval = 30  # Fetch from REST every 30 seconds as backup

                while True:
                    iteration += 1
                    time.sleep(self.cfg.price_poll_interval_sec)

                    # Periodic REST fetch as backup (in case WSS has no activity)
                    now = time.time()
                    if now - last_rest_fetch >= rest_fetch_interval:
                        rest_price = self._get_price_rest()
                        if rest_price:
                            # Only log if price changed
                            if rest_price != self.last_price:
                                logger.info(f"[REST] Price: {rest_price:.4f}")
                            self.history.append((datetime.now(timezone.utc), rest_price))
                            self.last_price = rest_price
                        last_rest_fetch = now

                    # Periodic status and risk check
                    if self.open_position:
                        price = self.last_price or self.ws_client.get_polymarket_price()
                        if price:
                            # Check risk exits
                            exit_reason = self._risk_exit(price)
                            if exit_reason:
                                self._exit(exit_reason, price)

                            # Show position status every 30 iterations
                            if iteration % 30 == 0:
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
        self._run_rest_mode()

    def _run_rest_mode(self):
        """Run bot in REST polling mode."""
        iteration = 0
        while True:
            iteration += 1
            try:
                # Get price from REST API
                price = self._get_price_rest()
                price_source = "REST"

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
