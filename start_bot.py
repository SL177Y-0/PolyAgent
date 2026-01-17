#!/usr/bin/env python3
"""Entry point to run the trading bot with killswitch support."""
from __future__ import annotations

import logging
import os
import signal
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional

from src.config import Config
from src.bot import Bot

# Global bot reference for signal handler
_bot_instance: Optional[Bot] = None
_shutting_down = False

logger = logging.getLogger(__name__)


def get_session_log_file(log_dir: str = "logs") -> str:
    """Generate a unique log file name for each bot session.

    Format: logs/bot_YYYYMMDD_HHMMSS.log
    Example: logs/bot_20250110_143052.log

    Args:
        log_dir: Directory to store log files

    Returns:
        str: Full path to the unique log file for this session
    """
    log_path = Path(log_dir)
    log_path.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    return str(log_path / f"bot_{timestamp}.log")


def configure_logging(level: str, log_file: str, fmt: str = "PLAIN"):
    lvl = getattr(logging, level.upper(), logging.INFO)

    # Create logs directory if it doesn't exist
    log_path = Path(log_file)
    log_path.parent.mkdir(parents=True, exist_ok=True)

    # Common formatter
    formatter = logging.Formatter(
        "%(asctime)s %(levelname)s %(name)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    # Configure root logger
    root = logging.getLogger()
    root.setLevel(lvl)
    root.handlers = []  # Clear any existing handlers

    # Console handler (always enabled)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(lvl)
    console_handler.setFormatter(formatter)
    root.addHandler(console_handler)

    # File handler (writes all logs to file - new file each session)
    file_handler = logging.FileHandler(log_file, mode="w", encoding="utf-8")
    file_handler.setLevel(lvl)
    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)

    # Silence noisy libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)

    # Log where logs are being saved
    root.info(f"Logging to file: {log_file}")


def shutdown_handler(signum, frame):
    """Handle shutdown signals (Ctrl+C, SIGTERM) with killswitch.
    
    If KILLSWITCH_ON_SHUTDOWN is enabled and there's an open position,
    this will attempt to close the position before exiting.
    """
    global _shutting_down, _bot_instance
    
    if _shutting_down:
        logger.warning("[KILLSWITCH] Already shutting down, forcing exit...")
        sys.exit(1)
    
    _shutting_down = True
    signal_name = signal.Signals(signum).name if hasattr(signal, 'Signals') else str(signum)
    logger.info(f"[KILLSWITCH] Received {signal_name}, initiating shutdown...")
    
    if _bot_instance is None:
        logger.info("[KILLSWITCH] No bot instance, exiting cleanly")
        sys.exit(0)
    
    # Check if killswitch is enabled
    killswitch_enabled = os.getenv("KILLSWITCH_ON_SHUTDOWN", "true").lower() in ("true", "1", "yes")
    
    if not killswitch_enabled:
        logger.info("[KILLSWITCH] Killswitch disabled, exiting without closing position")
        _bot_instance._save_state()
        sys.exit(0)
    
    # Check if there's an open position
    if _bot_instance.open_position is None:
        logger.info("[KILLSWITCH] No open position, exiting cleanly")
        _bot_instance._save_state()
        sys.exit(0)
    
    logger.warning("[KILLSWITCH] Open position detected, attempting to close...")
    
    try:
        # Stop WebSocket first to prevent new trades
        if _bot_instance.ws_client:
            logger.info("[KILLSWITCH] Stopping WebSocket...")
            _bot_instance.ws_client.stop()
        
        # Get current price for exit
        price = None
        if _bot_instance.last_price and _bot_instance.last_price > 0:
            price = _bot_instance.last_price
        else:
            # Try to fetch price from REST API
            try:
                price = _bot_instance._get_price_rest()
            except Exception as e:
                logger.warning(f"[KILLSWITCH] Failed to get price: {e}")
        
        if price and price > 0:
            logger.info(f"[KILLSWITCH] Closing position at price {price:.4f}")
            _bot_instance._exit("KILLSWITCH_SHUTDOWN", price)
            logger.info("[KILLSWITCH] Position closed successfully")
        else:
            logger.error("[KILLSWITCH] Could not get price, position NOT closed!")
            logger.error("[KILLSWITCH] You may need to manually close the position")
        
        # Save final state
        _bot_instance._save_state()
        
    except Exception as e:
        logger.error(f"[KILLSWITCH] Error during shutdown: {e}")
        # Still try to save state
        try:
            _bot_instance._save_state()
        except:
            pass
    
    logger.info("[KILLSWITCH] Shutdown complete")
    sys.exit(0)


def main():
    global _bot_instance
    
    raise SystemExit("start_bot is disabled in this setup: provide config via the API/frontend.")

    # Generate unique log file for this session
    session_log = get_session_log_file()
    configure_logging(cfg.log_level, session_log, cfg.log_format)

    logger.info("Starting Polymarket Spike Sam Bot")
    logger.info(f"Session log: {session_log}")

    # Basic startup checks
    if cfg.signature_type == 2 and not cfg.funder_address:
        raise SystemExit("FUNDER_ADDRESS required for Proxy mode")

    if not (cfg.market_token_id or cfg.market_slug):
        raise SystemExit("Set MARKET_TOKEN_ID or MARKET_SLUG in .env to choose a market")

    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, shutdown_handler)   # Ctrl+C
    signal.signal(signal.SIGTERM, shutdown_handler)  # kill command
    
    # On Windows, also handle SIGBREAK if available
    if hasattr(signal, 'SIGBREAK'):
        signal.signal(signal.SIGBREAK, shutdown_handler)
    
    killswitch_enabled = os.getenv("KILLSWITCH_ON_SHUTDOWN", "true").lower() in ("true", "1", "yes")
    logger.info(f"Killswitch on shutdown: {'ENABLED' if killswitch_enabled else 'DISABLED'}")

    # Create and run bot
    _bot_instance = Bot(cfg)
    
    try:
        _bot_instance.run()
    except KeyboardInterrupt:
        # This is a backup - the signal handler should catch it first
        shutdown_handler(signal.SIGINT, None)
    except Exception as e:
        logger.error(f"Bot crashed with error: {e}")
        # Try to close position on crash if killswitch enabled
        if killswitch_enabled and _bot_instance.open_position:
            logger.warning("[CRASH_RECOVERY] Attempting to close position...")
            shutdown_handler(signal.SIGTERM, None)
        raise


if __name__ == "__main__":
    main()
