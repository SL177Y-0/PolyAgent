"""FastAPI server for PolyAgent with isolated bot session management.

Each bot is a completely independent session with its own:
- Wallet (private key, signature type, funder address)
- Market configuration
- Strategy settings
- State and logs

Bots run in parallel and can have completely different configurations.
"""
from __future__ import annotations

import asyncio
import logging
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

import uvicorn
from fastapi import FastAPI, WebSocket, WebSocketDisconnect, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import json

from .bot_session import BotSession, BotConfigData, create_bot, list_bots, get_bot, delete_bot

# NOTE: No environment variables are used.
# All configuration comes from the frontend/UI and is stored in data/bots/*.json


logger = logging.getLogger(__name__)


# === Pydantic Models for API ===


class BotStatus(BaseModel):
    """Bot status for frontend."""
    bot_id: str
    name: str
    description: str
    status: str  # running, stopped, paused, error
    created_at: str
    trading_profile: Optional[str] = None
    market_slug: Optional[str] = None
    token_id: Optional[str] = None
    wallet_address: str
    usdc_balance: float = 0.0
    max_balance_per_bot: float = 10.0
    dry_run: bool = True
    signature_type: str = "EOA"
    uptime_seconds: Optional[float] = None
    position: Optional[Dict[str, Any]] = None
    session_stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    # Strategy config fields (needed by frontend)
    spike_threshold_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    trade_size_usd: Optional[float] = None
    current_price: Optional[float] = None
    spikes_detected: Optional[int] = None


class CreateBotRequest(BaseModel):
    """Request to create a new bot with full configuration."""
    name: str
    description: str = ""

    # Wallet configuration (optional - uses default if not provided)
    private_key: Optional[str] = None
    signature_type: int = 0  # 0 = EOA, 2 = Proxy
    funder_address: Optional[str] = None

    # Market configuration
    market_slug: Optional[str] = None
    market_token_id: Optional[str] = None

    # Strategy profile
    profile: Optional[str] = None  # normal, live, edge, custom

    # Trade settings
    trade_size_usd: Optional[float] = None
    max_balance_per_bot: Optional[float] = None
    dry_run: bool = True

    # Startup entry behavior
    entry_mode: Optional[str] = None  # immediate_buy | wait_for_spike | delayed_buy
    entry_delay_seconds: Optional[int] = None

    # Session limits
    max_trades_per_session: Optional[int] = None
    session_loss_limit_usd: Optional[float] = None

    # Risk management
    spike_threshold_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_seconds: Optional[int] = None

    # Additional config overrides
    custom_env: Dict[str, str] = Field(default_factory=dict)

    # Auto-start after creation
    auto_start: bool = False

    # Rebuy settings
    rebuy_delay_seconds: Optional[float] = None
    rebuy_strategy: Optional[str] = None
    rebuy_drop_pct: Optional[float] = None


class UpdateBotRequest(BaseModel):
    """Request to update bot configuration."""
    name: Optional[str] = None
    description: Optional[str] = None

    # Market updates
    market_slug: Optional[str] = None
    market_token_id: Optional[str] = None

    # Strategy updates
    profile: Optional[str] = None
    trade_size_usd: Optional[float] = None
    max_balance_per_bot: Optional[float] = None
    dry_run: Optional[bool] = None

    # Startup entry behavior
    entry_mode: Optional[str] = None
    entry_delay_seconds: Optional[int] = None

    # Session limits
    max_trades_per_session: Optional[int] = None
    session_loss_limit_usd: Optional[float] = None

    # Risk updates
    spike_threshold_pct: Optional[float] = None
    take_profit_pct: Optional[float] = None
    stop_loss_pct: Optional[float] = None
    max_hold_seconds: Optional[int] = None

    # Custom env variables
    custom_env: Optional[Dict[str, str]] = None

    # Rebuy settings
    rebuy_delay_seconds: Optional[float] = None
    rebuy_strategy: Optional[str] = None
    rebuy_drop_pct: Optional[float] = None


class TradeRequest(BaseModel):
    """Manual trade request."""
    side: str  # BUY or SELL
    amount_usd: float
    reason: str = "manual"


