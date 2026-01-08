#!/usr/bin/env python3
"""Manual single market trade using .env configuration.

Usage:
  python scripts/manual_trade.py --buy --size 1.05
  python scripts/manual_trade.py --sell --size 5

Default size uses DEFAULT_TRADE_SIZE_USD from .env
"""
from __future__ import annotations

import argparse
import logging

from src.config import Config
from src.clob_client import Client


def parse_args():
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--buy", action="store_true", help="Place a BUY order")
    g.add_argument("--sell", action="store_true", help="Place a SELL order")
    p.add_argument("--size", type=float, default=None, help="USD size for market order")
    return p.parse_args()


def main():
    cfg = Config.from_env()
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    client = Client(cfg)
    token_id = client.resolve_token_id()

    args = parse_args()
    side = "BUY" if args.buy else "SELL"
    size = args.size or cfg.default_trade_size_usd

    res = client.place_market_order(side=side, amount_usd=size, token_id=token_id)
    print(res.response)


if __name__ == "__main__":
    main()
