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
}, idempotency_key="payout-456")  # Optional, recommended
```

Withdrawals need an API key created with **Withdrawals** turned on, which requires two-factor authentication on your account.

Pass an `idempotency_key` (1-128 letters, digits, `-` or `_`) so that a retry after a timeout or network error cannot send the money twice. For 24 hours, a repeat with the same key returns the first withdrawal instead of creating another; while the first request is still running, a repeat fails with a 409 `APIError`. Use one key per payout, such as your own payout id.

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

`verify_ipn()` confirms a notification's transaction directly with SagaPay. Check the webhook signature first (see below); this network call is an extra check on top of it. Your API credentials are sent in the request body for this endpoint (no authentication headers are used).

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

SagaPay sends webhook notifications to your specified `ipn_url` when a transaction completes. Each one carries a signature over the exact raw request body:

```
X-Sagapay-Merchant-Signature: sha256=<hex HMAC-SHA256 of the raw body>
```

It is keyed with your **signing secret**. Copy it from the dashboard: **Webhooks → Signing secret**. It is not your API secret, and nobody else's secret can produce a valid signature for your notifications. `WebhookHandler` requires it and rejects any notification whose signature does not match.

```python
import os

from flask import Flask, request
from sagapay import IpnType, SIGNATURE_HEADER, WebhookError, WebhookHandler

app = Flask(__name__)

webhook_handler = WebhookHandler(
    os.environ["SAGAPAY_SIGNING_SECRET"],  # Webhooks -> Signing secret
    max_age_seconds=24 * 60 * 60,          # Optional: refuse notifications older than a day
)

@app.route("/webhook", methods=["POST"])
def handle_webhook():
    try:
        # The exact raw body: the signature is computed over these bytes.
        webhook = webhook_handler.process_webhook(
            request.get_data(), request.headers.get(SIGNATURE_HEADER)
        )
    except WebhookError:
        return "Invalid webhook", 401

    # Process each id once. Delivery is at-least-once, and a replayed
    # request carries a valid signature too.
    if not mark_processed(webhook.id):  # e.g. INSERT ... ON CONFLICT DO NOTHING
        return "OK", 200

    if webhook.type == IpnType.DEPOSIT:
        # Check what arrived before you credit it.
        credit_order(webhook.udf, webhook.asset, webhook.contract_address, webhook.amount)
    else:
        mark_payout_sent(webhook.udf, webhook.tx_hash)

    # Answer 2xx within 20 seconds. If your own processing fails, let the
    # request fail (5xx) so SagaPay retries it.
    return "OK", 200
```

The old `X-Sagapay-Signature` header was keyed with a secret shared by every merchant. It is retired: SagaPay no longer sends it, and this SDK no longer accepts it.

`parse_payload()` parses a body without checking its signature. Use it only for bodies you have already verified or stored.

### Replay protection

A captured webhook still has a valid signature, so the signature alone does not stop someone resending it. Protect against that:

- **Process each `id` once.** Record the ids you have handled (a unique column works) and answer duplicates with a 200 without acting on them again. This is the main defence and also covers normal retries.
- **Optionally check the age** with `max_age_seconds` on the handler, or `is_ipn_fresh(webhook, max_age_seconds)`. Keep the limit above the retry schedule (about 7.5 hours): retries reuse the original `timestamp`. A notification you resend from the dashboard also keeps it, so a resend older than your limit will be refused.
- **Check what you are crediting.** Match `asset`, `contract_address`, `amount` and `address` against the order before you fulfil it.

## Webhook Payload Format

When SagaPay sends a webhook to your endpoint, it will include the following payload:

```json
{
  "id": "transaction-uuid",
  "type": "DEPOSIT|WITHDRAWAL",
  "status": "COMPLETED",
  "address": "0x123abc...",
  "networkType": "ERC20|BEP20|TRC20|POLYGON|SOLANA",
  "asset": "USDT",
  "contractAddress": "0x55d398326f99059fF775485246999027B3197955",
  "amount": "10.5",
  "udf": "your-optional-user-defined-field",
  "txHash": "0xabc123...",
  "timestamp": "2025-03-16T14:30:00Z"
}
```

Notes:

- `type` is uppercase (`DEPOSIT` or `WITHDRAWAL`) and parses to `IpnType`.
- `status` is currently always `COMPLETED` — notifications are only sent when a transaction completes.
- `asset` and `contractAddress` (`contract_address` in Python) say what was received; `contractAddress` is `null` for the chain's native coin. `networkType` alone does not tell 100 TRX from 100 USDT.
- `udf` and `txHash` may be `null`.
- `timestamp` is set when the transaction completes and does not change on retries.
- SagaPay makes up to 6 delivery attempts, retrying after 1 min, 5 min, 15 min, 1 h and 6 h.

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
