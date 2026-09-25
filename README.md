# SagaPay Python SDK

Python SDK for [SagaPay](https://sagapay.io) - the world's first free, non-custodial blockchain payment gateway service provider. This SDK enables Python developers to seamlessly integrate cryptocurrency payments without holding customer funds. With enterprise-grade security and zero transaction fees, SagaPay empowers merchants to accept crypto payments across multiple blockchains while maintaining full control of their digital assets.

## Installation

```bash
pip install sagapay-sdk
```

## Quick Start

```python
from sagapay import Client, NetworkType

# Initialize the SagaPay client
client = Client(
    api_key="your-api-key",
    api_secret="your-api-secret"
)

# Create a deposit address
deposit = client.create_deposit({
    "network_type": NetworkType.BEP20,
    "contract_address": "0",  # Use '0' for native tokens (BNB)
    "amount": "1.5",
    "ipn_url": "https://yourwebsite.com/webhook",
    "udf": "order-123",
    "type": "TEMPORARY"
})

print(f"Deposit address created: {deposit.address}")
print(f"Expires at: {deposit.expires_at}")
```

## Features

- Deposit address generation
- Withdrawal processing
- Transaction status checking
- Wallet balance fetching
- Multi-chain support (ERC20, BEP20, TRC20, POLYGON, SOLANA)
- Webhook notifications (IPN)
- Custom UDF field support
- Non-custodial architecture
- Comprehensive error handling
- Pydantic models for type safety

## API Reference

### Create Deposit

```python
deposit = client.create_deposit({
    "network_type": NetworkType.BEP20,      # Required: Blockchain network type
    "contract_address": "0",                # Required: Contract address or '0' for native coins
    "amount": "1.5",                        # Required: Expected deposit amount
    "ipn_url": "https://example.com/webhook", # Required: URL for notifications
    "udf": "order-123",                     # Optional: User-defined field
    "type": "TEMPORARY",                    # Optional: TEMPORARY or PERMANENT
    "transfer_balance": True                # Optional: Auto-transfer received funds (default: true)
})
```

### Create Withdrawal

```python
withdrawal = client.create_withdrawal({
    "network_type": NetworkType.ERC20,
    "contract_address": "0xdAC17F958D2ee523a2206206994597C13D831ec7", # USDT on Ethereum
    "address": "0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    "amount": "10.5",
    "ipn_url": "https://example.com/webhook",
    "udf": "withdrawal-456"
})
```

### Check Transaction Status

```python
# By address
status = client.check_transaction_status(
    transaction_type=TransactionType.DEPOSIT,
    address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e"
)

# By transaction ID
status = client.check_transaction_status(
    transaction_type=TransactionType.DEPOSIT,
    id="deposit-uuid"
)
```

### Fetch Wallet Balance

```python
balance = client.fetch_wallet_balance(
    address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
    network_type=NetworkType.ERC20,
    contract_address="0xdAC17F958D2ee523a2206206994597C13D831ec7" # USDT on Ethereum
)
```

### Verify IPN

`verify_ipn()` confirms directly with SagaPay that an IPN notification is genuine. It is the primary way to authenticate webhook notifications. Your API credentials are sent in the request body for this endpoint (no authentication headers are used).

```python
from sagapay import IpnType

result = client.verify_ipn(
    txn_hash="0xabc123...",   # txHash from the webhook payload
    type=IpnType.DEPOSIT,     # or "DEPOSIT" / "WITHDRAWAL"
    amount="10.5",
    address="0x742d35Cc6634C0532925a3b844Bc454e4438f44e",
)

if result.verified:
    print("Notification is genuine")
```

## Handling Webhooks (IPN)

SagaPay sends webhook notifications to your specified `ipn_url` when a transaction completes. Delivery is at-least-once, so the same notification may be delivered more than once — make your handling idempotent (e.g. skip transaction IDs you have already processed).

The primary way to confirm a notification is genuine is `client.verify_ipn()`, which checks the transaction directly with SagaPay.

In addition, each webhook request carries an `X-Sagapay-Signature: sha256=<hex digest>` header — an HMAC-SHA256 of the exact raw request body, keyed with a platform-issued IPN secret (this is NOT your API secret). If SagaPay has issued you an IPN secret, pass it to `WebhookHandler` to verify the header; if you have none, leave it unset and signature verification is skipped.

```python
from flask import Flask, request, jsonify
from sagapay import Client, IpnType, TransactionStatus, WebhookHandler

app = Flask(__name__)

client = Client(api_key="your-api-key", api_secret="your-api-secret")

# ipn_secret is the OPTIONAL platform-issued IPN secret (NOT your API secret).
# Leave it unset (None) if you have none -- signature verification is skipped.
webhook_handler = WebhookHandler(ipn_secret="your-ipn-secret")

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    # Get the signature from the headers, e.g. "sha256=<hex digest>"
    signature = request.headers.get("X-Sagapay-Signature")

    # Get the exact raw request body (required for signature verification)
    payload = request.get_data()

    try:
        # Parse the payload (the signature is verified only when an
        # ipn_secret is configured)
        webhook = webhook_handler.process_webhook(payload, signature)

        # Primary check: confirm the notification with SagaPay
        verification = client.verify_ipn(
            txn_hash=webhook.tx_hash,
            type=webhook.type,
            amount=webhook.amount,
            address=webhook.address,
        )
        if not verification.verified:
            return jsonify({"received": False, "error": "IPN not verified"}), 200

        # Handle the transaction (delivery is at-least-once -- be idempotent)
        if webhook.status == TransactionStatus.COMPLETED:
            if webhook.type == IpnType.DEPOSIT:
                # Handle successful deposit
                update_order_status(webhook.udf, "paid")
            else:
                # Handle successful withdrawal
                update_withdrawal_status(webhook.udf, "completed")

        # Return a success response
        return jsonify({"received": True}), 200

    except Exception as e:
        # Log the error and return a response
        # Still return 200 to prevent retries
        return jsonify({"received": False, "error": str(e)}), 200
```

## Webhook Payload Format

When SagaPay sends a webhook to your endpoint, it will include the following payload:

```json
{
  "id": "transaction-uuid",
  "type": "DEPOSIT|WITHDRAWAL",
  "status": "COMPLETED",
  "address": "0x123abc...",
  "networkType": "ERC20|BEP20|TRC20|POLYGON|SOLANA",
  "amount": "10.5",
  "udf": "your-optional-user-defined-field",
  "txHash": "0xabc123...",
  "timestamp": "2025-03-16T14:30:00Z"
}
```

Notes:

- `type` is uppercase (`DEPOSIT` or `WITHDRAWAL`) and parses to `IpnType`.
- `status` is currently always `COMPLETED` — notifications are only sent when a transaction completes.
- `udf` and `txHash` may be `null`.

## Error Handling

The SDK includes comprehensive error handling with specific exception types. API errors are returned as `{"error": "<human-readable message>"}` — the message is surfaced in the exception, and the full body is available on `e.response`:

```python
from sagapay import Client
from sagapay.exceptions import APIError, ValidationError, WebhookError, NetworkError

try:
    client = Client(api_key="your-api-key", api_secret="your-api-secret")
    deposit = client.create_deposit(params)
except ValidationError as e:
    print(f"Validation error: {e}")
except APIError as e:
    print(f"API error ({e.status_code}): {e.message}")
except NetworkError as e:
    print(f"Network error: {e}")
```

## License

This SDK is released under the MIT License.

## Support

For questions or support, please contact support@sagapay.io or visit [https://sagapay.io](https://sagapay.io).
