"""Approve USDC.e for Polymarket CLOB contract."""
import os
from pathlib import Path
from web3 import Web3
from eth_account import Account

# Polygon RPC
RPC_URL = "https://polygon-rpc.com"
POLYMET_CLOB_ADDRESS = "0x4bFb273aFC67fA04C3eBa98d2C7F32B821a832bB"
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e on Polygon

# Load .env file
env_path = Path(__file__).parent.parent / ".env"
if env_path.exists():
    with open(env_path) as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                key, value = line.split("=", 1)
                os.environ[key.strip()] = value.strip()

# USDC.e ABI (only approve function)
USDC_ABI = [
    {
        "constant": False,
        "inputs": [
            {"name": "spender", "type": "address"},
            {"name": "amount", "type": "uint256"}
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function"
    },
    {
        "constant": True,
        "inputs": [
            {"name": "owner", "type": "address"},
            {"name": "spender", "type": "address"}
        ],
        "name": "allowance",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function"
    }
]

def main():
    # Load private key from .env
    private_key = os.getenv("PRIVATE_KEY", "").strip()
    if not private_key:
        print("Error: PRIVATE_KEY not found in environment")
        return

    if len(private_key) != 64:
        print(f"Error: PRIVATE_KEY must be 64 hex chars, got {len(private_key)}")
        return

    # Connect to Polygon
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("Error: Could not connect to Polygon RPC")
        return

    # Create account from private key
    acct = Account.from_key(private_key)
    print(f"Address: {acct.address}")

    # Check current allowance
    usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_E_ADDRESS), abi=USDC_ABI)
    current_allowance = usdc.functions.allowance(
        acct.address,
        POLYMET_CLOB_ADDRESS
    ).call()
    print(f"Current allowance: {current_allowance}")

    if current_allowance > 10**6:  # More than 1 USDC
        print("Already approved! No need to approve again.")
        return

    # Approve unlimited (2^256 - 1)
    unlimited = 2**256 - 1
    print(f"Approving {unlimited} USDC.e...")

    # Build transaction
    tx = usdc.functions.approve(
        Web3.to_checksum_address(POLYMET_CLOB_ADDRESS),
        unlimited
    ).build_transaction({
        'from': acct.address,
        'nonce': w3.eth.get_transaction_count(acct.address),
        'gas': 100000,
        'gasPrice': w3.eth.gas_price,
        'chainId': 137  # Polygon
    })

    # Sign and send
    signed = w3.eth.account.sign_transaction(tx, private_key)
    tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
    print(f"Transaction sent: {tx_hash.hex()}")

    # Wait for receipt
    receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=120)
    print(f"Confirmation status: {receipt['status']}")

    if receipt['status'] == 1:
        print("SUCCESS! USDC.e approved for Polymarket CLOB.")
    else:
        print("FAILED! Transaction reverted.")

if __name__ == "__main__":
    main()
