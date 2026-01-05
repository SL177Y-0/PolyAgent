"""Polymarket WebSocket client for real-time market data.

Connects to wss://ws-subscriptions-clob.polymarket.com/ws/market for live
orderbook, trade prices, and price changes. Provides callbacks for different
event types.

Based on Polymarket documentation:
https://docs.polymarket.com/developers/CLOB/websocket/market-channel

Updated with correct subscription format:
{"type": "market", "assets_ids": ["token_id"]}
"""
from __future__ import annotations

import asyncio
import json
import logging
from typing import Optional, Callable, Dict, Any
from datetime import datetime, timezone

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger(__name__)


# Correct WebSocket endpoint from Polymarket docs
WS_MARKET_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/market"


class PolymarketWebSocketClient:
    """Real-time WebSocket client for Polymarket CLOB data.

    Event types received:
    - book: Full orderbook snapshot
    - price_change: Individual price level updates
    - last_trade_price: Actual trade prices (most accurate for spike detection)
    - best_bid_ask: Current best bid/ask with spread

    Usage:
        async def on_price(data):
            print(f"Price: {data['price']}")

        client = PolymarketWebSocketClient(token_id="...")
        client.on_last_trade_price = on_price
        await client.connect()
    """

    def __init__(
        self,
        token_id: str,
        on_book: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_price_change: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_last_trade_price: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_best_bid_ask: Optional[Callable[[Dict[str, Any]], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
        on_connect: Optional[Callable[[], None]] = None,
        on_disconnect: Optional[Callable[[], None]] = None,
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library required. Install with: pip install websockets"
            )

        self.token_id = token_id
        self.ws: Optional[Any] = None
        self.running = False
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 60.0

        # Callbacks for different event types
        self.on_book = on_book
        self.on_price_change = on_price_change
        self.on_last_trade_price = on_last_trade_price
        self.on_best_bid_ask = on_best_bid_ask
        self.on_error = on_error
        self.on_connect = on_connect
        self.on_disconnect = on_disconnect

        # Latest data cache
        self.latest_price: Optional[float] = None
        self.latest_best_bid: Optional[float] = None
        self.latest_best_ask: Optional[float] = None
        self.latest_timestamp: Optional[int] = None
        self.last_update_time: Optional[datetime] = None

        # Statistics
        self.messages_received = 0
        self.last_message_type: Optional[str] = None
        self.connection_count = 0

    async def connect(self) -> None:
        """Connect to WebSocket and subscribe to market data."""
        self.running = True
        retry_count = 0

        while self.running:
            try:
                logger.info(f"Connecting to {WS_MARKET_URL}...")
                self.connection_count += 1

                async with websockets.connect(
                    WS_MARKET_URL,
                    ping_interval=20,
                    ping_timeout=60,
                    close_timeout=10,
                ) as websocket:
                    self.ws = websocket
                    logger.info("WebSocket connected!")

                    # Reset retry count on successful connection
                    retry_count = 0

                    # Subscribe to market data using correct format from Polymarket docs
                    # Format: {"type": "market", "assets_ids": ["token_id"]}
                    await self._subscribe()

                    if self.on_connect:
                        try:
                            self.on_connect()
                        except Exception as e:
                            logger.error(f"Error in connect callback: {e}")

                    # Process messages
                    async for message in websocket:
                        if not self.running:
                            break
                        await self._handle_message(message)

            except asyncio.CancelledError:
                logger.info("WebSocket connection cancelled")
                break
            except Exception as e:
                logger.warning(f"WebSocket error: {e}")

                if self.on_error:
                    try:
                        self.on_error(e)
                    except Exception:
                        pass

                if self.on_disconnect:
                    try:
                        self.on_disconnect()
                    except Exception:
                        pass

                # Exponential backoff for reconnection
                delay = min(
                    self.reconnect_delay * (2 ** retry_count),
                    self.max_reconnect_delay,
                )
                retry_count += 1
                logger.info(f"Reconnecting in {delay:.1f} seconds... (attempt {retry_count})")
                await asyncio.sleep(delay)

    async def _subscribe(self) -> None:
        """Subscribe to market data for the token.

        Uses the correct subscription format from Polymarket docs:
        {"type": "market", "assets_ids": ["token_id"]}
        """
        subscribe_msg = {
            "type": "market",
            "assets_ids": [self.token_id],
        }
        await self.ws.send(json.dumps(subscribe_msg))
        logger.info(f"Subscribed to market for token {self.token_id[:20]}...")

    async def _handle_message(self, message: str) -> None:
        """Parse and dispatch incoming WebSocket messages."""
        try:
            data = json.loads(message)

            # Handle empty array messages (initial subscription response)
            if isinstance(data, list):
                if len(data) == 0:
                    logger.debug("Received empty array (subscription ack)")
                    return
                # If array has content, use first element
                if len(data) > 0:
                    data = data[0]

            self.messages_received += 1

            event_type = data.get("event_type", "") if isinstance(data, dict) else ""
            self.last_message_type = event_type
            self.last_update_time = datetime.now(timezone.utc)

            # Extract timestamp if available
            if isinstance(data, dict) and "timestamp" in data:
                self.latest_timestamp = int(data["timestamp"])

            # Log first few messages for debugging
            if self.messages_received <= 5:
                logger.debug(f"Received message #{self.messages_received}: {event_type} - {str(data)[:200]}")

            if event_type == "book":
                # Full orderbook snapshot
                try:
                    self._handle_book(data)
                except Exception as e:
                    logger.debug(f"Error in book handler: {e}")
                if self.on_book:
                    try:
                        self.on_book(data)
                    except Exception as e:
                        logger.error(f"Error in book callback: {e}")

            elif event_type == "price_change":
                # Individual price level update
                self._handle_price_change(data)
                if self.on_price_change:
                    try:
                        self.on_price_change(data)
                    except Exception as e:
                        logger.error(f"Error in price_change callback: {e}")

            elif event_type == "last_trade_price":
                # Actual trade occurred - most accurate price
                price = float(data.get("price", 0))
                self.latest_price = price
                if self.on_last_trade_price:
                    try:
                        self.on_last_trade_price(data)
                    except Exception as e:
                        logger.error(f"Error in last_trade_price callback: {e}")

                logger.info(
                    f"[TRADE] {price:.4f} {data.get('side', 'N/A')} "
                    f"size={data.get('size', 'N/A')}"
                )

            elif event_type == "best_bid_ask":
                # Best bid/ask update
                self._handle_best_bid_ask(data)
                if self.on_best_bid_ask:
                    try:
                        self.on_best_bid_ask(data)
                    except Exception as e:
                        logger.error(f"Error in best_bid_ask callback: {e}")

            elif event_type == "tick_size_change":
                logger.debug(f"Tick size changed: {data}")

            elif event_type in ("new_market", "market_resolved"):
                logger.info(f"Market event: {event_type}")

            else:
                logger.debug(f"Unknown event type: {event_type}")

        except json.JSONDecodeError:
            logger.warning(f"Failed to parse message: {message[:200]}")
        except Exception as e:
            # Log the actual message for debugging
            logger.error(f"Error handling message: {e} | Message: {message[:500]}")

    def _handle_book(self, data: Dict[str, Any]) -> None:
        """Extract price from orderbook snapshot."""
        try:
            # Calculate mid-price from orderbook
            bids = data.get("bids", [])
            asks = data.get("asks", [])

            if bids and asks:
                # bids/asks can be lists of [price, size] or dicts with price/size keys
                best_bid = 0
                best_ask = 0

                # Handle list format [price, size]
                if isinstance(bids[0], list):
                    best_bid = float(bids[0][0]) if bids and len(bids[0]) > 0 else 0
                # Handle dict format {"price": ..., "size": ...}
                elif isinstance(bids[0], dict):
                    best_bid = float(bids[0].get("price", 0))

                if isinstance(asks[0], list):
                    best_ask = float(asks[0][0]) if asks and len(asks[0]) > 0 else 0
                elif isinstance(asks[0], dict):
                    best_ask = float(asks[0].get("price", 0))

                self.latest_best_bid = best_bid
                self.latest_best_ask = best_ask

                # Use mid-price if no trade price available
                if best_bid > 0 and best_ask > 0:
                    mid = (best_bid + best_ask) / 2
                    if self.latest_price is None:
                        self.latest_price = mid

        except Exception as e:
            logger.warning(f"Error parsing book data: {e}")

    def _handle_price_change(self, data: Dict[str, Any]) -> None:
        """Extract best bid/ask from price change event."""
        try:
            best_bid = float(data.get("best_bid", 0))
            best_ask = float(data.get("best_ask", 0))
            self.latest_best_bid = best_bid
            self.latest_best_ask = best_ask

        except Exception as e:
            logger.warning(f"Error parsing price_change: {e}")

    def _handle_best_bid_ask(self, data: Dict[str, Any]) -> None:
        """Handle best bid/ask event."""
        try:
            bid = float(data.get("best_bid", 0))
            ask = float(data.get("best_ask", 0))
            self.latest_best_bid = bid
            self.latest_best_ask = ask

        except Exception as e:
            logger.warning(f"Error parsing best_bid_ask: {e}")

    def get_polymarket_price(self) -> Optional[float]:
        """Get price using Polymarket's official pricing logic.

        Follows the same logic as polymarket.com:
        - If spread <= 0.10: midpoint of best bid/ask
        - If spread > 0.10: last trade price

        Returns:
            The price according to Polymarket's logic, or None if unavailable
        """
        # Check if we have bid/ask data
        if (
            self.latest_best_bid is not None
            and self.latest_best_ask is not None
            and self.latest_best_bid > 0
            and self.latest_best_ask > 0
        ):
            spread = self.latest_best_ask - self.latest_best_bid

            # Polymarket's official logic: use midpoint if spread <= 0.10
            if spread <= 0.10:
                return (self.latest_best_bid + self.latest_best_ask) / 2
            else:
                # Spread too wide - use last trade price
                if self.latest_price is not None:
                    return self.latest_price
                # Fallback to midpoint if no last trade
                return (self.latest_best_bid + self.latest_best_ask) / 2

        # No bid/ask data - return last trade price if available
        return self.latest_price

    def get_mid_price(self) -> Optional[float]:
        """Get the current mid-price from best bid/ask.

        Note: For Polymarket's official pricing logic, use get_polymarket_price() instead.
        """
        if (
            self.latest_best_bid is not None
            and self.latest_best_ask is not None
            and self.latest_best_bid > 0
            and self.latest_best_ask > 0
        ):
            return (self.latest_best_bid + self.latest_best_ask) / 2
        return self.latest_price

    def get_best_bid_ask(self) -> tuple[Optional[float], Optional[float]]:
        """Get current best bid and ask."""
        return self.latest_best_bid, self.latest_best_ask

    def stop(self) -> None:
        """Stop the WebSocket connection."""
        logger.info("Stopping WebSocket client...")
        self.running = False

    def get_statistics(self) -> Dict[str, Any]:
        """Get connection statistics."""
        return {
            "messages_received": self.messages_received,
            "last_message_time": self.last_update_time.isoformat() if self.last_update_time else None,
            "connection_count": self.connection_count,
            "is_connected": self.is_connected(),
        }

    def is_connected(self) -> bool:
        """Check if WebSocket is connected and receiving data."""
        if self.last_update_time is None:
            return False
        # Consider connected if received message in last 30 seconds
        return (datetime.now(timezone.utc) - self.last_update_time).total_seconds() < 30


def create_websocket_client(token_id: str) -> PolymarketWebSocketClient:
    """Factory function to create a WebSocket client."""
    return PolymarketWebSocketClient(token_id)


# Synchronous wrapper for use in blocking code
class WebSocketSyncWrapper:
    """Synchronous wrapper for the async WebSocket client.

    Runs the async WebSocket loop in a background thread and provides
    thread-safe access to latest prices.
    """

    def __init__(
        self,
        token_id: str,
        on_trade_callback: Optional[Callable[[float], None]] = None,
        on_connect_callback: Optional[Callable[[], None]] = None,
        on_disconnect_callback: Optional[Callable[[], None]] = None,
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError(
                "websockets library required. Install with: pip install websockets"
            )

        self.token_id = token_id
        self.on_trade_callback = on_trade_callback
        self.on_connect_callback = on_connect_callback
        self.on_disconnect_callback = on_disconnect_callback

        # Create async client with callbacks
        self.client = PolymarketWebSocketClient(
            token_id=token_id,
            on_last_trade_price=self._on_trade,
            on_best_bid_ask=self._on_best_bid_ask,
            on_connect=self._on_connect,
            on_disconnect=self._on_disconnect,
        )

        # Background thread for running async loop
        self.loop: Optional[asyncio.AbstractEventLoop] = None
        self.thread: Optional[Any] = None
        self._running = False

        # Thread-safe latest price
        import threading
        self._lock = threading.Lock()
        self._latest_trade_price: Optional[float] = None
        self._latest_best_bid: Optional[float] = None
        self._latest_best_ask: Optional[float] = None

    def _on_trade(self, data: Dict[str, Any]) -> None:
        """Handle trade price update in async context."""
        price = float(data.get("price", 0))
        with self._lock:
            self._latest_trade_price = price

        # Call user callback if provided
        if self.on_trade_callback:
            try:
                self.on_trade_callback(price)
            except Exception as e:
                logger.error(f"Error in trade callback: {e}")

    def _on_best_bid_ask(self, data: Dict[str, Any]) -> None:
        """Handle best bid/ask update."""
        bid = float(data.get("best_bid", 0))
        ask = float(data.get("best_ask", 0))
        with self._lock:
            self._latest_best_bid = bid
            self._latest_best_ask = ask

    def _on_connect(self) -> None:
        """Handle connection event."""
        if self.on_connect_callback:
            try:
                self.on_connect_callback()
            except Exception as e:
                logger.error(f"Error in connect callback: {e}")

    def _on_disconnect(self) -> None:
        """Handle disconnect event."""
        if self.on_disconnect_callback:
            try:
                self.on_disconnect_callback()
            except Exception as e:
                logger.error(f"Error in disconnect callback: {e}")

    def start(self) -> None:
        """Start the WebSocket client in a background thread."""
        import threading

        def run_loop():
            self.loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self.loop)
            self._running = True
            try:
                self.loop.run_until_complete(self.client.connect())
            finally:
                self._running = False

        self.thread = threading.Thread(target=run_loop, daemon=True)
        self.thread.start()
        logger.info("WebSocket client started in background thread")

        # Give it time to connect
        import time
        time.sleep(2)

    def stop(self) -> None:
        """Stop the WebSocket client."""
        self.client.stop()
        self._running = False
        if self.loop and not self.loop.is_closed():
            try:
                self.loop.call_soon_threadsafe(self.loop.stop)
            except RuntimeError:
                # Loop already stopped, this is fine
                pass
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)

    def get_latest_trade_price(self) -> Optional[float]:
        """Get the most recent trade price (thread-safe)."""
        with self._lock:
            return self._latest_trade_price

    def get_best_bid_ask(self) -> tuple[Optional[float], Optional[float]]:
        """Get current best bid and ask (thread-safe)."""
        with self._lock:
            return self._latest_best_bid, self._latest_best_ask

    def get_polymarket_price(self) -> Optional[float]:
        """Get price using Polymarket's official pricing logic (thread-safe).

        Follows the same logic as polymarket.com:
        - If spread <= 0.10: midpoint of best bid/ask
        - If spread > 0.10: last trade price

        Returns:
            The price according to Polymarket's logic, or None if unavailable
        """
        with self._lock:
            bid = self._latest_best_bid
            ask = self._latest_best_ask
            last_trade = self._latest_trade_price

        if bid and ask and bid > 0 and ask > 0:
            spread = ask - bid

            # Polymarket's official logic
            if spread <= 0.10:
                return (bid + ask) / 2
            else:
                # Spread too wide - use last trade price
                if last_trade is not None and last_trade > 0:
                    return last_trade
                # Fallback to midpoint
                return (bid + ask) / 2

        # No bid/ask - return last trade
        return last_trade

    def get_mid_price(self) -> Optional[float]:
        """Get mid-price from best bid/ask (thread-safe).

        Note: For Polymarket's official pricing logic, use get_polymarket_price() instead.
        """
        bid, ask = self.get_best_bid_ask()
        if bid and ask and bid > 0 and ask > 0:
            return (bid + ask) / 2
        return self.get_latest_trade_price()

    def is_connected(self) -> bool:
        """Check if the WebSocket is connected and receiving data."""
        return self._running and self.client.is_connected()
