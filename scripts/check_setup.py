#!/usr/bin/env python3
"""
Setup Verification Script
========================
Run this script before trading to verify your configuration is correct.

Usage: python scripts/check_setup.py [--pre-flight]
"""

import sys
import os
import json
import argparse

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv


def run_pre_flight_check():
    """Run quick pre-flight checks before trading."""
    from src.config import Config
    from src.clob_client import Client

    print("\n🚀 Running Pre-Flight Checks...")
    print("=" * 60)

    # 1. Config
    try:
        cfg = Config.from_env()
        print("✅ Config loaded.")
    except Exception as e:
        print(f"❌ Config Error: {e}")
        return False

    client = Client(cfg)

    # 2. Wallet Balance
    try:
        btc_tid = '108547978327958467449318042977006580876058560639743186491243488736783119648127'
        bal = client.get_balance_allowance(btc_tid)
        print(f"💰 Wallet Balance: {bal}")
    except Exception as e:
        print(f"⚠️ Balance Check Warning: {e}")

    # 3. Market Liquidity
    print("\n📊 Checking Liquidity:")

    # BTC (reference)
    print("  Bitcoin (Reference)...")
    try:
        ob_btc = client.get_orderbook(btc_tid)
        bids = ob_btc.bids if hasattr(ob_btc, 'bids') else ob_btc.get('bids', [])
        asks = ob_btc.asks if hasattr(ob_btc, 'asks') else ob_btc.get('asks', [])

        bid_btc = bids[0].price if bids else "0"
        ask_btc = asks[0].price if asks else "0"
        print(f"  ✅ Bitcoin: Bid {bid_btc} / Ask {ask_btc}")
    except Exception as e:
        print(f"  ❌ Bitcoin Check Failed: {e}")

    # Current Market
    current_slug = os.getenv("MARKET_SLUG", "Unknown")
    print(f"\n  Current Market ({current_slug})...")
    try:
        tid_curr = client.resolve_token_id()
        ob_curr = client.get_orderbook(tid_curr)

        bids_c = ob_curr.bids if hasattr(ob_curr, 'bids') else ob_curr.get('bids', [])
        asks_c = ob_curr.asks if hasattr(ob_curr, 'asks') else ob_curr.get('asks', [])

        bid_curr = bids_c[0].price if bids_c else "0"
        ask_curr = asks_c[0].price if asks_c else "0"
        print(f"  ℹ️  Current: Bid {bid_curr} / Ask {ask_curr}")

        if float(bid_curr) <= 0.01 and float(ask_curr) >= 0.99:
            print("  ⚠️  WARNING: Market appears ILLIQUID on CLOB")
        else:
            print("  ✅ Market looks active")
    except Exception as e:
        print(f"  ❌ Market Check Failed: {e}")

    print("\n🏁 Pre-Flight Check Complete.\n")
    return True


def print_header(title):
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_check(name, passed, detail=""):
    status = "✅" if passed else "❌"
    msg = f"  {status} {name}"
    if detail:
        msg += f": {detail}"
    print(msg)
    return passed