class BotConfigResponse(BaseModel):
    """Response with bot configuration."""
    bot_id: str
    name: str
    description: str
    status: str
    created_at: str
    config: Dict[str, Any]


# === WebSocket Connection Manager ===


class ConnectionManager:
    """Manages WebSocket connections for real-time updates."""

    def __init__(self):
        self.active_connections: List[WebSocket] = []
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        await websocket.accept()
        async with self._lock:
            self.active_connections.append(websocket)
        logger.info(f"WebSocket connected. Total: {len(self.active_connections)}")

    async def disconnect(self, websocket: WebSocket):
        async with self._lock:
            if websocket in self.active_connections:
                self.active_connections.remove(websocket)
        logger.info(f"WebSocket disconnected. Total: {len(self.active_connections)}")

    async def broadcast(self, message: dict):
        """Broadcast a message to all connected clients."""
        async with self._lock:
            disconnected = []
            for connection in self.active_connections:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.warning(f"Failed to send to WebSocket: {e}")
                    disconnected.append(connection)

            for conn in disconnected:
                self.active_connections.remove(conn)


# === Global State ===

manager = ConnectionManager()


# === FastAPI App ===

app = FastAPI(
    title="PolyAgent API",
    description="Multi-bot trading API with isolated sessions",
    version="2.0.0",
)

# CORS middleware - Allow frontend on various ports
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# === Startup/Shutdown ===


@app.on_event("startup")
async def startup_event():
    """Initialize on startup."""
    # Ensure bot config directory exists
    from .bot_session import BOT_CONFIG_DIR
    BOT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing bots and set up callbacks
    bots = list_bots()
    logger.info(f"Loaded {len(bots)} bot configurations")
    
    # Set up WebSocket callbacks for existing bot sessions
    setup_bot_callbacks()
    
    # Load global settings
    load_settings()

def attach_callbacks_to_session(session: BotSession):
    """Wire up WebSocket callbacks to a session."""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.get_event_loop()
    
    session.set_event_loop(loop)
    session.on_price_update = handle_price_update
    session.on_position_update = handle_position_update
    session.on_spike_detected = handle_spike_detected
    session.on_error = handle_error
    session.on_activity = handle_activity
    session.on_target_update = handle_target_update

def setup_bot_callbacks():
    """Set up WebSocket callbacks for all bot sessions."""
    from .bot_session import _active_sessions
    
    for session in _active_sessions.values():
        attach_callbacks_to_session(session)

async def handle_price_update(bot_id: str, price_data: Dict[str, Any]):
    """Handle price update from bot and broadcast via WebSocket."""
    await manager.broadcast({
        "type": "price_update",
        "bot_id": bot_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "data": price_data
    })

async def handle_position_update(bot_id: str, position_data: Dict[str, Any]):
    """Handle position update from bot and broadcast via WebSocket."""
    await manager.broadcast({
        "type": "position_update",
        "bot_id": bot_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "data": position_data
    })

async def handle_spike_detected(bot_id: str, spike_data: Dict[str, Any]):
    """Handle spike detection from bot and broadcast via WebSocket."""
    await manager.broadcast({
        "type": "spike_detected",
        "bot_id": bot_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "data": spike_data
    })

async def handle_error(bot_id: str, error_data: Dict[str, Any]):
    """Handle error from bot and broadcast via WebSocket."""
    await manager.broadcast({
        "type": "error",
        "bot_id": bot_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "data": error_data
    })

async def handle_activity(bot_id: str, activity_data: Dict[str, Any]):
    """Handle activity from bot and broadcast via WebSocket for real-time ActivityFeed."""
    await manager.broadcast({
        "type": "activity",
        "bot_id": bot_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "data": activity_data
    })

async def handle_target_update(bot_id: str, target_data: Dict[str, Any]):
    """Handle target update from bot and broadcast via WebSocket for Train of Trade strategy."""
    await manager.broadcast({
        "type": "target_update",
        "bot_id": bot_id,
        "timestamp": int(datetime.now(timezone.utc).timestamp()),
        "data": target_data
    })


@app.on_event("shutdown")
async def shutdown_event():
    """Stop all bots on shutdown."""
    bots = BotSession.list_all()
    for session in bots:
        if session.status == "running":
            session.stop()
    logger.info("All bots stopped")


