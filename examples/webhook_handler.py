#!/usr/bin/env python3
"""
Example webhook handler for SagaPay notifications.

This example uses Flask to create a simple server that handles
webhook notifications from SagaPay.

To run this example:
1. Install Flask: pip install flask
2. Run the server: python webhook_handler.py
3. Expose your server to the internet (e.g., using ngrok)
4. Set your webhook URL in SagaPay to point to your server
"""

import os
import logging

from flask import Flask, request, jsonify

from sagapay import Client, IpnType, TransactionStatus, WebhookHandler, WebhookPayload
from sagapay.exceptions import SagaPayError, WebhookError

app = Flask(__name__)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Initialize the webhook handler with the OPTIONAL platform-issued IPN secret.
# This is NOT your API secret. If SagaPay has not issued you an IPN secret,
# leave it unset (None) and signature verification is skipped -- the
# verify_ipn() call below remains the primary authenticity check either way.
webhook_handler = WebhookHandler(
    ipn_secret=os.environ.get("SAGAPAY_IPN_SECRET")  # may be None
)

# Client used to confirm notifications via the verify-ipn endpoint
client = Client(
    api_key=os.environ.get("SAGAPAY_API_KEY", "your-api-key"),
    api_secret=os.environ.get("SAGAPAY_API_SECRET", "your-api-secret"),
)


@app.route("/webhook", methods=["POST"])
def handle_webhook():
    """Handle webhook notifications from SagaPay."""
    try:
        # Get the signature from the headers, e.g. "sha256=<hex digest>".
        # It is only required when an IPN secret is configured.
        signature = request.headers.get("X-Sagapay-Signature")

        # Get the exact raw request body (required for signature verification)
        payload = request.get_data()

        # Process and validate the webhook (signature is verified only
        # when an IPN secret is configured)
        webhook = webhook_handler.process_webhook(payload, signature)

        # Log the webhook
        logger.info(
            "Webhook received: ID=%s, Type=%s, Status=%s, Amount=%s",
            webhook.id,
            webhook.type,
            webhook.status,
            webhook.amount,
        )

        # Primary check: confirm the notification with SagaPay
        if webhook.tx_hash:
            verification = client.verify_ipn(
                txn_hash=webhook.tx_hash,
                type=webhook.type,
                amount=webhook.amount,
                address=webhook.address,
            )
            if not verification.verified:
                logger.error("IPN could not be verified: ID=%s", webhook.id)
                return jsonify({"received": False, "error": "IPN not verified"}), 200

        # Handle the transaction. Delivery is at-least-once, so the same
        # notification may arrive more than once -- make this idempotent
        # (e.g. skip transaction IDs you have already processed).
        handle_transaction_status(webhook)

        # Return a success response
        return jsonify({"received": True}), 200

    except WebhookError as e:
        # Log the error
        logger.error("Webhook error: %s", str(e))

        # Still return 200 to prevent retries
        return jsonify({"received": False, "error": str(e)}), 200

    except SagaPayError as e:
        # Log errors from the verify-ipn call
        logger.error("Error verifying IPN: %s", str(e))

        # Still return 200 to prevent retries
        return jsonify({"received": False, "error": str(e)}), 200

    except Exception as e:
        # Log any unexpected errors
        logger.exception("Unexpected error processing webhook: %s", str(e))

        # Still return 200 to prevent retries
        return jsonify({"received": False, "error": "Internal server error"}), 200


def handle_transaction_status(webhook: WebhookPayload) -> None:
    """Handle different transaction statuses.

    Args:
        webhook: The webhook payload
    """
    if webhook.status == TransactionStatus.COMPLETED:
        # Handle completed transaction (currently the only status SagaPay sends)
        logger.info("Transaction %s completed: %s %s", webhook.id, webhook.amount, webhook.type)

        # Example business logic (note: webhook.type is uppercase IpnType):
        if webhook.type == IpnType.DEPOSIT:
            # Update order status in your database
            logger.info("Updating order %s to status 'paid'", webhook.udf)
            # update_order_status(webhook.udf, "paid")
        else:  # IpnType.WITHDRAWAL
            # Update withdrawal status in your database
            logger.info("Updating withdrawal %s to status 'completed'", webhook.udf)
            # update_withdrawal_status(webhook.udf, "completed")

    else:
        # Other statuses are not currently sent via IPN, but log them
        # defensively in case new statuses are introduced
        logger.info(
            "Transaction %s is %s: %s %s",
            webhook.id,
            webhook.status,
            webhook.amount,
            webhook.type,
        )


if __name__ == "__main__":
    # Run the Flask app
    app.run(host="0.0.0.0", port=8080, debug=True)
