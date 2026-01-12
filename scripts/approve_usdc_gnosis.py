"""Approve USDC.e for Polymarket CLOB via Gnosis Safe.

For Gnosis Safe (signature_type=2), we need to:
1. Build the ERC20 approve transaction
2. Submit it through the Gnosis Safe contract
3. Sign with the owner key

The Safe address: 0xA382Ec690573Bb43fBf192497adbdA8e0A43C3dF
The owner key address: 0xB10816D4F1CD55821A7FEdD28Fa78b6c00c030b3
"""
import os
from pathlib import Path
from web3 import Web3
from eth_account import Account
import json

# Polygon RPC
RPC_URL = "https://polygon-rpc.com"

# Contract addresses
USDC_E_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"  # USDC.e on Polygon
GNOSIS_SAFE_MASTER_COPY = "0xd9Db270c1B5E3Bd161E8c8503c55cEABeE709552"  # Gnosis Safe v1.3.0 on Polygon

# Polymarket CLOB Exchange contract (from py_clob_client config)
POLYMET_EXCHANGE = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8B8982E"

# ERC20 ABI (only approve function)
ERC20_ABI = [
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

# Gnosis Safe ABI (simplified - only what we need)
GNOSIS_SAFE_ABI = [
    {
        "inputs": [
            {"name": "to", "type": "address"},
            {"name": "value", "type": "uint256"},
            {"name": "data", "type": "bytes"},
            {"name": "operation", "type": "uint8"},
            {"name": "safeTxGas", "type": "uint256"},
            {"name": "baseGas", "type": "uint256"},
            {"name": "gasPrice", "type": "uint256"},
            {"name": "gasToken", "type": "address"},
            {"name": "refundReceiver", "type": "address"},
            {"name": "signatures", "type": "bytes"}
        ],
        "name": "execTransaction",
        "outputs": [{"name": "success", "type": "bool"}],
        "stateMutability": "payable",
        "type": "function"
    },
    {
        "inputs": [],
        "name": "getThreshold",
        "outputs": [{"name": "", "type": "uint256"}],
        "stateMutability": "view",
        "type": "function"
    },
    {
        "inputs": [{"name": "owner", "type": "address"}],
        "name": "isOwner",
        "outputs": [{"name": "", "type": "bool"}],
        "stateMutability": "view",
        "type": "function"
    }
]

# Operation types: 0 = Call, 1 = DelegateCall
OPERATION_CALL = 0

def load_env():
    """Load .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ[key.strip()] = value.strip()

def main():
    # Load environment
    load_env()

    # Get private key
    private_key = os.getenv("PRIVATE_KEY", "").strip()
    if not private_key:
        print("Error: PRIVATE_KEY not found in environment")
        return

    if len(private_key) != 64:
        print(f"Error: PRIVATE_KEY must be 64 hex chars, got {len(private_key)}")
        return

    # Get addresses
    funder_address = os.getenv("FUNDER_ADDRESS", "")
    if not funder_address:
        print("Error: FUNDER_ADDRESS not found in environment")
        return

    print(f"Owner key address: 0xB10816D4F1CD55821A7FEdD28Fa78b6c00c030b3")
    print(f"Gnosis Safe address: {funder_address}")
    print(f"Polymarket Exchange: {POLYMET_EXCHANGE}")
    print(f"USDC.e: {USDC_E_ADDRESS}")
    print()

    # Connect to Polygon
    w3 = Web3(Web3.HTTPProvider(RPC_URL))
    if not w3.is_connected():
        print("Error: Could not connect to Polygon RPC")
        return

    # Create account from private key
    acct = Account.from_key(private_key)

    # Create contract instances
    usdc = w3.eth.contract(
        address=Web3.to_checksum_address(USDC_E_ADDRESS),
        abi=ERC20_ABI
    )

    # Check current allowance
    print("Checking current allowance...")
    current_allowance = usdc.functions.allowance(
        Web3.to_checksum_address(funder_address),
        Web3.to_checksum_address(POLYMET_EXCHANGE)
    ).call()
    print(f"Current allowance: {current_allowance / 1e6:.2f} USDC.e")

    if current_allowance >= 10**6:  # More than 1 USDC
        print("\nAlready approved! No need to approve again.")
        return

    # Check Safe configuration
    safe = w3.eth.contract(
        address=Web3.to_checksum_address(funder_address),
        abi=GNOSIS_SAFE_ABI
    )

    threshold = safe.functions.getThreshold().call()
    is_owner = safe.functions.isOwner(acct.address).call()

    print(f"Safe threshold: {threshold} signatures required")
    print(f"Owner key is an owner: {is_owner}")
    print()

    if not is_owner:
        print("Error: The owner key address is not an owner of this Safe!")
        return

    # Build the ERC20 approve transaction data
    print("Building approval transaction...")
    unlimited = 2**256 - 1
    approve_data = usdc.encodeABI(
        "approve",
        args=[
            Web3.to_checksum_address(POLYMET_EXCHANGE),
            unlimited
        ]
    )

    # For single-owner Safe, we can try direct approval first
    # Sometimes the owner can directly approve if the Safe is configured for it
    print("\nTrying to estimate Safe transaction...")

    # Get nonce and gas price
    nonce = w3.eth.get_transaction_count(acct.address)
    gas_price = w3.eth.gas_price

    # Build Safe transaction
    safe_tx_data = safe.encodeABI(
        "execTransaction",
        args=[
            Web3.to_checksum_address(USDC_E_ADDRESS),  # to
            0,  # value (no ETH being sent)
            approve_data,  # data (encoded approve call)
            OPERATION_CALL,  # operation (0 = call)
            0,  # safeTxGas (0 = estimate)
            0,  # baseGas (0 = estimate)
            0,  # gasPrice (0 = use current)
            "0x0000000000000000000000000000000000000000",  # gasToken
            "0x0000000000000000000000000000000000000000",  # refundReceiver
            b""  # signatures (empty for now)
        ]
    )

    # Try to execute the transaction
    try:
        tx = {
            'to': Web3.to_checksum_address(funder_address),
            'from': acct.address,
            'data': safe_tx_data,
            'nonce': nonce,
            'gas': 300000,  # Should be enough for Safe execution
            'gasPrice': gas_price,
            'chainId': 137  # Polygon
        }

        print("Estimating gas...")
        gas_estimate = w3.eth.estimate_gas(tx)
        tx['gas'] = gas_estimate + 50000  # Add buffer
        print(f"Estimated gas: {gas_estimate}")

        print("\nSigning and sending transaction...")
        signed = w3.eth.account.sign_transaction(tx, private_key)
        tx_hash = w3.eth.send_raw_transaction(signed.raw_transaction)
        print(f"Transaction sent: {tx_hash.hex()}")

        print("Waiting for confirmation...")
        receipt = w3.eth.wait_for_transaction_receipt(tx_hash, timeout=180)

        if receipt['status'] == 1:
            print("\nSUCCESS! USDC.e approved for Polymarket CLOB.")
            print(f"Transaction hash: {tx_hash.hex()}")

            # Verify the approval
            new_allowance = usdc.functions.allowance(
                Web3.to_checksum_address(funder_address),
                Web3.to_checksum_address(POLYMET_EXCHANGE)
            ).call()
            print(f"New allowance: {new_allowance / 1e6:.2f} USDC.e")
        else:
            print("FAILED! Transaction reverted.")
            print(f"Receipt: {receipt}")
    except Exception as e:
        print(f"\nError: {e}")
        print("\nThe Safe transaction might need a different approach.")
        print("\nAlternative: Approve through Polymarket UI:")
        print("1. Go to https://polymarket.com/")
        print("2. Connect your wallet (Gnosis Safe)")
        print("3. Try to make a trade - it should prompt for approval")
        print("4. Or use the 'Deposit' flow to approve USDC.e")

if __name__ == "__main__":
    main()
