#!/usr/bin/env python3
"""Update .env file with new values.

Usage:
    python scripts/update_env.py KEY VALUE
    python scripts/update_env.py MARKET_SLUG some-market-slug
"""
import re
import sys
from pathlib import Path

ENV_FILE = Path(__file__).parent.parent / ".env"


def update_env(key: str, value: str) -> bool:
    """Update a single key in .env file."""
    if not ENV_FILE.exists():
        print(f"ERROR: {ENV_FILE} not found!")
        return False
    
    content = ENV_FILE.read_text()
    
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
    print("SUCCESS: .env file updated!")
    return True


def main():
    if len(sys.argv) < 3:
        print("Usage: python scripts/update_env.py KEY VALUE")
        print("Example: python scripts/update_env.py MARKET_SLUG some-market-slug")
        sys.exit(1)
    
    key = sys.argv[1]
    value = sys.argv[2]
    
    success = update_env(key, value)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
