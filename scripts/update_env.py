#!/usr/bin/env python3
"""Update .env file with new market settings."""
import re
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"

# Settings to update
UPDATES = {
    "MARKET_SLUG": "crban-syl-ran-2026-01-12",
    "DEFAULT_TRADE_SIZE_USD": "1.0",
    "DRY_RUN": "false",
    "MAX_SPREAD_PCT": "500",
    "SPIKE_THRESHOLD_PCT": "0.5",
    "MIN_SPIKE_STRENGTH": "0.3",
}

def update_env():
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found!")
        return False
    
    content = ENV_FILE.read_text()
    
    for key, value in UPDATES.items():
        # Pattern to match KEY=value (with or without quotes)
        pattern = rf'^{key}=.*$'
        replacement = f'{key}={value}'
        
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, replacement, content, flags=re.MULTILINE)
            print(f"Updated: {key}={value}")
        else:
            # Add if not exists
            content += f"\n{key}={value}"
            print(f"Added: {key}={value}")
    
    ENV_FILE.write_text(content)
    print()
    print("SUCCESS: .env file updated!")
    return True

if __name__ == "__main__":
    update_env()