# === REST Endpoints ===


@app.get("/")
async def root():
    """Root endpoint with API info."""
    return {
        "name": "PolyAgent Multi-Bot API",
        "version": "2.0.0",
        "status": "running",
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/api/status")
async def get_status():
    """Get overall system status."""
    bots = list_bots()

    return {
        "status": "running" if any(b["status"] == "running" for b in bots) else "idle",
        "bots": bots,
        "total_bots": len(bots),
        "active_bots": sum(1 for b in bots if b["status"] == "running"),
    }


# === Bot Management Endpoints ===


@app.get("/api/bots")
async def list_bots_endpoint():
    """List all bot sessions."""
    bots = list_bots()
    return {"bots": bots, "total": len(bots)}


@app.post("/api/bots")
async def create_bot_endpoint(request: CreateBotRequest):
    """Create a new bot session with custom configuration.

    This creates a completely isolated bot with its own wallet and settings.
    """
    try:
        # Build config overrides
        config_overrides = {
            "market_slug": request.market_slug,
            "market_token_id": request.market_token_id,
            "dry_run": request.dry_run,
            "custom_env": request.custom_env,
        }

        # Add wallet config if provided
        if request.private_key:
            # Validate private key format
            pk = request.private_key.strip()
            if pk.startswith("0x"):
                pk = pk[2:]
            if len(pk) != 64:
                raise HTTPException(status_code=400, detail="Private key must be 64 hex characters")
            config_overrides["private_key"] = pk

        if request.signature_type is not None:
            config_overrides["signature_type"] = request.signature_type

        if request.funder_address:
            if request.signature_type != 2:
                raise HTTPException(status_code=400, detail="Funder address only used for Proxy mode (signature_type=2)")
            config_overrides["funder_address"] = request.funder_address

        # Add trade settings
        if request.trade_size_usd is not None:
            config_overrides["default_trade_size_usd"] = request.trade_size_usd

        if request.max_balance_per_bot is not None:
            config_overrides["max_balance_per_bot"] = request.max_balance_per_bot

        # Startup entry behavior
        if request.entry_mode is not None:
            config_overrides["entry_mode"] = request.entry_mode
        if request.entry_delay_seconds is not None:
            config_overrides["entry_delay_seconds"] = request.entry_delay_seconds

        # Session limits
        if request.max_trades_per_session is not None:
            config_overrides["max_trades_per_session"] = request.max_trades_per_session
        if request.session_loss_limit_usd is not None:
            config_overrides["session_loss_limit_usd"] = request.session_loss_limit_usd

        # Add risk settings
        if request.spike_threshold_pct is not None:
            config_overrides["spike_threshold_pct"] = request.spike_threshold_pct

        if request.take_profit_pct is not None:
            config_overrides["take_profit_pct"] = request.take_profit_pct

        if request.stop_loss_pct is not None:
            config_overrides["stop_loss_pct"] = request.stop_loss_pct

        if request.max_hold_seconds is not None:
            config_overrides["max_hold_seconds"] = request.max_hold_seconds

        # Add rebuy settings
        if request.rebuy_delay_seconds is not None:
            config_overrides["rebuy_delay_seconds"] = request.rebuy_delay_seconds
        if request.rebuy_strategy is not None:
            config_overrides["rebuy_strategy"] = request.rebuy_strategy
        if request.rebuy_drop_pct is not None:
            config_overrides["rebuy_drop_pct"] = request.rebuy_drop_pct

        # Create the bot session
        session = BotSession.create(
            name=request.name,
            description=request.description,
            config_overrides=config_overrides,
            profile=request.profile,
        )

        # Set up WebSocket callbacks for new session
        attach_callbacks_to_session(session)

        if request.auto_start:
            session.start()

        # Broadcast bot created event
        await manager.broadcast({
            "type": "bot_created",
            "bot_id": session.config_data.bot_id,
            "data": session.get_status(),
        })

        return {
            "bot_id": session.config_data.bot_id,
            "name": session.config_data.name,
            "status": session.status,
        }

    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Failed to create bot: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/bots/{bot_id}")
async def get_bot_endpoint(bot_id: str):
    """Get a specific bot's status."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    return session.get_status()


@app.get("/api/bots/{bot_id}/config")
async def get_bot_config(bot_id: str):
    """Get a bot's full configuration."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    return {
        "bot_id": session.config_data.bot_id,
        "name": session.config_data.name,
        "description": session.config_data.description,
        "status": session.config_data.status,
        "created_at": session.config_data.created_at,
        "config": session.config_data.to_dict(),
    }