def main():
    load_dotenv()
    
    print_header("POLYMARKET TRADING AGENT - SETUP VERIFICATION")
    all_passed = True
    
    # ============================================================
    # SECTION 1: Environment File Check
    # ============================================================
    print_header("1. Environment Configuration (.env)")
    
    # Check .env exists
    env_exists = os.path.exists('.env')
    all_passed &= print_check(".env file exists", env_exists)
    
    if not env_exists:
        print("    → Copy .env.example to .env and fill in your values")
        return False
    
    # Check private key
    private_key = os.getenv('PRIVATE_KEY', '')
    pk_valid = len(private_key.replace('0x', '')) == 64
    all_passed &= print_check("PRIVATE_KEY set", pk_valid, 
                              f"{len(private_key)} chars" if private_key else "NOT SET")
    
    # Check signature type
    sig_type = os.getenv('SIGNATURE_TYPE', '0')
    sig_desc = {0: "EOA (direct wallet)", 1: "Magic/Email", 2: "Browser"}.get(int(sig_type), "Unknown")
    print_check("SIGNATURE_TYPE", True, f"{sig_type} = {sig_desc}")
    
    # ============================================================
    # SECTION 2: Configuration File Check
    # ============================================================
    print_header("2. Trading Configuration (.env)")
    
    try:
        from src.config import Config
        cfg = Config.from_env()
        all_passed &= print_check(".env loads & validates", True)

        # Market selection
        if cfg.market_slug:
            print_check("Market slug", True, cfg.market_slug)
        if cfg.market_token_id:
            print_check("Token ID", True, f"{cfg.market_token_id[:30]}...")
        if not (cfg.market_slug or cfg.market_token_id):
            all_passed &= print_check("Market configured", False, "Set MARKET_SLUG or MARKET_TOKEN_ID in .env")

        # Strategy/risk excerpts
        print_check("Default trade size", True, f"${cfg.default_trade_size_usd}")
        print_check("Spike threshold", True, f"{cfg.spike_threshold_pct}%")
        print_check("DRY_RUN", True, "ENABLED" if cfg.dry_run else "DISABLED (real trading)")
        print_check("TP / SL / MaxHold", True, f"{cfg.take_profit_pct}% / {cfg.stop_loss_pct}% / {cfg.max_hold_seconds}s")

    except Exception as e:
        all_passed &= print_check("Config validation", False, str(e))
    
    # ============================================================
    # SECTION 3: Wallet Check
    # ============================================================
    print_header("3. Wallet & Balance Check")
    
    try:
        from web3 import Web3
        
        w3 = Web3(Web3.HTTPProvider(os.getenv('POLYGON_RPC', 'https://polygon-rpc.com')))
        all_passed &= print_check("Polygon RPC connected", w3.is_connected())
        
        if private_key and pk_valid:
            pk = private_key.replace('0x', '')
            account = w3.eth.account.from_key(pk)
            addr = account.address
            print_check("Wallet address", True, addr)
            
            # Check MATIC balance
            matic_bal = w3.eth.get_balance(addr)
            matic = w3.from_wei(matic_bal, 'ether')
            matic_ok = float(matic) > 0.1
            all_passed &= print_check("MATIC for gas", matic_ok, f"{float(matic):.4f} MATIC")
            
            # Check USDC.e balance
            usdc_addr = '0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174'
            usdc_abi = [{'constant':True,'inputs':[{'name':'_owner','type':'address'}],'name':'balanceOf','outputs':[{'name':'','type':'uint256'}],'type':'function'}]
            usdc = w3.eth.contract(address=usdc_addr, abi=usdc_abi)
            usdc_bal = usdc.functions.balanceOf(addr).call()
            usdc_usd = usdc_bal / 10**6
            usdc_ok = usdc_usd >= 1.0
            all_passed &= print_check("USDC.e balance", usdc_ok, f"${usdc_usd:.2f}")
            
    except ImportError:
        print_check("Web3 installed", False, "pip install web3")
    except Exception as e:
        all_passed &= print_check("Wallet check", False, str(e))
    
    # ============================================================
    # SECTION 4: API Connection Check
    # ============================================================
    print_header("4. Polymarket API Check")
    
    try:
        from py_clob_client.client import ClobClient
        
        pk = private_key.replace('0x', '') if private_key else ''
        sig_type_int = int(os.getenv('SIGNATURE_TYPE', '0'))
        
        client = ClobClient(
            host="https://clob.polymarket.com",
            key=pk,
            chain_id=137,
            signature_type=sig_type_int
        )
        
        # Test API connection
        markets = client.get_sampling_simplified_markets()  # lightweight ping
        all_passed &= print_check("API connection", True, f"Found {len(markets) if markets else 0} markets")
        
        # Try to derive API credentials
        try:
            creds = client.derive_api_key()
            all_passed &= print_check("API credentials", True, f"Key: {creds.api_key[:16]}...")
        except Exception as e:
            all_passed &= print_check("API credentials", False, str(e)[:50])
        
    except ImportError:
        print_check("py-clob-client installed", False, "pip install py-clob-client")
    except Exception as e:
        all_passed &= print_check("API check", False, str(e)[:50])
    
    # ============================================================
    # SECTION 5: Allowances Check
    # ============================================================
    print_header("5. Contract Allowances")
    
    try:
        contracts = [
            ("CTF Exchange", "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"),
            ("NEG_RISK Exchange", "0xC5d563A36AE78145C45a50134d48A1215220f80a"),
        ]
        
        allow_abi = [{'constant':True,'inputs':[{'name':'_owner','type':'address'},{'name':'_spender','type':'address'}],'name':'allowance','outputs':[{'name':'','type':'uint256'}],'type':'function'}]
        usdc = w3.eth.contract(address='0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174', abi=allow_abi)
        
        for name, spender in contracts:
            allowance = usdc.functions.allowance(addr, spender).call()
            ok = allowance > 0
            status = "APPROVED" if ok else "NOT APPROVED"
            all_passed &= print_check(f"{name}", ok, status)
            
            if not ok:
                print(f"    → Run: python scripts/fix_allowance.py")
                
    except Exception as e:
        print_check("Allowance check", False, str(e)[:50])
    
    # ============================================================
    # SUMMARY
    # ============================================================
    print_header("SUMMARY")
    
    if all_passed:
        print("  ✅ All checks passed! You're ready to trade.")
        print("\n  Next steps:")
        print("    1. Review config/config.yaml settings")
        print("    2. Run: python main.py")
    else:
        print("  ❌ Some checks failed. Please fix the issues above.")
        print("\n  Common fixes:")
        print("    - Copy .env.example to .env and set PRIVATE_KEY")
        print("    - Run: python scripts/fix_allowance.py")
        print("    - Ensure you have MATIC for gas and USDC.e for trading")
    
    print(f"\n{'='*60}\n")
    return all_passed


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Verify PolyAgent setup before trading")
    parser.add_argument("--pre-flight", action="store_true",
                       help="Run quick pre-flight checks only")
    args = parser.parse_args()

    if args.pre_flight:
        success = run_pre_flight_check()
    else:
        success = main()

    sys.exit(0 if success else 1)
