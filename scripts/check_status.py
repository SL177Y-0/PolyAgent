#!/usr/bin/env python3
"""Check current status: resolved token, mid price, and simple P&L if a temp position file exists.

This keeps it lightweight — no DB. For persistent positions, integrate a store later.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path

from src.config import Config
from src.clob_client import Client

STATE_FILE = Path("tmp_rovodev_runtime_state.json")


def main():
    cfg = Config.from_env()
    logging.basicConfig(level=getattr(logging, cfg.log_level.upper(), logging.INFO))

    client = Client(cfg)
    token = client.resolve_token_id()
    mid = client.get_mid_price(token)

    print(f"Token ID: {token}")
    print(f"Mid Price: {mid:.4f}")

    if STATE_FILE.exists():
        try:
            data = json.loads(STATE_FILE.read_text())
            pos = data.get("open_position")
            if pos:
                entry = pos.get("entry_price")
                side = pos.get("side")
                if side and entry:
                    if side.upper() == "BUY":
                        pnl_pct = (mid - entry) / entry * 100.0
                    else:
                        pnl_pct = (entry - mid) / entry * 100.0
                    print(f"Open Position: {side} ${pos.get('amount_usd')} entry {entry:.4f} → PnL {pnl_pct:.2f}%")
        except Exception:
            pass


if __name__ == "__main__":
    main()