@app.put("/api/bots/{bot_id}")
async def update_bot_endpoint(bot_id: str, request: UpdateBotRequest):
    """Update a bot's configuration."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    # Build updates dict
    updates = {}

    if request.name is not None:
        updates["name"] = request.name
        session.config_data.name = request.name

    if request.description is not None:
        updates["description"] = request.description
        session.config_data.description = request.description

    if request.market_slug is not None:
        updates["market_slug"] = request.market_slug

    if request.market_token_id is not None:
        updates["market_token_id"] = request.market_token_id

    if request.profile is not None:
       updates["trading_profile"] = request.profile

    if request.trade_size_usd is not None:
       updates["default_trade_size_usd"] = request.trade_size_usd

    if request.max_balance_per_bot is not None:
       updates["max_balance_per_bot"] = request.max_balance_per_bot

    if request.dry_run is not None:
       updates["dry_run"] = request.dry_run

    if request.spike_threshold_pct is not None:
       updates["spike_threshold_pct"] = request.spike_threshold_pct

    if request.take_profit_pct is not None:
       updates["take_profit_pct"] = request.take_profit_pct

    if request.stop_loss_pct is not None:
       updates["stop_loss_pct"] = request.stop_loss_pct

    if request.max_hold_seconds is not None:
       updates["max_hold_seconds"] = request.max_hold_seconds
       session.config_data.max_hold_seconds = request.max_hold_seconds

    # Rebuy updates
    if request.rebuy_delay_seconds is not None:
       updates["rebuy_delay_seconds"] = request.rebuy_delay_seconds
       session.config_data.rebuy_delay_seconds = request.rebuy_delay_seconds
    if request.rebuy_strategy is not None:
       updates["rebuy_strategy"] = request.rebuy_strategy
       session.config_data.rebuy_strategy = request.rebuy_strategy
    if request.rebuy_drop_pct is not None:
       updates["rebuy_drop_pct"] = request.rebuy_drop_pct
       session.config_data.rebuy_drop_pct = request.rebuy_drop_pct

    # Custom env overrides
    if request.custom_env is not None:
        updates["custom_env"] = request.custom_env

    # Entry behavior updates
    if request.entry_mode is not None:
        updates["entry_mode"] = request.entry_mode
        session.config_data.entry_mode = request.entry_mode
    if request.entry_delay_seconds is not None:
        updates["entry_delay_seconds"] = request.entry_delay_seconds
        session.config_data.entry_delay_seconds = request.entry_delay_seconds

    # Session limit updates
    if request.max_trades_per_session is not None:
        updates["max_trades_per_session"] = request.max_trades_per_session
        session.config_data.max_trades_per_session = request.max_trades_per_session
    if request.session_loss_limit_usd is not None:
        updates["session_loss_limit_usd"] = request.session_loss_limit_usd
        session.config_data.session_loss_limit_usd = request.session_loss_limit_usd

    session.update_config(updates)
    session.save_config()

    await manager.broadcast({
        "type": "bot_updated",
        "bot_id": bot_id,
        "data": session.get_status(),
    })

    return {"status": "updated", "bot_id": bot_id}


@app.delete("/api/bots/{bot_id}")
async def delete_bot_endpoint(bot_id: str):
    """Delete a bot session."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    session.delete()

    await manager.broadcast({
        "type": "bot_deleted",
        "bot_id": bot_id,
    })

    return {"status": "deleted", "bot_id": bot_id}


