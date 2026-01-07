#!/usr/bin/env python3
"""Entry point to run the trading bot."""
from __future__ import annotations

import logging
import os
from pathlib import Path
from datetime import datetime

from src.config import Config
from src.bot import Bot


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


def main():
    cfg = Config.from_env()

    # Generate unique log file for this session
    session_log = get_session_log_file()
    configure_logging(cfg.log_level, session_log, cfg.log_format)

    logging.getLogger(__name__).info("Starting Polymarket Spike Sam Bot")
    logging.getLogger(__name__).info(f"Session log: {session_log}")

    # Basic startup checks
    if cfg.signature_type == 2 and not cfg.funder_address:
        raise SystemExit("FUNDER_ADDRESS required for Proxy mode")

    if not (cfg.market_token_id or cfg.market_slug):
        raise SystemExit("Set MARKET_TOKEN_ID or MARKET_SLUG in .env to choose a market")

    bot = Bot(cfg)
    bot.run()


if __name__ == "__main__":
    main()
