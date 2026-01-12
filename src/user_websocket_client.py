"""Polymarket User WebSocket client for real-time order/trade status updates.

Connects to wss://ws-subscriptions-clob.polymarket.com/ws/user for:
- Order status updates (PLACEMENT, UPDATE, CANCELLATION)
- Trade status updates (MATCHED -> MINED -> CONFIRMED or FAILED)

The key event is trade status "CONFIRMED" which means tokens have settled on-chain.

Based on Polymarket documentation:
https://docs.polymarket.com/developers/CLOB/websocket/user-channel
"""
from __future__ import annotations

import asyncio
import json
import logging
import threading
import time
from typing import Optional, Callable, Dict, Any, Set
from datetime import datetime, timezone
from dataclasses import dataclass

try:
    import websockets
    WEBSOCKETS_AVAILABLE = True
except ImportError:
    WEBSOCKETS_AVAILABLE = False

logger = logging.getLogger(__name__)

WS_USER_URL = "wss://ws-subscriptions-clob.polymarket.com/ws/user"


@dataclass
class PendingSettlement:
    """Tracks a pending order settlement."""
    order_id: str
    created_at: datetime
    confirmed: bool = False
    confirmed_at: Optional[datetime] = None
    status: str = "PENDING"


class UserWebSocketClient:
    """WebSocket client for Polymarket User Channel (authenticated).
    
    Provides real-time order and trade status updates, enabling us to know
    exactly when tokens have settled on-chain (status: CONFIRMED).
    
    Usage:
        client = UserWebSocketClient(
            api_key="...",
            api_secret="...",
            api_passphrase="...",
            on_trade_confirmed=lambda order_id, status: print(f"{order_id}: {status}")
        )
        client.start()
        
        # Wait for settlement
        is_confirmed = client.wait_for_settlement(order_id, timeout_sec=2.0)
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        on_trade_confirmed: Optional[Callable[[str, str], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ):
        if not WEBSOCKETS_AVAILABLE:
            raise ImportError("websockets library required. Install with: pip install websockets")
        
        self.api_key = api_key
        self.api_secret = api_secret
        self.api_passphrase = api_passphrase
        
        # Callbacks
        self.on_trade_confirmed = on_trade_confirmed
        self.on_error = on_error
        
        # Connection state
        self.ws: Optional[Any] = None
        self.running = False
        self.connected = False
        self.reconnect_delay = 1.0
        self.max_reconnect_delay = 30.0
        
        # Settlement tracking
        self._pending_settlements: Dict[str, PendingSettlement] = {}
        self._settlement_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()
        
        # Background thread
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None
    
    def start(self):
        """Start the WebSocket client in a background thread."""
        if self._thread and self._thread.is_alive():
            logger.warning("[USER_WSS] Already running")
            return
        
        self.running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("[USER_WSS] Started in background thread")
    
    def stop(self):
        """Stop the WebSocket client."""
        self.running = False
        if self._loop:
            self._loop.call_soon_threadsafe(self._loop.stop)
        if self._thread:
            self._thread.join(timeout=5.0)
        logger.info("[USER_WSS] Stopped")
    
    def _run_loop(self):
        """Run the async event loop in a background thread."""
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._connect_loop())
        except Exception as e:
            logger.error(f"[USER_WSS] Loop error: {e}")
        finally:
            self._loop.close()
    
    async def _connect_loop(self):
        """Connection loop with auto-reconnect."""
        while self.running:
            try:
                await self._connect()
            except Exception as e:
                if self.on_error:
                    self.on_error(e)
                logger.warning(f"[USER_WSS] Connection error: {e}")
                
            if self.running:
                logger.info(f"[USER_WSS] Reconnecting in {self.reconnect_delay}s...")
                await asyncio.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 1.5, self.max_reconnect_delay)
    
    async def _connect(self):
        """Connect to User WebSocket and authenticate."""
        logger.info(f"[USER_WSS] Connecting to {WS_USER_URL}...")
        
        async with websockets.connect(WS_USER_URL, ping_interval=30) as ws:
            self.ws = ws
            self.connected = True
            self.reconnect_delay = 1.0  # Reset on successful connect
            logger.info("[USER_WSS] Connected!")
            
            # Authenticate
            auth_msg = {
                "auth": {
                    "apiKey": self.api_key,
                    "secret": self.api_secret,
                    "passphrase": self.api_passphrase,
                },
                "type": "user",
            }
            await ws.send(json.dumps(auth_msg))
            logger.info("[USER_WSS] Authenticated and subscribed to user channel")
            
            # Listen for messages
            async for message in ws:
                if not self.running:
                    break
                await self._handle_message(message)
        
        self.connected = False
        self.ws = None
    
    async def _handle_message(self, raw_message: str):
        """Handle incoming WebSocket message."""
        try:
            data = json.loads(raw_message)
            
            # Handle array of messages
            messages = data if isinstance(data, list) else [data]
            
            for msg in messages:
                event_type = msg.get("event_type")
                
                if event_type == "trade":
                    await self._handle_trade_event(msg)
                elif event_type == "order":
                    await self._handle_order_event(msg)
                    
        except json.JSONDecodeError:
            logger.warning(f"[USER_WSS] Invalid JSON: {raw_message[:100]}")
        except Exception as e:
            logger.error(f"[USER_WSS] Error handling message: {e}")
    
    async def _handle_trade_event(self, msg: Dict[str, Any]):
        """Handle trade status update."""
        trade_id = msg.get("id", "")
        status = msg.get("status", "")
        taker_order_id = msg.get("taker_order_id", "")
        side = msg.get("side", "")
        size = msg.get("size", "")
        price = msg.get("price", "")
        
        logger.debug(f"[USER_WSS] Trade {trade_id[:16]}...: {status} {side} {size}@{price}")
        
        # Check if this is a confirmation for a pending order
        if status in ("CONFIRMED", "MINED"):
            with self._lock:
                # Check by taker_order_id
                if taker_order_id in self._pending_settlements:
                    settlement = self._pending_settlements[taker_order_id]
                    if status == "CONFIRMED":
                        settlement.confirmed = True
                        settlement.confirmed_at = datetime.now(timezone.utc)
                        settlement.status = "CONFIRMED"
                        logger.info(f"[USER_WSS] Settlement CONFIRMED for {taker_order_id[:16]}...")
                        
                        # Signal the waiting thread
                        if taker_order_id in self._settlement_events:
                            self._settlement_events[taker_order_id].set()
                        
                        # Callback
                        if self.on_trade_confirmed:
                            self.on_trade_confirmed(taker_order_id, "CONFIRMED")
                    else:
                        settlement.status = status
                
                # Also check maker orders
                for maker_order in msg.get("maker_orders", []):
                    maker_id = maker_order.get("order_id", "")
                    if maker_id in self._pending_settlements:
                        if status == "CONFIRMED":
                            self._pending_settlements[maker_id].confirmed = True
                            self._pending_settlements[maker_id].status = "CONFIRMED"
                            if maker_id in self._settlement_events:
                                self._settlement_events[maker_id].set()
        
        elif status == "FAILED":
            with self._lock:
                if taker_order_id in self._pending_settlements:
                    self._pending_settlements[taker_order_id].status = "FAILED"
                    if taker_order_id in self._settlement_events:
                        self._settlement_events[taker_order_id].set()
                    logger.warning(f"[USER_WSS] Trade FAILED for {taker_order_id[:16]}...")
    
    async def _handle_order_event(self, msg: Dict[str, Any]):
        """Handle order status update."""
        order_id = msg.get("id", "")
        order_type = msg.get("type", "")  # PLACEMENT, UPDATE, CANCELLATION
        side = msg.get("side", "")
        
        logger.debug(f"[USER_WSS] Order {order_id[:16]}...: {order_type} {side}")
    
    def register_pending_order(self, order_id: str):
        """Register an order to track its settlement status."""
        with self._lock:
            self._pending_settlements[order_id] = PendingSettlement(
                order_id=order_id,
                created_at=datetime.now(timezone.utc),
            )
            self._settlement_events[order_id] = threading.Event()
        logger.debug(f"[USER_WSS] Registered pending order: {order_id[:16]}...")
    
    def wait_for_settlement(self, order_id: str, timeout_sec: float = 2.0) -> bool:
        """Wait for an order to be confirmed (settled on-chain).
        
        Args:
            order_id: The order ID to wait for
            timeout_sec: Maximum time to wait (default 2 seconds)
            
        Returns:
            True if settlement was confirmed, False if timeout
        """
        with self._lock:
            if order_id not in self._settlement_events:
                # Order not registered, register now
                self.register_pending_order(order_id)
            
            # Check if already confirmed
            if order_id in self._pending_settlements:
                if self._pending_settlements[order_id].confirmed:
                    return True
            
            event = self._settlement_events.get(order_id)
        
        if event:
            # Wait for confirmation or timeout
            confirmed = event.wait(timeout=timeout_sec)
            
            with self._lock:
                if order_id in self._pending_settlements:
                    return self._pending_settlements[order_id].confirmed
            
            return confirmed
        
        return False
    
    def is_settled(self, order_id: str) -> bool:
        """Check if an order has been confirmed as settled."""
        with self._lock:
            if order_id in self._pending_settlements:
                return self._pending_settlements[order_id].confirmed
        return False
    
    def cleanup_order(self, order_id: str):
        """Remove an order from settlement tracking."""
        with self._lock:
            self._pending_settlements.pop(order_id, None)
            self._settlement_events.pop(order_id, None)
    
    @property
    def is_connected(self) -> bool:
        """Check if WebSocket is connected."""
        return self.connected and self.ws is not None


class UserWebSocketSyncWrapper:
    """Synchronous wrapper for UserWebSocketClient.
    
    Provides a simple interface for the bot to use without dealing with async.
    """
    
    def __init__(
        self,
        api_key: str,
        api_secret: str,
        api_passphrase: str,
        on_trade_confirmed: Optional[Callable[[str, str], None]] = None,
    ):
        self._client = UserWebSocketClient(
            api_key=api_key,
            api_secret=api_secret,
            api_passphrase=api_passphrase,
            on_trade_confirmed=on_trade_confirmed,
        )
        self._fallback_mode = False
    
    def start(self):
        """Start the WebSocket client."""
        try:
            self._client.start()
            # Give it a moment to connect
            time.sleep(0.5)
            if not self._client.is_connected:
                logger.warning("[USER_WSS] Connection not established, will use fallback mode")
                self._fallback_mode = True
        except Exception as e:
            logger.warning(f"[USER_WSS] Failed to start: {e}, using fallback mode")
            self._fallback_mode = True
    
    def stop(self):
        """Stop the WebSocket client."""
        self._client.stop()
    
    def register_pending_order(self, order_id: str):
        """Register an order for settlement tracking."""
        if not self._fallback_mode:
            self._client.register_pending_order(order_id)
    
    def wait_for_settlement(self, order_id: str, timeout_sec: float = 2.0) -> bool:
        """Wait for settlement confirmation with fallback.
        
        If WebSocket is not connected, falls back to simple time-based wait.
        """
        if self._fallback_mode or not self._client.is_connected:
            # Fallback: just wait the timeout
            logger.debug(f"[SETTLEMENT] Fallback mode: waiting {timeout_sec}s")
            time.sleep(timeout_sec)
            return True  # Assume settled after wait
        
        return self._client.wait_for_settlement(order_id, timeout_sec)
    
    def is_settled(self, order_id: str) -> bool:
        """Check if an order has been settled."""
        if self._fallback_mode:
            return True  # Assume settled in fallback mode
        return self._client.is_settled(order_id)
    
    def cleanup_order(self, order_id: str):
        """Remove order from tracking."""
        if not self._fallback_mode:
            self._client.cleanup_order(order_id)
    
    @property
    def is_connected(self) -> bool:
        """Check connection status."""
        return not self._fallback_mode and self._client.is_connected