@app.post("/api/bots/{bot_id}/start")
async def start_bot(bot_id: str):
    """Start a bot session."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    # Inject global daily loss limit into this session's config before start
    try:
        session.config_data.daily_loss_limit_usd = getattr(_settings_cache, "daily_loss_limit_usd", 0.0)
        session.save_config()
    except Exception:
        pass

    success = session.start()
    if not success:
        # Return the actual error message if available
        error_msg = session.last_error or "Failed to start bot"
        raise HTTPException(status_code=400, detail=error_msg)

    await manager.broadcast({
        "type": "bot_started",
        "bot_id": bot_id,
        "data": session.get_status(),
    })

    return {"status": "started", "bot_id": bot_id}


@app.post("/api/bots/{bot_id}/stop")
async def stop_bot(bot_id: str):
    """Stop a bot session."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    # Killswitch: close open position before stopping if enabled
    try:
        if _settings_cache.killswitch_on_shutdown and session.bot and session.bot.open_position:
            session.close_position()
    except Exception as e:
        logger.warning(f"Failed to killswitch-close position for {bot_id}: {e}")

    session.stop()

    await manager.broadcast({
        "type": "bot_stopped",
        "bot_id": bot_id,
    })

    return {"status": "stopped", "bot_id": bot_id}


@app.post("/api/bots/{bot_id}/pause")
async def pause_bot(bot_id: str):
    """Pause a bot session."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    success = session.pause()
    if not success:
        error_msg = session.last_error or "Failed to pause bot"
        raise HTTPException(status_code=400, detail=error_msg)

    await manager.broadcast({
        "type": "bot_paused",
        "bot_id": bot_id,
    })

    return {"status": "paused", "bot_id": bot_id}


@app.post("/api/bots/{bot_id}/resume")
async def resume_bot(bot_id: str):
    """Resume a paused bot session."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    success = session.resume()
    if not success:
        error_msg = session.last_error or "Failed to resume bot"
        raise HTTPException(status_code=400, detail=error_msg)

    await manager.broadcast({
        "type": "bot_resumed",
        "bot_id": bot_id,
    })

    return {"status": "resumed", "bot_id": bot_id}


# === Trading Endpoints ===


@app.post("/api/bots/{bot_id}/trade")
async def manual_trade(bot_id: str, request: TradeRequest):
    """Execute a manual trade on a specific bot."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    result = session.execute_trade(
        side=request.side.upper(),
        amount_usd=request.amount_usd,
    )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Trade failed"))

    await manager.broadcast({
        "type": "trade_executed",
        "bot_id": bot_id,
        "data": result,
    })

    return result


@app.post("/api/bots/{bot_id}/close-position")
async def close_position(bot_id: str):
    """Close the current position for a bot."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    result = session.close_position()

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error", "Failed to close position"))

    await manager.broadcast({
        "type": "position_closed",
        "bot_id": bot_id,
        "data": result,
    })

    return result


# === New Data Endpoints (Phase 2) ===


