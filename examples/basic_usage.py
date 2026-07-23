#!/usr/bin/env python3
"""
Basic usage examples for the SagaPay Python SDK.
"""

import os
from pprint import pprint

from sagapay import Client, NetworkType, TransactionType


def main():
    """Run basic examples of the SagaPay SDK."""
    
    # Initialize the client with your API credentials
    client = Client(
        api_key=os.environ.get("SAGAPAY_API_KEY", "your-api-key"),
        api_secret=os.environ.get("SAGAPAY_API_SECRET", "your-api-secret"),
    )
    
    # Example 1: Create a deposit address
    print("Creating deposit address...")
    try:
        deposit = client.create_deposit({
            "network_type": NetworkType.BEP20,
            "contract_address": "0",  # Use '0' for native tokens (BNB)
            "amount": "1.5",
            "ipn_url": "https://yourwebsite.com/webhook",
            "udf": "order-123",
            "type": "TEMPORARY"
        })
        print("✓ Deposit address created:")
        pprint(deposit.model_dump())
        print()
    except Exception as e:
        print(f"✗ Error creating deposit: {e}")
    
    # Example 2: Create a withdrawal
    print("Creating withdrawal...")
    try:
        withdrawal = client.create_withdrawal({
            "network_type": NetworkType.ERC20,
            "contract_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7",  # USDT on Ethereum
            "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            "amount": "10.5",
            "ipn_url": "https://yourwebsite.com/webhook",
            "udf": "withdrawal-456"
        })
        print("✓ Withdrawal created:")
        pprint(withdrawal.model_dump())
        print()
    except Exception as e:
        print(f"✗ Error creating withdrawal: {e}")
    
    # Example 3: Check transaction status
    print("Checking transaction status...")
    try:
        address = "0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
        status = client.check_transaction_status(TransactionType.DEPOSIT, address=address)
        print("✓ Transaction status retrieved:")
        print(f"  Address: {status.address}")
        print(f"  Transaction Type: {status.transaction_type}")
        print(f"  Count: {status.count}")
        
        if status.count > 0:
            print("  Transactions:")
            for i, tx in enumerate(status.transactions):
                print(f"    #{i+1} ID: {tx.id}, Status: {tx.status}, Amount: {tx.amount}")
        print()
    except Exception as e:
        print(f"✗ Error checking transaction status: {e}")
    
    # Example 4: Fetch wallet balance
    print("Fetching wallet balance...")
    try:
        balance = client.fetch_wallet_balance(
            address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
            network_type=NetworkType.ERC20,
            contract_address="0xdAC17F958D2ee523a2206206994597C13D831ec7"  # USDT on Ethereum
        )
        print("✓ Wallet balance retrieved:")
        print(f"  Address: {balance.address}")
        print(f"  Token: {balance.token.symbol} ({balance.token.name})")
        print(f"  Balance: {balance.balance.formatted}")
    except Exception as e:
        print(f"✗ Error fetching wallet balance: {e}")


if __name__ == "__main__":
    main()