@app.get("/api/bots/{bot_id}/price-history")
async def get_price_history(bot_id: str, limit: int = 300, resolution: int = 1):
    """Get historical price data for the chart."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    
    if not session.bot:
        raise HTTPException(status_code=400, detail="Bot not running - no price data available")

    # Get price history from bot
    history = session.bot.history  # deque of (timestamp, price)

    # Sample based on resolution (for now, just return raw data)
    data = []
    if history:
        history_list = list(history)[-limit:]  # Get last 'limit' points
        data = [
            {"time": int(ts.timestamp()), "price": price}
            for ts, price in history_list
        ]

    return {
        "bot_id": bot_id,
        "data": data,
        "count": len(data),
        "resolution": resolution
    }


@app.get("/api/bots/{bot_id}/spike-status")
async def get_spike_status(bot_id: str):
    """Get spike detection analysis in the same shape as frontend SpikeDetection type.

    Shape returned:
    {
      "bot_id": str,
      "is_active": bool,
      "threshold": float,
      "max_change_pct": float,
      "max_change_window_sec": int,
      "volatility_cv": float,
      "max_volatility_cv": float,
      "is_volatility_filtered": bool,
      "history_size": int,
      "max_history_size": int,
      "windows": [ { window_sec, base_price, current_price, change_pct, window_min?, is_spike? } ]
    }
    """
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    bot = session.bot
    if not bot:
        return {
            "bot_id": bot_id,
            "is_active": False,
            "threshold": session.config_data.spike_threshold_pct,
            "max_change_pct": 0.0,
            "max_change_window_sec": 0,
            "volatility_cv": 0.0,
            "max_volatility_cv": session.config_data.max_volatility_cv,
            "is_volatility_filtered": False,
            "history_size": 0,
            "max_history_size": session.config_data.price_history_size,
            "windows": [],
        }

    current_price = bot.last_price if bot.last_price else 0

    # Compute multi-window analysis
    max_spike, stats = bot._compute_spike_multi_window(current_price) if current_price else (0.0, {})

    # Build windows data
    windows = []
    if hasattr(bot, 'history') and len(bot.history) > 0 and current_price:
        now = datetime.now(timezone.utc)
        windows_seconds = bot.cfg.get_spike_windows_seconds()
        for window_sec in windows_seconds:
            cutoff = now - timedelta(seconds=window_sec)
            window_prices = [(ts, p) for ts, p in bot.history if ts >= cutoff and p > 0]
            if len(window_prices) >= 2:
                base_price = window_prices[0][1]
                change_pct = (current_price - base_price) / max(base_price, 1e-9) * 100.0
                is_spike = abs(change_pct) >= bot.cfg.spike_threshold_pct
                windows.append({
                    "window_sec": window_sec,
                    "window_min": window_sec // 60,
                    "base_price": base_price,
                    "current_price": current_price,
                    "change_pct": change_pct,
                    "is_spike": is_spike,
                })

    return {
        "bot_id": bot_id,
        "is_active": session.status == "running",
        "threshold": bot.cfg.spike_threshold_pct,
        "max_change_pct": max_spike,
        "max_change_window_sec": stats.get("window_seconds", 0),
        "volatility_cv": stats.get("volatility_cv", 0.0),
        "max_volatility_cv": bot.cfg.max_volatility_cv,
        "is_volatility_filtered": stats.get("volatility_filtered", False),
        "history_size": len(bot.history) if hasattr(bot, 'history') else 0,
        "max_history_size": bot.cfg.price_history_size,
        "windows": windows,
    }


@app.get("/api/bots/{bot_id}/target")
async def get_bot_target(bot_id: str):
    """Get current trading target for Train of Trade strategy."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    bot = session.bot
    if not bot:
        return {
            "bot_id": bot_id,
            "target": None,
            "message": "Bot not running"
        }

    target = bot.current_target
    if not target:
        return {
            "bot_id": bot_id,
            "target": None,
            "message": "No target set"
        }

    return {
        "bot_id": bot_id,
        "target": target.to_dict(),
        "current_price": bot.last_price,
        "distance_to_target": (
            (bot.last_price - target.price) / target.price * 100
            if target.price and bot.last_price
            else 0
        ),
    }


@app.get("/api/bots/{bot_id}/orderbook")
async def get_orderbook(bot_id: str, depth: int = 5):
    """Get orderbook snapshot (max 5 levels)."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    
    # Return empty orderbook if bot is not running
    if not session.client:
        return {
            "bot_id": bot_id,
            "bids": [],
            "asks": [],
            "not_running": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    depth = min(depth, 5)  # Cap at 5
    try:
        ob = session.client.get_orderbook(session.token_id)
        
        def format_levels(levels, max_depth):
            result = []
            if not levels:
                return result
            # Handle list of objects or dicts
            levels_list = levels if isinstance(levels, list) else []
            if not levels_list and isinstance(levels, dict):
                # Should not happen if py-clob-client is consistent
                pass
                
            for level in levels_list[:max_depth]:
                price = float(level.price if hasattr(level, "price") else level["price"])
                size = float(level.size if hasattr(level, "size") else level["size"])
                result.append({"price": price, "size": size})
            return result
        
        # Helper to get bids/asks safely
        bids = ob.bids if hasattr(ob, "bids") else ob.get("bids", [])
        asks = ob.asks if hasattr(ob, "asks") else ob.get("asks", [])
        
        return {
            "bot_id": bot_id,
            "bids": format_levels(bids, depth),
            "asks": format_levels(asks, depth),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching orderbook: {e}")
        return {
            "bot_id": bot_id,
            "bids": [],
            "asks": [],
            "error": str(e)
        }


@app.get("/api/bots/{bot_id}/market-metrics")  
async def get_market_metrics(bot_id: str):
    """Get market metrics (bid/ask/spread/liquidity)."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")
    
    # Return empty metrics if bot is not running
    if not session.client:
        return {
            "bot_id": bot_id,
            "best_bid": 0,
            "best_ask": 0,
            "spread_pct": 0,
            "bid_liquidity": 0,
            "ask_liquidity": 0,
            "mid_price": 0,
            "not_running": True,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    try:
        metrics = session.client.get_orderbook_metrics(session.token_id)
        return {
            "bot_id": bot_id,
            "best_bid": metrics.get("best_bid", 0),
            "best_ask": metrics.get("best_ask", 0),
            "spread_pct": metrics.get("spread_pct", 0),
            "bid_liquidity": metrics.get("bid_liquidity", 0),
            "ask_liquidity": metrics.get("ask_liquidity", 0),
            "mid_price": (metrics.get("best_bid", 0) + metrics.get("best_ask", 0)) / 2,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    except Exception as e:
        logger.error(f"Error fetching metrics: {e}")
        return {
            "bot_id": bot_id,
            "error": str(e)
        }


@app.get("/api/bots/{bot_id}/activities")
async def get_activities(bot_id: str, limit: int = 100, activity_type: str = "all"):
    """Get activity log for ActivityFeed."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    # Get activities from the session's activity log
    activities = session.activity_log.get_all(limit=limit, activity_type=activity_type)
    
    # If no activities yet, add system activities about current state
    if len(activities) == 0:
        if session.bot and hasattr(session.bot, 'spikes_detected') and session.bot.spikes_detected > 0:
            activities.append({
                "id": f"act_{int(datetime.now(timezone.utc).timestamp())}_spikes",
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "type": "system",
                "message": f"Spikes detected: {session.bot.spikes_detected}",
                "details": {"spikes_count": session.bot.spikes_detected},
                "bot_id": bot_id
            })

        if session.bot and hasattr(session.bot, 'total_trades') and session.bot.total_trades > 0:
            activities.append({
                "id": f"act_{int(datetime.now(timezone.utc).timestamp())}_trades",
                "timestamp": int(datetime.now(timezone.utc).timestamp()),
                "type": "system",
                "message": f"Total trades: {session.bot.total_trades}",
                "details": {"total_trades": session.bot.total_trades},
                "bot_id": bot_id
            })
        
        # Add session started activity if running
        if session.status == "running" and session.start_time:
            activities.append({
                "id": f"act_{int(session.start_time.timestamp())}_started",
                "timestamp": int(session.start_time.timestamp()),
                "type": "system",
                "message": f"Bot started: {session.config_data.name}",
                "details": {},
                "bot_id": bot_id
            })

    return {
        "bot_id": bot_id,
        "activities": activities,
        "count": len(activities)
    }


@app.get("/api/bots/{bot_id}/trades")
async def get_trades(bot_id: str, limit: int = 100):
    """Get trade history for chart markers."""
    session = get_bot(bot_id)
    if not session:
        raise HTTPException(status_code=404, detail=f"Bot {bot_id} not found")

    # Return trade history from bot's trade list if available
    trades = []

    if session.bot and hasattr(session.bot, '_trade_history'):
        trades = session.bot._trade_history[-limit:]
    elif session.bot and hasattr(session.bot, 'total_trades'):
        # Return summary if no detailed history
        trades.append({
            "id": f"trade_summary_{bot_id}",
            "timestamp": int(datetime.now(timezone.utc).timestamp()),
            "side": "N/A",
            "price": 0.0,
            "amount_usd": 0.0,
            "pnl_usd": session.bot.realized_pnl if hasattr(session.bot, 'realized_pnl') else 0.0,
            "reason": f"Total trades: {session.bot.total_trades}"
        })

    return {
        "bot_id": bot_id,
        "trades": trades,
        "count": len(trades)
    }


# === Configuration Endpoints ===


@app.get("/api/config/profiles")
async def get_profiles():
    """Get available trading profiles."""
    from .config import TradingProfile

    profiles = TradingProfile.get_all_profiles()
    return {
        "profiles": [
            {
                "name": p.name,
                "description": p.description,
                "spike_threshold_pct": p.spike_threshold_pct,
                "take_profit_pct": p.take_profit_pct,
                "stop_loss_pct": p.stop_loss_pct,
                "default_trade_size_usd": p.default_trade_size_usd,
                "max_hold_seconds": p.max_hold_seconds,
                "cooldown_seconds": p.cooldown_seconds,
                "min_spike_strength": getattr(p, 'min_spike_strength', 0.5),
                "use_volatility_filter": getattr(p, 'use_volatility_filter', True),
                "max_volatility_cv": getattr(p, 'max_volatility_cv', 10.0),
                "rebuy_delay_seconds": getattr(p, 'rebuy_delay_seconds', 2.0),
                "rebuy_strategy": getattr(p, 'rebuy_strategy', 'immediate'),
                "rebuy_drop_pct": getattr(p, 'rebuy_drop_pct', 0.1),
            }
            for p in profiles.values()
        ]
    }


# === Global Settings Endpoints ===

# Global settings file and cache
SETTINGS_FILE = Path("data/settings.json")

class GlobalSettings(BaseModel):
   slippage_tolerance: float = 0.06
   min_bid_liquidity: float = 5.0
   min_ask_liquidity: float = 5.0
   max_spread_pct: float = 1.0
   wss_enabled: bool = True
   wss_reconnect_delay: float = 1.0
   killswitch_on_shutdown: bool = True
   log_level: str = "INFO"
   daily_loss_limit_usd: float = 0.0

# Settings cache
_settings_cache: GlobalSettings = GlobalSettings()

def load_settings():
    """Load settings from file."""
    global _settings_cache
    if SETTINGS_FILE.exists():
        try:
            with open(SETTINGS_FILE, "r") as f:
                data = json.load(f)
            _settings_cache = GlobalSettings(**data)
        except Exception as e:
            logger.warning(f"Failed to load settings: {e}")
    else:
        # Create default settings file
        save_settings()

def save_settings():
    """Save settings to file."""
    SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(SETTINGS_FILE, "w") as f:
        json.dump(_settings_cache.model_dump(), f, indent=2)

@app.get("/api/settings")
async def get_settings():
    """Get global settings."""
    return _settings_cache.dict()

@app.put("/api/settings")
async def update_settings(settings: GlobalSettings):
    """Update global settings."""
    global _settings_cache
    _settings_cache = settings

    # Save to file
    save_settings()

    # Broadcast update
    await manager.broadcast({
        "type": "settings_updated", 
        "data": settings.dict()
    })

    return {"status": "updated"}


# === WebSocket Endpoint ===


@app.post("/api/kill")
async def kill_all():
    """Killswitch: close all positions and stop all bots."""
    bots = list_bots()
    for b in bots:
        session = get_bot(b["bot_id"]) if isinstance(b, dict) else None
        if session and session.status == "running":
            try:
                if _settings_cache.killswitch_on_shutdown and session.bot and session.bot.open_position:
                    session.close_position()
            except Exception as e:
                logger.warning(f"Failed to close on killswitch for {session.config_data.bot_id}: {e}")
            session.stop()
    await manager.broadcast({"type": "system", "data": {"message": "Killswitch activated"}})
    return {"status": "killed"}

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time bot updates."""
    await manager.connect(websocket)
    try:
        # Send initial state
        await websocket.send_json({
            "type": "init",
            "data": {
                "bots": list_bots(),
            },
        })

        # Handle incoming messages
        while True:
            data = await websocket.receive_json()

            if data.get("type") == "ping":
                await websocket.send_json({"type": "pong"})

            elif data.get("type") == "subscribe_bot":
                bot_id = data.get("bot_id")
                session = get_bot(bot_id)
                if session:
                    await websocket.send_json({
                        "type": "bot_state",
                        "bot_id": bot_id,
                        "data": session.get_status(),
                    })

    except WebSocketDisconnect:
        await manager.disconnect(websocket)
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        await manager.disconnect(websocket)


# === Server Runner ===


def run_api_server(host: str = "127.0.0.1", port: int = 8000):
    """Run the API server."""
    uvicorn.run(
        "src.api_server:app",
        host=host,
        port=port,
        log_level="info",
        reload=False,
    )


if __name__ == "__main__":
    run_api_server()
